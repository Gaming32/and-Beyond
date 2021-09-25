import shlex
import subprocess
import sys
from typing import List

missing_deps_text = ''
missing_deps: List[str] = []

if sys.version_info[:2] < (3, 9):
    print('Python 3.9 or later is required to run this game.')
    sys.exit(1)

has_pygame_20 = True
try:
    import pygame
except ModuleNotFoundError:
    has_pygame_20 = False
else:
    import pygame.version
    if pygame.version.vernum[:2] < (2, 0):
        has_pygame_20 = False
if not has_pygame_20:
    missing_deps_text += ' - Pygame 2.0 or later (pygame>=2.0)\n'
    missing_deps.append('pygame>=2.0')

has_janus = True
try:
    import janus
except ModuleNotFoundError:
    has_janus = False
if not has_janus:
    missing_deps_text += ' - janus (janus)\n'
    missing_deps.append('janus')

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
    missing_deps_text += ' - aiofiles (aiofiles)\n'
    missing_deps.append('aiofiles')

has_opensimplex = True
try:
    import opensimplex
except ModuleNotFoundError:
    has_opensimplex = False
if not has_opensimplex:
    missing_deps_text += ' - OpenSimplex Noise (opensimplex)\n'
    missing_deps.append('opensimplex')

if missing_deps:
    print('You appear to be missing the following requirements for this game to run:')
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

import and_beyond.client.main
