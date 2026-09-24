"""Точка входа самопроверки навыка: python scripts/self_check.py [корень]."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alice_skill.self_check import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))