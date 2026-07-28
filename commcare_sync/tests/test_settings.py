"""Guardrails for base settings.py values that are easy to regress silently
(no import or runtime error would surface a wrong value)."""

from django.conf import settings


class TestQClusterTuning:
    """Q_CLUSTER defaults tuned for a laptop-friendly SQLite broker: see the
    comments beside these keys in commcare_sync/settings.py for the full
    rationale (dispatcher disk wakeups, save_limit eviction of task
    results)."""

    def test_poll_interval_is_relaxed(self):
        assert settings.Q_CLUSTER['poll'] == 1.0

    def test_save_limit_is_scoped_per_func(self):
        assert settings.Q_CLUSTER['save_limit_per'] == 'func'
