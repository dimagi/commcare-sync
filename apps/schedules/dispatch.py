"""Creating and dispatching runs.

Manual and scheduled runs, in any app, are created here.

There are two entry points because the two kinds of trigger differ in
one respect only: A scheduled task performs the work itself, so it wants
the run row and nothing else; A manual trigger runs inside a request and
has to hand the work to a worker.
"""

from django_q.tasks import async_task


def create_run(config, *, triggered_from_ui=False, triggered_by=None):
    """Create a run for ``config``, unless one is already active.

    Returns the run, or ``None`` if the config already has an active run.

    For scheduled tasks, which go on to perform the work inline.

    .. note:: The check is vulnerable to a race condition: Two
       concurrent triggers can both observe no active run and both
       create one. The window is small. If duplicate runs are observed
       in practice, use ``select_for_update`` inside a transaction to
       lock rows.
    """
    if config.has_active_run:
        return None
    return config.runs.create(
        config_version=config.latest_version,
        triggered_from_ui=triggered_from_ui,
        triggered_by=triggered_by,
    )


def create_run_and_dispatch(
    config, task, *, triggered_from_ui=True, triggered_by=None, **task_kwargs
):
    """Create a run for ``config`` and enqueue ``task`` to perform it.

    For manual triggers, which enqueue the work rather than doing it.

    Returns ``(run, task_id)``, or ``(None, None)`` if a run is already
    active. ``task_kwargs`` are passed through to ``task`` (e.g.
    ``start_over``). Note that Django Q2's ``async_task`` reserves several
    keyword names for its own queue options (``timeout``, ``group``,
    ``sync``, ``hook``, ``cached``, ``broker``, ``q_options``) -- a
    ``task_kwargs`` entry with one of those names is consumed by
    ``async_task`` as a queue option instead of reaching ``task``.
    """
    run = create_run(
        config, triggered_from_ui=triggered_from_ui, triggered_by=triggered_by
    )
    if run is None:
        return None, None
    return run, async_task(task, run.id, **task_kwargs)
