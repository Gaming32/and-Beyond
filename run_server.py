# pyright: reportUnusedImport=false
# The launching script needs to be Python 2.X compatible so that it can tell people to upgrade ;)
from __future__ import print_function

import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

if sys.version_info[0] > 2:
    from typing import List
    raw_input = input

missing_deps_text = ''
missing_deps = [] # type: List[str]

if sys.version_info[:2] < (3, 9):
    print('Python 3.9 or later is required to run this game.')
    raw_input('Press ENTER to exit...')
    sys.exit(1)

has_colorama = True
try:
    import colorama
except ModuleNotFoundError:
    has_colorama = False
if not has_colorama:
    missing_deps_text += ' - Colorama (colorama)\n'
    missing_deps.append('colorama')

has_aiofiles = True
try:
    import aiofiles
except ModuleNotFoundError:
    has_aiofiles = False
if not has_aiofiles:
    missing_deps_text += ' - Asynchronous files (aiofiles)\n'
    missing_deps.append('aiofiles')

has_opensimplex = True
try:
    import opensimplex
except ModuleNotFoundError:
    has_opensimplex = False
if not has_opensimplex:
    missing_deps_text += ' - OpenSimplex Noise (opensimplex)\n'
    missing_deps.append('opensimplex')

has_cryptography = True
try:
    import cryptography
except ModuleNotFoundError:
    has_cryptography = False
if not has_cryptography:
    missing_deps_text += ' - Cryptography (cryptography)\n'
    missing_deps.append('cryptography')

has_aiohttp = True
try:
    import aiohttp
except ModuleNotFoundError:
    has_aiohttp = False
if not has_aiohttp:
    missing_deps_text += ' - Asynchronous HTTP (aiohttp)\n'
    missing_deps.append('aiohttp')

has_humanize = True
try:
    import humanize
except ModuleNotFoundError:
    has_humanize = False
if not has_humanize:
    missing_deps_text += ' - Humanizer (humanize)\n'
    missing_deps.append('humanize')

has_typing_extensions_410 = True
try:
    from typing_extensions import Never, Self
except ImportError:
    has_typing_extensions_410 = False
if not has_typing_extensions_410:
    missing_deps_text += ' - typing_extensions 4.1.0 or later (typing_extensions>=4.1.0)\n'
    missing_deps.append('typing_extensions>=4.1.0')

if missing_deps:
    print('You appear to be missing the following requirements for this server to run:')
    print(missing_deps_text, end='')
    yes = input('Would you like to install them? [Y/n] ')
    if not yes or yes[0].lower() == 'y':
        args = [sys.executable, '-m', 'pip', 'install', '-U'] + missing_deps
        print(shlex.join(args))
        result = subprocess.run(args)
        if result.returncode != 0:
            print('Install failed with return code', result.returncode)
            sys.exit(1)
    else:
        print('Installation cancelled.')
        sys.exit(0)

GAME_DIR = Path(__file__).parent
if GAME_DIR.is_file() and os.path.splitext(GAME_DIR)[1].lower() == '.pyz':
    # Extract files from PYZ
    date_for_refresh = GAME_DIR.stat().st_mtime
    import zipfile
    with zipfile.ZipFile(GAME_DIR, 'r') as zfp:
        print('Extracting files from PYZ...')
        start = time.perf_counter()
        files_list = [
            f for f in zfp.namelist()
            if f.startswith('and_beyond/')
            if not os.path.exists(f) or os.path.getmtime(f) <= date_for_refresh
        ]
        zfp.extractall(members=files_list, path='.rundir')
        end = time.perf_counter()
        print('Extracted', len(files_list), 'files from PYZ in', end - start, 'seconds')
        if '--debug' in sys.argv:
            print('Extracted:', files_list)
    sys.path.insert(0, '.rundir')

from and_beyond.server.main import main
main()
