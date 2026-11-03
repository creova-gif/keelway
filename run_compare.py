#!/usr/bin/env python3
"""
Keelway Evaluation Runner Entrypoint.
Delegates to evaluations/run_compare.py.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from evaluations.run_compare import main

if __name__ == "__main__":
    main()
