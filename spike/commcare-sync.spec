# -*- mode: python ; coding: utf-8 -*-
"""Spike PyInstaller spec: a console --onedir build of the launcher.

Deliberately over-collects. The findings note says which of these were
actually needed so that P's spec can be trimmed.
"""

import os
import sys

from PyInstaller.utils.hooks import collect_all

# django_q.brokers reads Q_CLUSTER at import; without settings its
# submodules are not collected and the cluster fails to start.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'commcare_sync.settings')
os.environ.setdefault('SECRET_KEY', 'build-time-only')
os.environ.setdefault('FERNET_KEYS', '["build-time-only"]')

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

datas = [
    (os.path.join(ROOT, 'templates'), 'templates'),
    (os.path.join(ROOT, 'static'), 'static'),
]
binaries = []
# pyodbc is a single extension module, which collect_all() skips.
hiddenimports = ['django_q.brokers', 'django_q.brokers.orm', 'pyodbc']

PACKAGES = [
    'django',
    'apps',
    'commcare_sync',
    'django_q',
    'reversion',
    'anymail',
    'commcare_export',
    'db_query_fwd',
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
]
if sys.platform in ('win32', 'darwin'):
    PACKAGES.append('webview')

for package in PACKAGES:
    try:
        d, b, h = collect_all(package)
    except Exception as err:  # noqa: BLE001
        print(f'SPIKE: collect_all({package!r}) failed: {err!r}')
        continue
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [os.path.join(SPECPATH, 'entry.py')],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'pytest', 'playwright', 'IPython'],
    noarchive=False,
)
if sys.platform == 'darwin':
    # Both psycopg wheels ship a libpq.5.dylib under their own .dylibs
    # directory, and PyInstaller rewrites each extension to load
    # @rpath/libpq.5.dylib from the top level. Its dependency analysis
    # adds a top-level symbolic link of that name to whichever copy it
    # met first (a SYMLINK entry, kept in a.datas): psycopg2's, which is
    # older than the libpq psycopg 3's extension was built against. Point
    # the link at psycopg 3's copy instead, which psycopg2 runs against.
    for toc_name in ('binaries', 'datas'):
        for entry in getattr(a, toc_name):
            if 'libpq' in entry[0] or 'libpq' in entry[1]:
                print(f'SPIKE: {toc_name}', entry)
    a.datas = [
        entry
        for entry in a.datas
        if not (entry[2] == 'SYMLINK' and entry[0] == 'libpq.5.dylib')
    ]
    a.datas.append(
        ('libpq.5.dylib', 'psycopg_binary/.dylibs/libpq.5.dylib', 'SYMLINK')
    )

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='commcare-sync',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
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
