"""Server version.

Single source of truth. `pyproject.toml` repeats it because the format
requires it, and a test checks that the two do not drift apart. The image
carries it as an OCI label.

The number follows SemVer: MAJOR.MINOR.PATCH. MAJOR goes up when
compatibility breaks (a tool changes its name, an environment variable
stops existing), MINOR when something is added, PATCH when something is
fixed.
"""

from __future__ import annotations

__version__ = "2.4.0"
