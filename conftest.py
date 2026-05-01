"""Project-root pytest configuration.

This hook works around a subtle interaction between pytest-django and
pytest-unmagic.

pytest-django decides at COLLECTION time whether to set up the test
database for the session: it scans each test item's `fixturenames` and
`django_db` markers (see pytest_django/fixtures.py:_get_databases_for_test).
If a test only declares its DB need via unmagic's `@use('db')`, the name
isn't in `fixturenames` at collection time — unmagic resolves fixtures
lazily via `request.getfixturevalue('db')` at execution. Result:
pytest-django skips test-database creation, and tests fall through to
the developer database with no transactional isolation.

The hook below forces collection-time visibility of the default `db`
alias by applying the `django_db` marker to every test that doesn't
already have one. Tests still using the regular `db` fixture get
transactional rollback for free; tests that need `transaction=True`
or `live_server` declare those explicitly themselves and aren't
overridden because their existing closer marker wins.
"""


def pytest_collection_modifyitems(config, items):
    import pytest

    db_marker = pytest.mark.django_db
    for item in items:
        if not list(item.iter_markers(name='django_db')):
            item.add_marker(db_marker)
