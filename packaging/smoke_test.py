"""
Drives a built bundle the way the pilot will, and fails if anything the
build could have broken has broken.

    uv run python packaging/smoke_test.py <path to the executable>

With CORPORA_USERNAME and CORPORA_API_KEY in the environment, also runs a
real export from the test project on www.commcarehq.org. Every check
runs, so one run reports everything; the exit code is 1 if any failed.
"""

import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import psutil

START_TIMEOUT = 180
TICK_TIMEOUT = 150
STOP_TIMEOUT = 90
DISPATCHER_FUNC = 'apps.schedules.tasks.run_due_schedules'

results: list[tuple[bool, str]] = []


def ok(message):
    print(f'OK   {message}', flush=True)
    results.append((True, message))


def fail(message):
    print(f'FAIL {message}', flush=True)
    results.append((False, message))


def run(command, **kwargs):
    print('+', ' '.join(map(str, command)), flush=True)
    return subprocess.run(
        command, capture_output=True, text=True, timeout=600, **kwargs
    )


def check_export_tool_help(exe, work):
    result = run([exe, '--run-det', '--help'], cwd=work)
    if result.returncode == 0 and 'commcare-export' in result.stdout:
        ok('--run-det --help exits 0')
    else:
        fail(
            f'--run-det --help exited {result.returncode}: '
            f'{result.stdout[-1000:]} {result.stderr[-1000:]}'
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
        print('SKIP export: CORPORA_USERNAME and CORPORA_API_KEY not set')
        return
    query = work / 'query.xlsx'
    write_query_file(query)
    # The export tool's SQL writer does not know SQLite; Excel instead.
    output = work / 'export.xlsx'
    since = (date.today() - timedelta(days=30)).isoformat()
    result = run(
        [
            exe,
            '--run-det',
            '--query',
            str(query),
            '--project',
            'corpora',
            '--commcare-hq',
            'https://www.commcarehq.org',
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
        fail(f'--run-det export exited {result.returncode}: {output_text}')
        return
    import openpyxl

    workbook = openpyxl.load_workbook(output, read_only=True)
    rows = sum(1 for _ in workbook['cases'].iter_rows()) - 1
    ok(f'--run-det exported {rows} case(s) from corpora to Excel')


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


def query(db, sql, params=()):
    try:
        with sqlite3.connect(f'file:{db}?mode=ro', uri=True) as connection:
            connection.execute('PRAGMA busy_timeout = 2000')
            return connection.execute(sql, params).fetchall()
    except sqlite3.Error:
        return []


def processes_under(directory):
    directory = str(directory.resolve()).lower()
    found = []
    for process in psutil.process_iter(['pid', 'exe', 'cmdline']):
        exe = (process.info['exe'] or '').lower()
        if exe.startswith(directory):
            found.append(f'{process.info["pid"]} {process.info["cmdline"]}')
    return found


def check_server(exe, work):
    data_dir = work / 'data'
    data_dir.mkdir()
    port = free_port()
    url = f'http://127.0.0.1:{port}/'
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(('DJANGO', 'COMMCARE_SYNC'))
    }
    started = time.monotonic()
    process = subprocess.Popen(
        [exe, '--server', '--port', str(port), '--data-dir', str(data_dir)],
        env=env,
    )
    try:
        status = wait_for(
            lambda: process.poll() is None and http_status(url), START_TIMEOUT
        )
        if status in (200, 302):
            ok(
                f'/ answered {status} {time.monotonic() - started:.1f}s after launch'
            )
        elif process.poll() is not None:
            fail(
                f'the launcher exited with {process.returncode} before serving'
            )
            return
        else:
            fail(
                f'/ did not answer 200 or 302 within {START_TIMEOUT}s: {status}'
            )

        db = data_dir / 'db.sqlite3'
        schedules = query(
            db,
            'SELECT func FROM django_q_schedule WHERE func = ?',
            (DISPATCHER_FUNC,),
        )
        if schedules:
            ok('the dispatcher schedule exists')
        else:
            fail('no dispatcher schedule in the database')

        # A fresh database's schedule fires on the first tick.
        tasks = wait_for(
            lambda: query(
                db,
                'SELECT success FROM django_q_task WHERE func = ?',
                (DISPATCHER_FUNC,),
            ),
            TICK_TIMEOUT,
            interval=2,
        )
        if tasks and all(success for (success,) in tasks):
            ok(
                f'the dispatcher ran {time.monotonic() - started:.0f}s after launch'
            )
        elif tasks:
            fail(f'the dispatcher ran but failed: {tasks}')
        else:
            fail(f'the dispatcher did not run within {TICK_TIMEOUT}s')

        tree = psutil.Process(process.pid).children(recursive=True)
        if len(tree) >= 2:
            ok(f'the cluster is running: {len(tree)} descendant process(es)')
        else:
            fail(
                f'expected the cluster child and its workers, found {len(tree)}'
            )
        descendants = [(child.pid, child.create_time()) for child in tree]

        (data_dir / 'stop').touch()
        stopping = time.monotonic()
        try:
            process.wait(timeout=STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            fail(
                f'the launcher did not stop within {STOP_TIMEOUT}s of the stop file'
            )
            process.kill()
            process.wait()
        else:
            if process.returncode == 0:
                ok(
                    f'the launcher stopped {time.monotonic() - stopping:.1f}s after the stop file'
                )
            else:
                fail(
                    f'the launcher stopped with exit code {process.returncode}'
                )

        time.sleep(2)
        left = []
        for pid, create_time in descendants:
            try:
                child = psutil.Process(pid)
                if abs(child.create_time() - create_time) < 1:
                    left.append(f'{pid} {child.cmdline()}')
            except psutil.Error:
                pass
        left += processes_under(Path(exe).parent)
        if left:
            fail(f'process(es) left behind: {left}')
        else:
            ok('no process left behind')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

    with_tracebacks = [
        log.name
        for log in sorted((data_dir / 'logs').glob('*'))
        if 'Traceback' in log.read_text(encoding='utf-8', errors='replace')
    ]
    if with_tracebacks:
        fail(f'tracebacks in {with_tracebacks}')
    else:
        ok('no tracebacks in the logs')


def main():
    exe = Path(sys.argv[1]).resolve()  # the export runs elsewhere
    if not exe.is_file():
        print(f'No executable at {exe}')
        return 2
    work = Path(tempfile.mkdtemp(prefix='smoke-'))
    check_export_tool_help(exe, work)
    check_export(exe, work)
    check_server(exe, work)

    summary = '\n'.join(
        f'- {"OK" if passed else "FAIL"}: {message}'
        for passed, message in results
    )
    print('\n' + summary, flush=True)
    step_summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if step_summary:
        with open(step_summary, 'a', encoding='utf-8') as summary_file:
            summary_file.write(
                f'## Smoke test ({sys.platform})\n\n{summary}\n'
            )
    logs = os.environ.get('SMOKE_TEST_LOGS')
    if logs:
        import shutil

        shutil.copytree(work / 'data' / 'logs', logs, dirs_exist_ok=True)
    return 0 if all(passed for passed, _ in results) else 1


if __name__ == '__main__':
    sys.exit(main())
