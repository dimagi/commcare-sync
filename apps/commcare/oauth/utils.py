"""
OAuth utility functions for CommCare HQ integration.

Provides PKCE generation, token exchange, refresh, and session management.
"""

import base64
import hashlib
import secrets
import time
from typing import TYPE_CHECKING, TypedDict

import httpx
from django.conf import settings

if TYPE_CHECKING:
    from django.http import HttpRequest


class OAuthTokenData(TypedDict, total=False):
    """Structure of OAuth token data stored in session."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_at: float  # Unix timestamp
    scope: str
    commcare_email: str
    server_url: str


# Session key for storing CommCare OAuth data
COMMCARE_OAUTH_SESSION_KEY = 'commcare_oauth'

# Session key for OAuth state during flow
OAUTH_STATE_SESSION_KEY = 'commcare_oauth_state'
OAUTH_PKCE_SESSION_KEY = 'commcare_oauth_pkce'


def generate_pkce_pair() -> tuple[str, str]:
    """
    Generate PKCE code verifier and challenge for secure OAuth flow.

    Returns:
        Tuple of (code_verifier, code_challenge)
    """
    # Generate a cryptographically random code verifier
    code_verifier = (
        base64.urlsafe_b64encode(secrets.token_bytes(32))
        .decode('utf-8')
        .rstrip('=')
    )

    # Create SHA256 hash and base64url encode it for the challenge
    code_challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        )
        .decode('utf-8')
        .rstrip('=')
    )

    return code_verifier, code_challenge


def generate_state() -> str:
    """Generate a cryptographically random state parameter for CSRF protection."""
    return secrets.token_urlsafe(32)


def get_commcare_hq_url() -> str:
    """Get the CommCare HQ base URL from settings."""
    return getattr(settings, 'COMMCARE_HQ_URL', 'https://www.commcarehq.org')


def get_oauth_authorize_url() -> str:
    """Get the CommCare HQ OAuth authorization endpoint."""
    return f'{get_commcare_hq_url()}/oauth/authorize/'


def get_oauth_token_url() -> str:
    """Get the CommCare HQ OAuth token endpoint."""
    return f'{get_commcare_hq_url()}/oauth/token/'


def get_identity_url() -> str:
    """Get the CommCare HQ identity API endpoint."""
    return f'{get_commcare_hq_url()}/api/v0.5/identity/'


def get_user_domains_url() -> str:
    """Get the CommCare HQ user domains API endpoint."""
    return f'{get_commcare_hq_url()}/api/v0.5/user_domains/'


def exchange_code_for_token(
    code: str,
    redirect_uri: str,
    code_verifier: str,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> dict | None:
    """
    Exchange an authorization code for access and refresh tokens.

    Args:
        code: The authorization code from the OAuth callback
        redirect_uri: The redirect URI used in the authorization request
        code_verifier: The PKCE code verifier
        client_id: OAuth client ID (defaults to settings)
        client_secret: OAuth client secret (defaults to settings, optional for public clients)

    Returns:
        Token response dict or None if exchange fails
    """
    if client_id is None:
        client_id = getattr(settings, 'COMMCARE_OAUTH_CLIENT_ID', '')

    if client_secret is None:
        client_secret = getattr(settings, 'COMMCARE_OAUTH_CLIENT_SECRET', '')

    token_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'code_verifier': code_verifier,
    }

    # Include client secret if available (for confidential clients)
    if client_secret:
        token_data['client_secret'] = client_secret

    try:
        response = httpx.post(
            get_oauth_token_url(),
            data=token_data,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError:
        return None
    except Exception:
        return None


def refresh_access_token(
    refresh_token: str,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> dict | None:
    """
    Refresh an expired access token using a refresh token.

    Args:
        refresh_token: The refresh token
        client_id: OAuth client ID (defaults to settings)
        client_secret: OAuth client secret (defaults to settings)

    Returns:
        New token response dict or None if refresh fails
    """
    if client_id is None:
        client_id = getattr(settings, 'COMMCARE_OAUTH_CLIENT_ID', '')

    if client_secret is None:
        client_secret = getattr(settings, 'COMMCARE_OAUTH_CLIENT_SECRET', '')

    token_data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
    }

    if client_secret:
        token_data['client_secret'] = client_secret

    try:
        response = httpx.post(
            get_oauth_token_url(),
            data=token_data,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError:
        return None
    except Exception:
        return None


def fetch_user_identity(access_token: str) -> dict | None:
    """
    Fetch user identity information from CommCare HQ.

    Args:
        access_token: Valid OAuth access token

    Returns:
        User identity dict with username, email, etc. or None if request fails
    """
    try:
        response = httpx.get(
            get_identity_url(),
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError:
        return None
    except Exception:
        return None


def fetch_user_domains(access_token: str) -> list[dict] | None:
    """
    Fetch the list of domains the user has access to.

    Args:
        access_token: Valid OAuth access token

    Returns:
        List of domain dicts with 'domain_name' and 'project_name', or None if request fails
    """
    try:
        response = httpx.get(
            get_user_domains_url(),
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get('objects', [])
    except httpx.HTTPStatusError:
        return None
    except Exception:
        return None


def get_commcare_oauth_session(
    request: 'HttpRequest',
) -> OAuthTokenData | None:
    """
    Get CommCare OAuth token data from the session.

    Args:
        request: Django request object

    Returns:
        OAuth token data dict or None if not present
    """
    return request.session.get(COMMCARE_OAUTH_SESSION_KEY)


def set_commcare_oauth_session(
    request: 'HttpRequest', token_data: OAuthTokenData
) -> None:
    """
    Store CommCare OAuth token data in the session.

    Args:
        request: Django request object
        token_data: OAuth token data to store
    """
    request.session[COMMCARE_OAUTH_SESSION_KEY] = token_data


def clear_commcare_oauth_session(request: 'HttpRequest') -> None:
    """
    Clear CommCare OAuth token data from the session.

    Args:
        request: Django request object
    """
    if COMMCARE_OAUTH_SESSION_KEY in request.session:
        del request.session[COMMCARE_OAUTH_SESSION_KEY]

    # Also clear any pending OAuth state
    if OAUTH_STATE_SESSION_KEY in request.session:
        del request.session[OAUTH_STATE_SESSION_KEY]
    if OAUTH_PKCE_SESSION_KEY in request.session:
        del request.session[OAUTH_PKCE_SESSION_KEY]


def has_valid_oauth_token(request: 'HttpRequest') -> bool:
    """
    Check if the session has a valid (non-expired) OAuth token.

    Args:
        request: Django request object

    Returns:
        True if valid token exists, False otherwise
    """
    oauth_data = get_commcare_oauth_session(request)
    if not oauth_data:
        return False

    access_token = oauth_data.get('access_token')
    if not access_token:
        return False

    # Check expiration with 5-minute buffer
    expires_at = oauth_data.get('expires_at', 0)
    buffer_seconds = 5 * 60
    if time.time() >= (expires_at - buffer_seconds):
        return False

    return True


def get_valid_access_token(request: 'HttpRequest') -> str | None:
    """
    Get a valid access token from the session, refreshing if needed.

    Args:
        request: Django request object

    Returns:
        Valid access token or None if unavailable
    """
    oauth_data = get_commcare_oauth_session(request)
    if not oauth_data:
        return None

    access_token = oauth_data.get('access_token')
    expires_at = oauth_data.get('expires_at', 0)
    refresh_token = oauth_data.get('refresh_token')

    # Check if token is still valid (with 5-minute buffer)
    buffer_seconds = 5 * 60
    if time.time() < (expires_at - buffer_seconds):
        return access_token

    # Try to refresh the token
    if refresh_token:
        new_token_data = refresh_access_token(refresh_token)
        if new_token_data:
            # Update session with new tokens
            oauth_data['access_token'] = new_token_data['access_token']
            if 'refresh_token' in new_token_data:
                oauth_data['refresh_token'] = new_token_data['refresh_token']
            if 'expires_in' in new_token_data:
                oauth_data['expires_at'] = (
                    time.time() + new_token_data['expires_in']
                )
            set_commcare_oauth_session(request, oauth_data)
            return new_token_data['access_token']

    return None


def validate_email_match(oauth_email: str, user_email: str) -> bool:
    """
    Validate that the OAuth email matches the user's account email.

    This is a security measure to ensure users can only connect their own
    CommCare account, not impersonate others.

    Args:
        oauth_email: Email from CommCare OAuth
        user_email: Email of the logged-in user

    Returns:
        True if emails match (case-insensitive), False otherwise
    """
    if not oauth_email or not user_email:
        return False
    return oauth_email.lower().strip() == user_email.lower().strip()
