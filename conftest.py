import sys
from pathlib import Path

# Ensure workspace root is always on sys.path for test discovery and imports
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
