"""
Token Manager for CommCare OAuth CLI tokens.

Handles secure storage, loading, and validation of OAuth tokens for CLI usage.
Tokens are stored in ~/.commcare-sync/commcare_token.json
"""

import json
import os
import stat
from datetime import datetime, timedelta
from pathlib import Path


class TokenManager:
    """
    Manages OAuth token storage and retrieval for CLI tools.

    Tokens are stored in JSON format with expiration tracking.
    """

    def __init__(self, token_file: str | None = None):
        """
        Initialize token manager.

        Args:
            token_file: Path to token file. Defaults to ~/.commcare-sync/commcare_token.json
        """
        if token_file:
            self.token_file = Path(token_file)
        else:
            # Default: Store in user's home directory
            config_dir = Path.home() / '.commcare-sync'
            config_dir.mkdir(exist_ok=True)
            self.token_file = config_dir / 'commcare_token.json'

    def save_token(
        self, token_data: dict, user_identity: dict | None = None
    ) -> bool:
        """
        Save OAuth token to file with expiration timestamp.

        Args:
            token_data: Token response from OAuth provider
            user_identity: Optional user identity dict from CommCare

        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate expiration time if expires_in is provided
            if 'expires_in' in token_data:
                expires_at = (
                    datetime.now()
                    + timedelta(seconds=token_data['expires_in'])
                ).isoformat()
                token_data['expires_at'] = expires_at

            # Add saved timestamp
            token_data['saved_at'] = datetime.now().isoformat()

            # Add user identity if provided
            if user_identity:
                token_data['user_identity'] = user_identity

            # Ensure parent directory exists
            self.token_file.parent.mkdir(parents=True, exist_ok=True)

            # Write token to file
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)

            # Set restrictive permissions (owner read/write only)
            # On Windows, this may not have the same effect but we try anyway
            try:
                os.chmod(self.token_file, stat.S_IRUSR | stat.S_IWUSR)
            except (OSError, AttributeError):
                # Permissions may not work on all platforms
                pass

            return True
        except Exception as e:
            print(f'Failed to save token: {e}')
            return False

    def load_token(self) -> dict | None:
        """
        Load OAuth token from file.

        Returns:
            Token data dict or None if file doesn't exist or is invalid
        """
        try:
            if not self.token_file.exists():
                return None

            with open(self.token_file) as f:
                return json.load(f)
        except Exception:
            return None

    def get_valid_token(self) -> str | None:
        """
        Get a valid access token, checking expiration.

        Returns:
            Access token string if valid, None if expired or not found
        """
        token_data = self.load_token()

        if not token_data:
            return None

        # Check if token has expired
        if 'expires_at' in token_data:
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            # Add 5 minute buffer before expiration
            if datetime.now() >= (expires_at - timedelta(minutes=5)):
                return None

        return token_data.get('access_token')

    def is_expired(self) -> bool:
        """
        Check if the stored token is expired.

        Returns:
            True if expired or no token, False if still valid
        """
        return self.get_valid_token() is None

    def clear_token(self) -> bool:
        """
        Delete the stored token file.

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.token_file.exists():
                self.token_file.unlink()
            return True
        except Exception:
            return False

    def get_token_info(self) -> dict | None:
        """
        Get information about the stored token without returning the token itself.

        Returns:
            Dict with token metadata or None if no token
        """
        token_data = self.load_token()

        if not token_data:
            return None

        info = {
            'saved_at': token_data.get('saved_at'),
            'expires_at': token_data.get('expires_at'),
            'token_type': token_data.get('token_type', 'Bearer'),
            'has_refresh_token': 'refresh_token' in token_data,
            'is_valid': self.get_valid_token() is not None,
            'token_file': str(self.token_file),
        }

        # Include user info if available
        user_identity = token_data.get('user_identity', {})
        if user_identity:
            info['username'] = user_identity.get('username', '')

        # Calculate time remaining
        if 'expires_at' in token_data:
            try:
                expires_at = datetime.fromisoformat(token_data['expires_at'])
                now = datetime.now()
                if now < expires_at:
                    time_remaining = expires_at - now
                    info['expires_in_seconds'] = int(
                        time_remaining.total_seconds()
                    )
                else:
                    info['expires_in_seconds'] = 0
            except (ValueError, TypeError):
                pass

        return info
