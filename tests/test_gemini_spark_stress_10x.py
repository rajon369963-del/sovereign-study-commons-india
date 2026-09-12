#!/usr/bin/env python3
"""Run the isolated 100-task synthesis/receipt stress test.

This proves queue and receipt behavior, not educational or physical verification.
All task files and the SQLite ledger live in pytest temporary directories.
"""
from pathlib import Path
import sys

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([str(Path(__file__).with_name("test_isolated_synthesis.py")), "-q"]))
