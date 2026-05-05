# Drop django-allauth and Public Signup

## Background

The site was originally built assuming public users could sign up. In
practice, each deployment is owned by a single organization, and all
users belong to that organization. Public signup is already disabled at
the allauth adapter level (`NoNewUsersAccountAdapter`), but the library,
URLs, templates, and CTAs are still in the codebase.

This change removes django-allauth entirely and replaces it with
Django's built-in `django.contrib.auth` views. New users will be created
by superusers via the Django admin.

The project is not yet in production, so existing user sessions and
data-migration concerns do not apply.

## Goals

- Remove the `django-allauth` dependency.
- Remove "Sign up" / "Create account" CTAs from the UI.
- Replace allauth-backed login, logout, password change, and password
  reset (by email) with Django's built-in equivalents.
- Make `email` the authentication identifier on `CustomUser`.

## Non-goals

- No in-app invite flow. New users are created via Django admin only.
- No changes to the landing page beyond removing the signup button.
- No changes to `CommCareAccount` ("create account" in the
  `commcare/accounts.html` template refers to a different model and is
  out of scope).

## Replacement: Django built-in auth

Mount `django.contrib.auth.urls` at `/accounts/`. This provides URL
names: `login`, `logout`, `password_change`, `password_change_done`,
`password_reset`, `password_reset_done`, `password_reset_confirm`,
`password_reset_complete`.

Django expects templates under `templates/registration/`. The existing
templates in `templates/account/` will be moved and renamed to match
Django's names, and their `{% url 'account_*' %}` references will be
rewritten.

## Changes

### Dependency

- Remove `django-allauth` from `pyproject.toml` and refresh the lockfile.

### Settings (`commcare_sync/settings.py`, `commcare_sync/settings_docker.py`)

- Remove `'allauth'` and `'allauth.account'` from `INSTALLED_APPS`.
- Remove `'allauth.account.middleware.AccountMiddleware'` from
  `MIDDLEWARE`.
- Remove `'allauth.account.auth_backends.AuthenticationBackend'` from
  `AUTHENTICATION_BACKENDS` (leaving Django's default `ModelBackend`).
- Remove all `ACCOUNT_*` settings:
  `ACCOUNT_ADAPTER`, `ACCOUNT_LOGIN_METHODS`, `ACCOUNT_SIGNUP_FIELDS`,
  `ACCOUNT_UNIQUE_EMAIL`, `ACCOUNT_SESSION_REMEMBER`,
  `ACCOUNT_LOGOUT_ON_GET`, `ACCOUNT_EMAIL_VERIFICATION`, and the same
  in `settings_docker.py`.
- Add `LOGIN_URL = 'login'` (explicit).
- Keep `LOGIN_REDIRECT_URL = '/'`.
- Add `LOGOUT_REDIRECT_URL = '/'`.

### URLs (`commcare_sync/urls.py`)

- Replace `path('accounts/', include('allauth.urls'))` with
  `path('accounts/', include('django.contrib.auth.urls'))`.

### `apps/users/`

- Delete `apps/users/account_adapter.py`.
- Delete `apps/users/signals.py` (the `user_signed_up` notification has
  no trigger once signup is gone).
- Update `apps/users/apps.py` if it imports `signals`.
- `apps/users/models.py`: add to `CustomUser`:
  ```python
  USERNAME_FIELD = 'email'
  REQUIRED_FIELDS = []
  ```
  Also set `email = models.EmailField(unique=True)` so the username
  field is unique, as Django requires.
- Generate a migration for the model changes.
- Move `templates/account/profile.html` to `templates/users/profile.html`
  and update the `render(...)` call in `apps/users/views.py:profile`.

### Templates

Move and rename:

| From                                             | To                                              |
|--------------------------------------------------|-------------------------------------------------|
| `templates/account/login.html`                   | `templates/registration/login.html`             |
| `templates/account/logout.html`                  | `templates/registration/logged_out.html`        |
| `templates/account/password_change.html`         | `templates/registration/password_change_form.html` |
| `templates/account/password_reset.html`          | `templates/registration/password_reset_form.html` |
| `templates/account/password_reset_done.html`     | `templates/registration/password_reset_done.html` |
| `templates/account/password_reset_from_key.html` | `templates/registration/password_reset_confirm.html` |
| `templates/account/password_reset_from_key_done.html` | `templates/registration/password_reset_complete.html` |
| `templates/account/profile.html`                 | `templates/users/profile.html`                  |

Add `templates/registration/password_change_done.html` (Django requires
it; can be a thin template that messages and redirects to profile).

Delete:

- `templates/account/signup.html`
- `templates/account/verification_sent.html`
- `templates/account/email_confirm.html`
- `templates/account/base.html` — move to
  `templates/registration/base.html`; the registration templates extend
  it for the shared full-page form wrapper.
- `templates/socialaccount/` (entire directory)

In each remaining template, rewrite URL names:

- `account_login` → `login`
- `account_logout` → `logout`
- `account_change_password` → `password_change`
- `account_reset_password` → `password_reset`
- `account_email` → remove (no email-management page)

Form field handling needs minor adjustment: Django's `AuthenticationForm`
uses `username` and `password` field names, vs. allauth's `login` and
`password`. Update `login.html` accordingly.

### Top nav (`templates/web/components/top_nav.html`)

- Remove the "Sign up" button (line 94).
- Update the password-change link: `account_change_password` →
  `password_change`.
- Convert the logout anchor (currently a GET link) into a small
  CSRF-protected POST form styled as a dropdown item, since Django's
  `LogoutView` requires POST.

### Landing page (`templates/web/landing_page.html`)

- Remove the "Create account" button (lines 16–18).
- Update the "Sign in" link from `account_login` to `login`.

### Tests

- `apps/exports/tests/conftest.py`: remove the allauth rate-limit
  override block (lines ~20–24).
- Audit `apps/users/tests/` and `apps/commcare/tests/test_views.py` for
  references to `account_login` / `account_signup` URL names and update
  to Django's names.

## Verification

- `uv run ruff check` and `uv run mypy apps/ commcare_sync/ *.py` clean.
- `uv run pytest` green.
- Manual smoke: log in, log out, change password, request password
  reset (verify email is sent), follow reset link, set new password,
  log in with new password.
- `grep -r allauth` returns nothing in source.
