"""
OAuth views for CommCare HQ integration.

Handles the OAuth authorization flow: initiate, callback, and disconnect.
"""

import time
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.commcare.oauth.utils import (
    OAUTH_PKCE_SESSION_KEY,
    OAUTH_STATE_SESSION_KEY,
    clear_commcare_oauth_session,
    exchange_code_for_token,
    fetch_user_identity,
    generate_pkce_pair,
    generate_state,
    get_commcare_hq_url,
    get_oauth_authorize_url,
    set_commcare_oauth_session,
    validate_email_match,
)


@login_required
def oauth_initiate(request):
    """
    Initiate the CommCare OAuth authorization flow.

    Generates PKCE and state parameters, stores them in session,
    and redirects to CommCare HQ authorization page.
    """
    client_id = getattr(settings, 'COMMCARE_OAUTH_CLIENT_ID', '')

    if not client_id:
        messages.error(
            request,
            _(
                'CommCare OAuth is not configured. Please contact your administrator.'
            ),
        )
        return redirect('commcare:home')

    # Generate PKCE pair and state
    code_verifier, code_challenge = generate_pkce_pair()
    state = generate_state()

    # Store in session for verification in callback
    request.session[OAUTH_STATE_SESSION_KEY] = state
    request.session[OAUTH_PKCE_SESSION_KEY] = code_verifier

    # Build the redirect URI
    redirect_uri = request.build_absolute_uri(
        reverse('commcare:oauth_callback')
    )

    # Build authorization URL
    auth_params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'access_apis',
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
    }

    auth_url = f'{get_oauth_authorize_url()}?{urlencode(auth_params)}'

    return HttpResponseRedirect(auth_url)


@login_required
def oauth_callback(request):
    """
    Handle the OAuth callback from CommCare HQ.

    Validates state, exchanges code for tokens, fetches user identity,
    validates email match, and stores tokens in session.
    """
    # Check for errors from CommCare
    error = request.GET.get('error')
    if error:
        error_description = request.GET.get(
            'error_description', 'Unknown error'
        )
        messages.error(
            request,
            _('CommCare authorization failed: %(error)s')
            % {'error': error_description},
        )
        return redirect('commcare:home')

    # Get authorization code
    code = request.GET.get('code')
    if not code:
        messages.error(
            request, _('No authorization code received from CommCare.')
        )
        return redirect('commcare:home')

    # Validate state parameter (CSRF protection)
    state = request.GET.get('state')
    expected_state = request.session.get(OAUTH_STATE_SESSION_KEY)

    if not state or state != expected_state:
        messages.error(
            request, _('Invalid state parameter. Please try again.')
        )
        return redirect('commcare:home')

    # Get PKCE code verifier from session
    code_verifier = request.session.get(OAUTH_PKCE_SESSION_KEY)
    if not code_verifier:
        messages.error(request, _('Session expired. Please try again.'))
        return redirect('commcare:home')

    # Build redirect URI (must match the one used in authorization)
    redirect_uri = request.build_absolute_uri(
        reverse('commcare:oauth_callback')
    )

    # Exchange code for tokens
    token_response = exchange_code_for_token(
        code=code,
        redirect_uri=redirect_uri,
        code_verifier=code_verifier,
    )

    if not token_response:
        messages.error(
            request,
            _(
                'Failed to exchange authorization code for tokens. Please try again.'
            ),
        )
        return redirect('commcare:home')

    access_token = token_response.get('access_token')
    if not access_token:
        messages.error(
            request, _('No access token received. Please try again.')
        )
        return redirect('commcare:home')

    # Fetch user identity to get email
    identity = fetch_user_identity(access_token)
    if not identity:
        messages.error(
            request,
            _(
                'Failed to fetch user identity from CommCare. Please try again.'
            ),
        )
        return redirect('commcare:home')

    commcare_email = identity.get('username', '')

    # Validate email match
    if not validate_email_match(commcare_email, request.user.email):
        messages.error(
            request,
            _(
                'CommCare account email (%(commcare_email)s) does not match your '
                'CommCare Sync account email (%(sync_email)s). You can only connect '
                'a CommCare account with the same email address.'
            )
            % {
                'commcare_email': commcare_email,
                'sync_email': request.user.email,
            },
        )
        return redirect('commcare:home')

    # Calculate expiration timestamp
    expires_in = token_response.get('expires_in', 3600)
    expires_at = time.time() + expires_in

    # Store tokens in session
    oauth_data = {
        'access_token': access_token,
        'refresh_token': token_response.get('refresh_token', ''),
        'token_type': token_response.get('token_type', 'Bearer'),
        'expires_at': expires_at,
        'scope': token_response.get('scope', 'access_apis'),
        'commcare_email': commcare_email,
        'server_url': get_commcare_hq_url(),
    }
    set_commcare_oauth_session(request, oauth_data)

    # Clean up temporary session data
    if OAUTH_STATE_SESSION_KEY in request.session:
        del request.session[OAUTH_STATE_SESSION_KEY]
    if OAUTH_PKCE_SESSION_KEY in request.session:
        del request.session[OAUTH_PKCE_SESSION_KEY]

    messages.success(
        request,
        _('Successfully connected to CommCare as %(email)s.')
        % {'email': commcare_email},
    )

    return redirect('commcare:home')


@login_required
def oauth_disconnect(request):
    """
    Disconnect the CommCare OAuth connection.

    Clears OAuth tokens from the session.
    """
    clear_commcare_oauth_session(request)
    messages.success(request, _('Disconnected from CommCare.'))
    return redirect('commcare:home')
