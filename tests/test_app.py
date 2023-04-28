import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import app

# Your test code goes here


def test_addition():
    assert 1 + 1 == 2


def test_subtraction():
    assert 5 - 3 == 2
