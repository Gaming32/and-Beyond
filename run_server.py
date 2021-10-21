# The launching script needs to be Python 2.X compatible so that it can tell people to upgrade ;)
from __future__ import print_function

import os
import shlex
import subprocess
import sys

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

from and_beyond.server.main import main
main()
