import asyncio
import logging
import sys

import colorama
from pw32.utils import init_logger


async def _main():
    logging.info('Starting server...')


def main():
    init_logger()
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    with colorama.colorama_text():
        asyncio.run(_main())


if __name__ == '__main__':
    main()
