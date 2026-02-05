"""
Django management command to obtain CommCare OAuth token via CLI flow.

Usage:
    python manage.py get_commcare_token

Or with custom settings:
    python manage.py get_commcare_token --port 8888

This uses a public OAuth client (no secret) with PKCE for security.
Tokens are saved to ~/.commcare-sync/commcare_token.json
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.commcare.oauth.cli import TokenManager, get_oauth_token
from apps.commcare.oauth.utils import fetch_user_identity


class Command(BaseCommand):
    help = 'Obtain a CommCare OAuth access token for CLI/script usage via browser authorization'

    def add_arguments(self, parser):
        parser.add_argument(
            '--client-id',
            type=str,
            help='OAuth client ID (defaults to COMMCARE_OAUTH_CLI_CLIENT_ID from settings)',
        )
        parser.add_argument(
            '--commcare-url',
            type=str,
            help='CommCare HQ URL (defaults to COMMCARE_HQ_URL from settings)',
        )
        parser.add_argument(
            '--port',
            type=int,
            default=8765,
            help='Local port for OAuth callback (default: 8765)',
        )
        parser.add_argument(
            '--scope',
            type=str,
            default='access_apis',
            help='OAuth scopes to request (default: "access_apis")',
        )
        parser.add_argument(
            '--save-to',
            type=str,
            help='Save token to specified file instead of default location',
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress output (only print token)',
        )

    def handle(self, *args, **options):
        # Get configuration from options or settings
        client_id = options.get('client_id') or getattr(
            settings, 'COMMCARE_OAUTH_CLI_CLIENT_ID', None
        )
        commcare_url = options.get('commcare_url') or getattr(
            settings, 'COMMCARE_HQ_URL', 'https://www.commcarehq.org'
        )

        if not client_id:
            raise CommandError(
                'OAuth client ID not provided.\n'
                'Set COMMCARE_OAUTH_CLI_CLIENT_ID in settings/environment or use --client-id\n\n'
                'To set up OAuth:\n'
                '1. Create a Public OAuth application in CommCare HQ\n'
                '2. Set redirect URI to: http://localhost:8765/callback\n'
                '3. Add COMMCARE_OAUTH_CLI_CLIENT_ID to your .env file'
            )

        if not options['quiet']:
            self.stdout.write(
                self.style.SUCCESS('\nCommCare OAuth Token Setup')
            )
            self.stdout.write('=' * 70)
            self.stdout.write(f'CommCare URL: {commcare_url}')
            self.stdout.write(f'Client ID: {client_id}')
            self.stdout.write(f'Scope: {options["scope"]}')
            self.stdout.write(f'Callback Port: {options["port"]}\n')

        # Get OAuth token
        token_data = get_oauth_token(
            client_id=client_id,
            commcare_url=commcare_url,
            port=options['port'],
            scope=options['scope'],
            verbose=not options['quiet'],
        )

        if not token_data:
            raise CommandError('Failed to obtain OAuth token')

        # Fetch user identity
        access_token = token_data.get('access_token')
        user_identity = None
        if access_token:
            user_identity = fetch_user_identity(access_token)
            if user_identity and not options['quiet']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Authenticated as: {user_identity.get("username", "unknown")}'
                    )
                )

        # Save to token manager
        if options.get('save_to'):
            token_manager = TokenManager(token_file=options['save_to'])
        else:
            token_manager = TokenManager()

        if token_manager.save_token(token_data, user_identity):
            if not options['quiet']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nToken saved to: {token_manager.token_file}'
                    )
                )
        else:
            self.stderr.write(self.style.ERROR('Failed to save token'))

        # Show token info
        info = token_manager.get_token_info()
        if info and 'expires_in_seconds' in info and not options['quiet']:
            minutes = info['expires_in_seconds'] // 60
            self.stdout.write(f'Expires in: {minutes} minutes\n')

        if not options['quiet']:
            self.stdout.write(self.style.SUCCESS('Setup Complete!'))
            self.stdout.write(
                'You can now run: python manage.py test_oauth_connection\n'
            )

        # In quiet mode, just print the token
        if options['quiet']:
            self.stdout.write(access_token)
