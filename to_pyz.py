import zipfile
from pathlib import Path

from and_beyond.common import VERSION_NAME

DEST_FILENAME = f'and-Beyond-{VERSION_NAME}.pyz'

AND_BEYOND = Path('and_beyond')

with open(DEST_FILENAME, 'wb') as fp:
    print('Writing shebang')
    fp.write(b'#!/usr/bin/env python3.9\n')
    with zipfile.ZipFile(fp, 'w', zipfile.ZIP_DEFLATED) as zfp:
        for child in AND_BEYOND.rglob('*'):
            arcname = child.relative_to('.').as_posix()
            if child.parent.name == '__pycache__':
                print('Skipping', arcname)
                continue
            print('Writing', arcname)
            zfp.write(child, arcname)
        print('Writing __main__.py')
        zfp.write('run_game.py', '__main__.py')
