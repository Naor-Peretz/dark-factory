"""Make the Builder's checkout importable without living inside it.

The Verifier runs with cwd = workspace/repo and this directory supplied via add_dirs,
so `import app` must resolve against the working directory, not this file's parent.
"""

import os
import sys

sys.path.insert(0, os.getcwd())
