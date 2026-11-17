"""wesad/ conftest: adds wesad/ to sys.path so 'from src.checks.X import ...'
works when pytest is invoked from the project root as 'pytest wesad/tests/'."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
