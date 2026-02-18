"""
Extract raw body state from qwop-python PhysicsWorld in qwop-wr observation format.

Delegates to src/observation for 1:1 match with reference.
"""

import sys
import os

_src = os.path.join(os.path.dirname(__file__), "..", "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from observation import extract_raw, OBS_PARTS

# Re-export for scripts that import from state_extractor
extract_state = extract_raw
