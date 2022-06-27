import py_compile
import time
import zipfile
from pathlib import Path
from typing import Optional

from and_beyond.common import VERSION_DISPLAY_NAME

OUTPUT_DIR = Path('dist')
OUTPUT_DIR.mkdir(exist_ok=True)
DEST_FILE = OUTPUT_DIR / f'and-Beyond-{VERSION_DISPLAY_NAME}-server.pyz'

AND_BEYOND_DIR = Path('and_beyond')


def copy_to_zip(zfp: zipfile.ZipFile, file: Path, arcname: Optional[str] = None) -> None:
    global counter
    if arcname is None:
        arcname = file.relative_to('.').as_posix()
    print('Writing', arcname)
    zfp.write(file, arcname)
    counter += 1


start = time.perf_counter()
counter = 0

with open(DEST_FILE, 'wb') as fp:
    print('Writing shebang')
    fp.write(b'#!/usr/bin/env python3\n')

    with zipfile.ZipFile(fp, 'w', zipfile.ZIP_DEFLATED) as zfp:
        for child in AND_BEYOND_DIR.rglob('*'):
            rel = child.relative_to('.').as_posix()
            if '__pycache__' in (child.name, child.parent.name) or 'client' in child.parts:
                print('Skipping', rel)
                continue
            if child.is_dir():
                copy_to_zip(zfp, child, rel)
            else:
                print('Compiling', rel)
                child_name = str(child)
                child_name_pyc = child_name + 'c'
                py_compile.compile(child_name, child_name_pyc, str(rel))
                child_pyc = Path(child_name_pyc)
                pyc_rel = child_pyc.relative_to('.').as_posix()
                copy_to_zip(zfp, child_pyc, pyc_rel)
                print('Cleaning', pyc_rel)
                child_pyc.unlink()

        print('Writing __main__.py')
        zfp.write('run_server.py', '__main__.py')

        print('Writing LICENSE')
        zfp.write('LICENSE')

end = time.perf_counter()
print('Successfully zipped', counter, 'files in', end - start, 'seconds')
print('Result stored in', DEST_FILE)
