"""
Root conftest.py — makes the project root available as a package search path
so that `from src.checks.X import ...` works in tests without __init__.py files.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
