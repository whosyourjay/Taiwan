"""Puts the repository root on ``sys.path``.

``python3 pool/tiling.py`` puts pool/ on the path instead of the root, so
importing lib, parse or rank fails. Modules here import this first to undo that.
``python3 -m pool.tiling`` never reaches it.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
