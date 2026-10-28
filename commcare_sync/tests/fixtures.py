"""
Fixtures for tests that exercise the launcher in-process.
"""

import logging
import os
from contextlib import contextmanager

from unmagic import fixture

from commcare_sync.launcher.env import (
    DATA_DIR_ENV_VAR,
    MODE_ENV_VAR,
    PORT_ENV_VAR,
)


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


@contextmanager
def restore_launcher_process_state():
    """
    ``main()`` changes the working directory and umask, writes the
    launcher's environment variables and configures the package logger,
    none of which it undoes.
    """
    cwd = os.getcwd()
    umask = os.umask(0)
    os.umask(umask)
    launcher_logger = logging.getLogger('commcare_sync.launcher')
    handlers = list(launcher_logger.handlers)
    level, propagate = launcher_logger.level, launcher_logger.propagate
    try:
        with (
            unset_env_var(DATA_DIR_ENV_VAR),
            unset_env_var(MODE_ENV_VAR),
            unset_env_var(PORT_ENV_VAR),
        ):
            yield
    finally:
        os.chdir(cwd)
        os.umask(umask)
        for handler in list(launcher_logger.handlers):
            if handler not in handlers:
                launcher_logger.removeHandler(handler)
                handler.close()
        launcher_logger.setLevel(level)
        launcher_logger.propagate = propagate


@fixture
def launcher_process_state():
    with restore_launcher_process_state():
        yield
