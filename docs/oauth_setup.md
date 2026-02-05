CommCare OAuth Setup
====================

CommCare Sync supports OAuth integration with CommCare HQ to enable easier
configuration. OAuth allows you to:

- Auto-fetch your available CommCare domains/projects
- Browse available case types and form types
- Fetch DET export configurations directly from CommCare
- Validate export configurations against live CommCare data

**Note:** OAuth is for interactive configuration assistance only. Production
data exports still require API keys configured in your CommCare Account.

## Prerequisites

- A CommCare HQ account with access to at least one domain
- Admin access to register OAuth applications (or ask your CommCare admin)

## Step 1: Register OAuth Applications in CommCare HQ

You need to create **two OAuth applications** in CommCare HQ:

1. **Web Application** (Confidential Client) - for browser-based OAuth
2. **CLI Application** (Public Client) - for command-line tools

### Create the Web Application

1. Log into CommCare HQ at https://www.commcarehq.org
2. Navigate to **OAuth Applications**: https://www.commcarehq.org/oauth/applications/
3. Click **New Application**
4. Fill in the following:
   - **Name**: `CommCare Sync Web`
   - **Client Type**: `Confidential`
   - **Authorization Grant Type**: `Authorization code`
   - **Redirect URIs**:
     ```
     http://localhost:8001/commcare/oauth/callback/
     https://your-production-domain.com/commcare/oauth/callback/
     ```
5. Click **Save**
6. Note the **Client ID** and **Client Secret**

### Create the CLI Application

1. Click **New Application** again
2. Fill in the following:
   - **Name**: `CommCare Sync CLI`
   - **Client Type**: `Public`
   - **Authorization Grant Type**: `Authorization code`
   - **Redirect URIs**:
     ```
     http://localhost:8765/callback
     ```
3. Click **Save**
4. Note the **Client ID** (no secret for public clients)

## Step 2: Configure Environment Variables

1. Copy `.env.dev` to `.env`:
   ```bash
   cp .env.dev .env
   ```

2. Edit `.env` and uncomment/fill in the OAuth settings:
   ```bash
   COMMCARE_OAUTH_CLIENT_ID=your_web_client_id
   COMMCARE_OAUTH_CLIENT_SECRET=your_web_client_secret
   COMMCARE_OAUTH_CLI_CLIENT_ID=your_cli_client_id
   ```

## Step 3: Test the Connection

### Test CLI OAuth

```bash
# Acquire a token via browser
python manage.py get_commcare_token

# Test the connection
python manage.py test_oauth_connection
```

The `get_commcare_token` command will:
1. Open your browser to CommCare HQ authorization page
2. Wait for you to authorize
3. Save the token to `~/.commcare-sync/commcare_token.json`

### Test Web OAuth

1. Start the development server: `python manage.py runserver`
2. Navigate to http://localhost:8001/commcare/
3. Click **Connect with CommCare**
4. Authorize in CommCare HQ
5. Verify the status shows "Connected" with your email

## Security Notes

### Email Matching

For security, the CommCare OAuth email **must match** your CommCare Sync
account email. This prevents users from connecting CommCare accounts that
don't belong to them.

### Token Storage

- **Web OAuth**: Tokens are stored in the Django session (not the database)
  and expire when the session expires or when CommCare revokes the token.
- **CLI OAuth**: Tokens are stored in `~/.commcare-sync/commcare_token.json`
  with restricted file permissions.

### API Keys vs OAuth

| Feature | OAuth | API Key |
|---------|-------|---------|
| Configuration UI | Yes | No |
| Domain browsing | Yes | No |
| Export config fetching | Yes | Yes |
| Production exports | No | Yes |
| Background jobs | No | Yes |

OAuth is for interactive configuration; API keys are for production exports.

## Troubleshooting

### "OAuth is not configured"

Ensure `COMMCARE_OAUTH_CLIENT_ID` is set in your environment or settings.

### "Email mismatch" error

Your CommCare account email must match your CommCare Sync account email.
Log into CommCare with the same email address you use for CommCare Sync.

### "Failed to exchange authorization code"

Check that:
- The redirect URI in CommCare HQ matches exactly (including trailing slash)
- The client secret is correct (for web app)
- CommCare HQ is accessible

### Token expired

OAuth tokens expire after a period (typically 1 hour). Simply reconnect
by clicking "Connect with CommCare" again, or run `get_commcare_token` for CLI.

## Management Commands

| Command | Description |
|---------|-------------|
| `get_commcare_token` | Acquire OAuth token via browser |
| `test_oauth_connection` | Test token validity and CommCare API |
| `test_fetch_domains` | Test fetching available domains |
| `test_fetch_case_types` | Test fetching case types for a domain |
| `test_fetch_det_exports` | Test fetching DET export configurations |
