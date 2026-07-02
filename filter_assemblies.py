#!/usr/bin/env python
"""
Backward-compatible entry point for the genbargo embargo annotator.

The implementation now lives in ``genbargo/embargo.py``. This shim is kept so
that existing callers (e.g. the chrombase pipeline) can keep invoking
``python filter_assemblies.py -t <tsv> -c -p <prefix> -d <out>`` unchanged.
"""

import os
import sys

# Ensure the genbargo package (a sibling directory of this file) is importable
# even when this script is invoked by absolute path from another project.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from genbargo.embargo import main  # noqa: E402

if __name__ == "__main__":
    main()
