"""Makes both backend components importable from the repository root.

`gateway` is a package; the Flink job ships `domain.py` as a flat module via
`--pyFiles`, so it is imported by bare name both here and on the cluster.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
for path in (ROOT, os.path.join(ROOT, "account-service")):
    if path not in sys.path:
        sys.path.insert(0, path)
