"""
Django management command to test CommCare OAuth connection.

Usage:
    python manage.py test_oauth_connection

Tests:
    1. Token file exists and is readable
    2. Token is not expired
    3. Token can authenticate with CommCare identity API
    4. User has access to at least one domain
"""

from django.core.management.base import BaseCommand, CommandError

from apps.commcare.oauth.cli import TokenManager
from apps.commcare.oauth.utils import (
    fetch_user_domains,
    fetch_user_identity,
    get_commcare_hq_url,
)


class Command(BaseCommand):
    help = 'Test CommCare OAuth connection and token validity'

    def add_arguments(self, parser):
        parser.add_argument(
            '--token-file',
            type=str,
            help='Path to token file (defaults to ~/.commcare-sync/commcare_token.json)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        verbose = options.get('verbose', False)
        token_file = options.get('token_file')

        self.stdout.write('\nCommCare OAuth Connection Test')
        self.stdout.write('=' * 70)

        # Initialize token manager
        token_manager = TokenManager(token_file=token_file)

        # Test 1: Token file exists
        self.stdout.write('\n1. Checking token file...')
        token_data = token_manager.load_token()
        if not token_data:
            self.stdout.write(
                self.style.ERROR(
                    f'   [FAIL] No token found at {token_manager.token_file}'
                )
            )
            self.stdout.write('\n   Run: python manage.py get_commcare_token')
            raise CommandError('No token file found')
        self.stdout.write(
            self.style.SUCCESS(
                f'   [OK] Token loaded from {token_manager.token_file}'
            )
        )

        # Test 2: Token not expired
        self.stdout.write('\n2. Checking token expiration...')
        info = token_manager.get_token_info()
        if not info:
            self.stdout.write(
                self.style.ERROR('   [FAIL] Could not read token info')
            )
            raise CommandError('Invalid token data')

        if not info.get('is_valid'):
            self.stdout.write(self.style.ERROR('   [FAIL] Token is expired'))
            self.stdout.write('\n   Run: python manage.py get_commcare_token')
            raise CommandError('Token expired')

        expires_in = info.get('expires_in_seconds', 0)
        minutes = expires_in // 60
        self.stdout.write(
            self.style.SUCCESS(
                f'   [OK] Token is valid (expires in {minutes} minutes)'
            )
        )

        if verbose:
            self.stdout.write(
                f'       Saved at: {info.get("saved_at", "unknown")}'
            )
            self.stdout.write(
                f'       Expires at: {info.get("expires_at", "unknown")}'
            )
            self.stdout.write(
                f'       Has refresh token: {info.get("has_refresh_token", False)}'
            )

        # Test 3: Token authenticates with CommCare
        self.stdout.write('\n3. Testing CommCare identity API...')
        access_token = token_manager.get_valid_token()
        if not access_token:
            self.stdout.write(
                self.style.ERROR('   [FAIL] Could not get valid access token')
            )
            raise CommandError('Invalid access token')

        commcare_url = get_commcare_hq_url()
        identity = fetch_user_identity(access_token)
        if not identity:
            self.stdout.write(
                self.style.ERROR('   [FAIL] Identity API request failed')
            )
            self.stdout.write(f'       CommCare URL: {commcare_url}')
            raise CommandError('Identity API failed')

        username = identity.get('username', 'unknown')
        self.stdout.write(
            self.style.SUCCESS(f'   [OK] Authenticated as: {username}')
        )

        if verbose:
            self.stdout.write(f'       CommCare URL: {commcare_url}')

        # Test 4: Check domain access
        self.stdout.write('\n4. Checking domain access...')
        domains = fetch_user_domains(access_token)
        if domains is None:
            self.stdout.write(
                self.style.ERROR('   [FAIL] Could not fetch user domains')
            )
            raise CommandError('User domains API failed')
        elif not domains:
            self.stdout.write(
                self.style.WARNING('   [WARN] User has no domain access')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'   [OK] User has access to {len(domains)} domain(s)'
                )
            )
            if verbose or len(domains) <= 5:
                for domain_info in domains[:10]:
                    domain_name = domain_info.get('domain_name', 'unknown')
                    project_name = domain_info.get('project_name', domain_name)
                    if domain_name != project_name:
                        self.stdout.write(f'       - {domain_name} ({project_name})')
                    else:
                        self.stdout.write(f'       - {domain_name}')
                if len(domains) > 10:
                    self.stdout.write(
                        f'       ... and {len(domains) - 10} more'
                    )

        # Summary
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('All tests passed!'))
        self.stdout.write(f'\nOAuth connection is working. User: {username}')
        self.stdout.write(f'Token expires in {minutes} minutes.\n')
