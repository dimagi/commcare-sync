"""
OAuth CLI Client for CommCare HQ.

Implements the OAuth Authorization Code flow with PKCE for CLI tools.
This allows scripts to authenticate users via browser and obtain access tokens.
"""

import socket
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from apps.commcare.oauth.utils import (
    fetch_user_identity,
    generate_pkce_pair,
    get_commcare_hq_url,
    get_oauth_token_url,
)


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures OAuth callback with authorization code."""

    received_code = None
    received_error = None
    received_error_description = None

    def do_GET(self):
        """Handle GET request from OAuth provider redirect."""
        query = parse_qs(urlparse(self.path).query)

        # Capture authorization code or error
        OAuthCallbackHandler.received_code = query.get('code', [None])[0]
        OAuthCallbackHandler.received_error = query.get('error', [None])[0]
        OAuthCallbackHandler.received_error_description = query.get(
            'error_description', [None]
        )[0]

        # Send response to browser
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        if OAuthCallbackHandler.received_code:
            html = """
                <html><body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: #28a745;">[SUCCESS] Authorization Successful!</h1>
                    <p>You can close this window and return to your terminal.</p>
                    <script>setTimeout(() => window.close(), 2000);</script>
                </body></html>
            """
        else:
            error_msg = (
                OAuthCallbackHandler.received_error_description
                or OAuthCallbackHandler.received_error
                or 'Unknown error'
            )
            html = f"""
                <html><body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: #dc3545;">[ERROR] Authorization Failed</h1>
                    <p>Error: {error_msg}</p>
                    <p>Please check the terminal for details.</p>
                </body></html>
            """

        self.wfile.write(html.encode('utf-8'))

    def log_message(self, format, *args):
        """Suppress HTTP server logs."""
        pass


def is_port_available(port: int) -> bool:
    """Check if a port is available for binding."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', port))
            return True
    except OSError:
        return False


def get_oauth_token(
    client_id: str,
    commcare_url: str | None = None,
    port: int = 8765,
    callback_path: str = '/callback',
    scope: str = 'access_apis',
    verbose: bool = True,
) -> dict | None:
    """
    Obtain an OAuth access token via browser-based authorization.

    This implements the OAuth Authorization Code flow with PKCE. It:
    1. Starts a local HTTP server to receive the callback
    2. Opens the user's browser to the authorization page
    3. Waits for the user to authorize
    4. Exchanges the authorization code for an access token

    Args:
        client_id: OAuth client ID (use CLI public client)
        commcare_url: CommCare HQ base URL (defaults to settings)
        port: Local port for OAuth callback (default: 8765)
        callback_path: Path for OAuth callback (default: "/callback")
        scope: OAuth scopes to request (default: "access_apis")
        verbose: Print status messages (default: True)

    Returns:
        Dict with token data including 'access_token', 'token_type', 'expires_in', etc.
        Returns None if authorization fails.
    """
    if commcare_url is None:
        commcare_url = get_commcare_hq_url()

    redirect_uri = f'http://localhost:{port}{callback_path}'

    # Check if port is available
    if not is_port_available(port):
        if verbose:
            print(f'Error: Port {port} is already in use.')
            print(
                'Please close the application using it or use --port to choose a different port.'
            )
        return None

    # Reset handler state
    OAuthCallbackHandler.received_code = None
    OAuthCallbackHandler.received_error = None
    OAuthCallbackHandler.received_error_description = None

    # Generate PKCE values for security
    code_verifier, code_challenge = generate_pkce_pair()

    # Build authorization URL
    auth_params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': scope,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
    }
    auth_url = f'{commcare_url}/oauth/authorize/?{urlencode(auth_params)}'

    if verbose:
        print()
        print('=' * 70)
        print('CommCare OAuth Authorization Flow')
        print('=' * 70)
        print()
        print(f'CommCare URL: {commcare_url}')
        print(f'Client ID: {client_id}')
        print()
        print('Opening browser for authorization...')
        print('If browser does not open, visit this URL:')
        print(auth_url)
        print()
        print('Waiting for authorization...')

    # Open browser for user authorization
    webbrowser.open(auth_url)

    # Start local server and wait for callback
    server = HTTPServer(('localhost', port), OAuthCallbackHandler)
    server.handle_request()

    # Check if we received an authorization code
    if OAuthCallbackHandler.received_error:
        if verbose:
            error_msg = (
                OAuthCallbackHandler.received_error_description
                or OAuthCallbackHandler.received_error
            )
            print(f'\n[ERROR] Authorization failed: {error_msg}')
        return None

    if not OAuthCallbackHandler.received_code:
        if verbose:
            print('\n[ERROR] No authorization code received')
        return None

    if verbose:
        print('\n[OK] Authorization code received')
        print('Exchanging code for access token...')

    # Exchange authorization code for access token
    token_data = {
        'grant_type': 'authorization_code',
        'code': OAuthCallbackHandler.received_code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'code_verifier': code_verifier,
    }

    try:
        response = httpx.post(
            get_oauth_token_url(),
            data=token_data,
            timeout=30,
        )
        response.raise_for_status()
        token_response = response.json()

        if verbose:
            print('\n[OK] Successfully obtained OAuth token!')
            print('=' * 70)
            print(f'\nAccess Token: {token_response["access_token"][:20]}...')
            print(f'Token Type: {token_response.get("token_type", "Bearer")}')
            print(
                f'Expires In: {token_response.get("expires_in", "Unknown")} seconds'
            )
            if token_response.get('refresh_token'):
                print('Refresh Token: Available')
            print()

        return token_response

    except httpx.HTTPStatusError as e:
        if verbose:
            print(f'\n[ERROR] Token exchange failed: {e.response.status_code}')
            print(f'Response: {e.response.text}')
        return None
    except Exception as e:
        if verbose:
            print(f'\n[ERROR] Error exchanging token: {str(e)}')
        return None


def get_or_refresh_token(
    client_id: str,
    commcare_url: str | None = None,
    token_file: str | None = None,
    verbose: bool = True,
) -> str | None:
    """
    Get a valid token, fetching a new one if needed.

    This is a convenience function that:
    1. Checks for existing valid token
    2. Returns it if valid
    3. Fetches new token via OAuth flow if expired/missing

    Args:
        client_id: OAuth client ID
        commcare_url: CommCare HQ base URL
        token_file: Optional custom token file path
        verbose: Print status messages

    Returns:
        Valid access token or None if failed
    """
    from apps.commcare.oauth.cli.token_manager import TokenManager

    manager = TokenManager(token_file)

    # Try to get existing valid token
    token = manager.get_valid_token()

    if token:
        if verbose:
            info = manager.get_token_info()
            if info and 'expires_in_seconds' in info:
                minutes = info['expires_in_seconds'] // 60
                print(f'Using cached token (expires in {minutes} minutes)')
        return token

    # Need new token
    if verbose:
        print('No valid token found. Starting OAuth flow...')

    token_data = get_oauth_token(
        client_id=client_id,
        commcare_url=commcare_url,
        verbose=verbose,
    )

    if not token_data:
        return None

    # Fetch user identity
    access_token = token_data.get('access_token')
    user_identity = None
    if access_token:
        user_identity = fetch_user_identity(access_token)

    # Save for future use
    manager.save_token(token_data, user_identity)

    if verbose:
        print(f'Token saved to: {manager.token_file}')

    return access_token
