"""Allow ``python -m yt_dlp_gui``."""

import sys

from .app import main

if __name__ == "__main__":
    sys.exit(main())
