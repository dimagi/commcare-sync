"""
Fixtures for tests that exercise the launcher in-process.
"""

import os
from contextlib import contextmanager

from unmagic import fixture

from commcare_sync.launcher.env import DATA_DIR_ENV_VAR


@contextmanager
def unset_env_var(name):
    """
    ``monkeypatch.delenv(raising=False)`` restores nothing when the
    variable was absent to begin with, so a test that sets it leaks it.
    """
    before = os.environ.pop(name, None)
    try:
        yield
    finally:
        if before is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = before


@fixture
def no_data_dir_env_var():
    with unset_env_var(DATA_DIR_ENV_VAR):
        yield
