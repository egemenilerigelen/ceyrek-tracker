"""Kurulum yapmadan çalıştırmak ve PyInstaller için başlatıcı.

Paket kuruluysa (`pip install -e .`) doğrudan `ceyrek-takip` ya da
`python -m ceyrek_tracker` da kullanılabilir.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ceyrek_tracker.app import main

if __name__ == "__main__":
    sys.exit(main())
