import sys
from pathlib import Path

# Đảm bảo thư mục gốc của project nằm trong sys.path để pytest import được `app.*`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))