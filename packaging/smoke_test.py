"""
Drives a built bundle the way the pilot will, and fails if anything the
build could have broken has broken.

    uv run python packaging/smoke_test.py <path to the executable>

With CORPORA_USERNAME and CORPORA_API_KEY in the environment, also runs a
real export from the corpora test project on www.commcarehq.org. Every
check runs, and a check that crashes counts as failed, so one run
reports everything; the exit code is 1 if any check failed.
"""

import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import psutil

from commcare_sync.launcher.env import DATABASE_FILENAME, LOGS_DIRNAME
from commcare_sync.launcher.instance import STOP_FILENAME

# apps.schedules.maintenance.DISPATCHER_FUNC, which needs Django settings.
DISPATCHER_FUNC = 'apps.schedules.tasks.run_due_schedules'
COMMCARE_HQ = 'https://www.commcarehq.org'
CORPORA_PROJECT = 'corpora'
EXPORT_SINCE_DAYS = 30

COMMAND_TIMEOUT = 600  # one --run-det invocation
START_TIMEOUT = 180  # launch to the first HTTP response
TICK_TIMEOUT = 150  # launch to the dispatcher's first successful task
STOP_TIMEOUT = 90  # stop file to exit
SETTLE_SECONDS = 2  # for killed descendants to disappear from the table
# The cluster child and at least one worker.
MIN_DESCENDANTS = 2

results: list[tuple[str, str]] = []


def record(status, message):
    print(f'{status:4} {message}', flush=True)
    results.append((status, message))


def check(name, function, *args):
    """Runs one check; a crash is a failure, not the end of the run."""
    try:
        function(*args)
    except Exception as err:
        record('FAIL', f'{name} crashed: {err!r}')


def run(command, **kwargs):
    print('+', ' '.join(map(str, command)), flush=True)
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT,
        **kwargs,
    )


def check_export_tool_help(exe, work):
    result = run([exe, '--run-det', '--help'], cwd=work)
    if result.returncode == 0 and 'commcare-export' in result.stdout:
        record('OK', '--run-det --help exits 0')
    else:
        record(
            'FAIL',
            f'--run-det --help exited {result.returncode}: '
            f'{result.stdout[-1000:]} {result.stderr[-1000:]}',
        )


def write_query_file(path):
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'cases'
    sheet.append(['Data Source', 'Source Field', 'Field'])
    sheet.append(['case', 'case_id', 'case_id'])
    sheet.append(['', 'properties.case_name', 'case_name'])
    workbook.save(path)


def check_export(exe, work):
    username = os.environ.get('CORPORA_USERNAME')
    api_key = os.environ.get('CORPORA_API_KEY')
    if not username or not api_key:
        record('SKIP', 'export: CORPORA_USERNAME and CORPORA_API_KEY not set')
        return
    query = work / 'query.xlsx'
    write_query_file(query)
    # The export tool's SQL writer does not know SQLite; Excel instead.
    output = work / 'export.xlsx'
    since = (date.today() - timedelta(days=EXPORT_SINCE_DAYS)).isoformat()
    # The export tool takes the key on the command line only.
    result = run(
        [
            exe,
            '--run-det',
            '--query',
            str(query),
            '--project',
            CORPORA_PROJECT,
            '--commcare-hq',
            COMMCARE_HQ,
            '--username',
            username,
            '--password',
            api_key,
            '--auth-mode',
            'apikey',
            '--since',
            since,
            '--output-format',
            'xlsx',
            '--output',
            str(output),
        ],
        cwd=work,
    )
    if result.returncode != 0:
        output_text = (result.stdout + result.stderr).replace(api_key, '***')
        record(
            'FAIL',
            f'--run-det export exited {result.returncode}: {output_text}',
        )
        return
    import openpyxl

    workbook = openpyxl.load_workbook(output, read_only=True)
    rows = sum(1 for _ in workbook['cases'].iter_rows()) - 1
    record('OK', f'--run-det exported {rows} case(s) from corpora to Excel')


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # A fresh install redirects / to the setup page, which wants the
    # token from the log; the redirect itself is the answer wanted.
    def redirect_request(self, *args, **kwargs):
        return None


def http_status(url):
    try:
        with urllib.request.build_opener(NoRedirect).open(
            url, timeout=5
        ) as response:
            return response.status
    except urllib.error.HTTPError as err:
        return err.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def wait_for(predicate, timeout, interval=0.5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return predicate()


class Launcher:
    """A bundle running in server mode on a free port."""

    def __init__(self, exe, data_dir):
        self.data_dir = data_dir
        self.db = data_dir / DATABASE_FILENAME
        self.port = free_port()
        self.url = f'http://127.0.0.1:{self.port}/'
        self.started = time.monotonic()
        self.last_query_error = None
        self.process = subprocess.Popen(
            [
                exe,
                '--server',
                '--port',
                str(self.port),
                '--data-dir',
                str(data_dir),
            ],
            env={
                name: value
                for name, value in os.environ.items()
                # Neither this checkout's Django settings nor the export
                # credentials are the server's business.
                if not name.startswith(('DJANGO', 'COMMCARE_SYNC', 'CORPORA_'))
            },
        )

    def elapsed(self):
        return time.monotonic() - self.started

    def query(self, sql, params=()):
        """Rows, or [] with the error kept for the failure message."""
        try:
            with sqlite3.connect(f'file:{self.db}?mode=ro', uri=True) as conn:
                conn.execute('PRAGMA busy_timeout = 2000')
                return conn.execute(sql, params).fetchall()
        except sqlite3.Error as err:
            self.last_query_error = err
            return []

    def descendants(self):
        try:
            return psutil.Process(self.process.pid).children(recursive=True)
        except psutil.NoSuchProcess:
            return []

    def kill(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait()


@contextmanager
def running(exe, data_dir):
    launcher = Launcher(exe, data_dir)
    try:
        yield launcher
    finally:
        launcher.kill()


def check_first_response(launcher):
    status = wait_for(
        lambda: launcher.process.poll() is None and http_status(launcher.url),
        START_TIMEOUT,
    )
    if status in (200, 302):
        record(
            'OK', f'/ answered {status} {launcher.elapsed():.1f}s after launch'
        )
    elif launcher.process.poll() is not None:
        record(
            'FAIL',
            f'the launcher exited with {launcher.process.returncode} before serving',
        )
    else:
        record(
            'FAIL',
            f'/ did not answer 200 or 302 within {START_TIMEOUT}s: {status}',
        )


def check_dispatcher_schedule(launcher):
    rows = launcher.query(
        'SELECT func FROM django_q_schedule WHERE func = ?', (DISPATCHER_FUNC,)
    )
    if rows:
        record('OK', 'the dispatcher schedule exists')
    else:
        record(
            'FAIL', f'no dispatcher schedule: {launcher.last_query_error!r}'
        )


def check_dispatcher_ran(launcher):
    # A fresh database's schedule fires on the first tick.
    tasks = wait_for(
        lambda: launcher.query(
            'SELECT success FROM django_q_task WHERE func = ?',
            (DISPATCHER_FUNC,),
        ),
        TICK_TIMEOUT,
        interval=2,
    )
    if tasks and all(success for (success,) in tasks):
        record(
            'OK', f'the dispatcher ran {launcher.elapsed():.0f}s after launch'
        )
    elif tasks:
        record('FAIL', f'the dispatcher ran but failed: {tasks}')
    else:
        record(
            'FAIL',
            f'the dispatcher did not run within {TICK_TIMEOUT}s: '
            f'{launcher.last_query_error!r}',
        )


def check_cluster_running(launcher):
    count = len(launcher.descendants())
    if count >= MIN_DESCENDANTS:
        record('OK', f'the cluster is running: {count} descendant process(es)')
    else:
        record(
            'FAIL',
            f'expected the cluster child and its workers, found {count}',
        )


def check_stops_on_request(launcher):
    (launcher.data_dir / STOP_FILENAME).touch()
    stopping = time.monotonic()
    try:
        launcher.process.wait(timeout=STOP_TIMEOUT)
    except subprocess.TimeoutExpired:
        record(
            'FAIL',
            f'the launcher did not stop within {STOP_TIMEOUT}s of the stop file',
        )
        return
    if launcher.process.returncode == 0:
        record(
            'OK',
            f'the launcher stopped {time.monotonic() - stopping:.1f}s after the stop file',
        )
    else:
        record(
            'FAIL',
            f'the launcher stopped with exit code {launcher.process.returncode}',
        )


def check_nothing_left(exe, descendants):
    time.sleep(SETTLE_SECONDS)
    left = []
    for pid, create_time in descendants:
        try:
            process = psutil.Process(pid)
            # Not a new process that happens to reuse the pid.
            if abs(process.create_time() - create_time) < 1:
                left.append(f'{pid} {process.cmdline()}')
        except psutil.Error:
            pass
    bundle = str(Path(exe).parent).lower()
    for process in psutil.process_iter(['pid', 'exe', 'cmdline']):
        if (process.info['exe'] or '').lower().startswith(bundle):
            left.append(f'{process.info["pid"]} {process.info["cmdline"]}')
    if left:
        record('FAIL', f'process(es) left behind: {left}')
    else:
        record('OK', 'no process left behind')


def check_no_tracebacks(data_dir):
    with_tracebacks = [
        log.name
        for log in sorted((data_dir / LOGS_DIRNAME).glob('*'))
        if 'Traceback' in log.read_text(encoding='utf-8', errors='replace')
    ]
    if with_tracebacks:
        record('FAIL', f'tracebacks in {with_tracebacks}')
    else:
        record('OK', 'no tracebacks in the logs')


def check_server(exe, data_dir):
    data_dir.mkdir()
    with running(exe, data_dir) as launcher:
        check('first response', check_first_response, launcher)
        check('dispatcher schedule', check_dispatcher_schedule, launcher)
        check('dispatcher run', check_dispatcher_ran, launcher)
        check('cluster processes', check_cluster_running, launcher)
        descendants = [
            (p.pid, p.create_time()) for p in launcher.descendants()
        ]
        check('stop', check_stops_on_request, launcher)
    check('leftover processes', check_nothing_left, exe, descendants)
    check('logs', check_no_tracebacks, data_dir)


def main():
    # Absolute: the checks run with other working directories.
    exe = Path(sys.argv[1]).resolve()
    if not exe.is_file():
        print(f'No executable at {exe}')
        return 2
    work = Path(tempfile.mkdtemp(prefix='smoke-'))
    data_dir = work / 'data'
    try:
        check('export tool help', check_export_tool_help, exe, work)
        check('export', check_export, exe, work)
        check('server', check_server, exe, data_dir)
    finally:
        summary = '\n'.join(
            f'- {status}: {message}' for status, message in results
        )
        print('\n' + summary, flush=True)
        step_summary = os.environ.get('GITHUB_STEP_SUMMARY')
        if step_summary:
            with open(step_summary, 'a', encoding='utf-8') as summary_file:
                summary_file.write(
                    f'## Smoke test ({sys.platform})\n\n{summary}\n'
                )
        logs = os.environ.get('SMOKE_TEST_LOGS')
        if logs and (data_dir / LOGS_DIRNAME).is_dir():
            shutil.copytree(data_dir / LOGS_DIRNAME, logs, dirs_exist_ok=True)
        shutil.rmtree(work, ignore_errors=True)
    return 0 if all(status != 'FAIL' for status, _ in results) else 1


if __name__ == '__main__':
    sys.exit(main())
