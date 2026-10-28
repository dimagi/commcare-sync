# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the desktop bundle: a windowed --onedir build of
the launcher, with the Data Export Tool and the SQL drivers inside.

    uv run pyinstaller --noconfirm packaging/commcare-sync.spec

Over-collects on purpose: collect_all() for each package proved to work
in the spike, and trimming costs a three-platform build per attempt.
"""

import importlib.util
import os
import sys

from PyInstaller.utils.hooks import collect_all

# django_q.brokers reads Q_CLUSTER at import, so the analysis needs
# loadable settings. Nothing from this environment reaches the bundle.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'commcare_sync.settings')
os.environ.setdefault('SECRET_KEY', 'build-time-only')
os.environ.setdefault('FERNET_KEYS', '["build-time-only"]')

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

# Packages whose data files, submodules or shared libraries the import
# analysis would miss: migrations, templates, static files, alembic's
# script templates, the drivers' bundled client libraries.
PACKAGES = [
    'django',
    'apps',
    'commcare_sync',
    'django_q',
    'reversion',
    'anymail',  # named only by the dotted string in EMAIL_BACKEND
    'commcare_export',
    'dqf',
    'whitenoise',
    'waitress',
    'platformdirs',
    'psutil',
    'sqlalchemy',
    'alembic',
    'psycopg',
    'psycopg2',
    'pymysql',
    'pyodbc',
    'openpyxl',
    'webview',  # Windows and macOS only
]

datas = [
    (os.path.join(ROOT, 'templates'), 'templates'),
    (os.path.join(ROOT, 'static'), 'static'),
]
binaries = []
# The brokers package is imported by name from Q_CLUSTER; pyodbc is a
# single extension module, which collect_all() skips.
hiddenimports = ['django_q.brokers', 'django_q.brokers.orm', 'pyodbc']

for package in PACKAGES:
    # Skipped when not installed: webview on Linux, pyodbc without the
    # odbc extra.
    if importlib.util.find_spec(package) is None:
        continue
    package_datas, package_binaries, package_hiddenimports = collect_all(
        package
    )
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

a = Analysis(
    [os.path.join(SPECPATH, 'entry.py')],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=['tkinter', 'pytest', 'playwright', 'IPython'],
)

if sys.platform == 'darwin':
    # Both psycopg wheels ship a libpq.5.dylib in their own .dylibs
    # directory, built against libpq 17 (psycopg2) and 18 (psycopg 3).
    # PyInstaller rewrites each extension to load @rpath/libpq.5.dylib
    # from the bundle's top level and adds one symbolic link there, to
    # whichever copy it met first: psycopg2's, which lacks a symbol
    # psycopg 3 needs. Point the link at psycopg 3's copy; psycopg2 runs
    # against the newer library.
    LIBPQ = 'libpq.5.dylib'
    a.datas = [
        entry
        for entry in a.datas
        if not (entry[2] == 'SYMLINK' and entry[0] == LIBPQ)
    ]
    a.datas.append((LIBPQ, f'psycopg_binary/.dylibs/{LIBPQ}', 'SYMLINK'))

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='commcare-sync',
    # No console: the launcher logs to the data directory when frozen.
    console=False,
    strip=False,
    upx=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='commcare-sync',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='CommCare Data Pipeline.app',
        icon=None,
        bundle_identifier='com.dimagi.commcare-sync',
    )
