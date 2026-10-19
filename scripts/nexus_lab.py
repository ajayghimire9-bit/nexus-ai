"""Dependency-free local recorded-data launcher (Python >=3.11).

Fixtures remain disabled unless explicitly requested; no simulator backend.
"""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))

if __name__=='__main__':
    from run_learning_lab import main
    main()
