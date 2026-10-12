"""
J.A.R.V.I.S. — Version and Release Metadata
Maintained by SudhirDevOps1
"""

__version__ = "0.2.0"
__app_name__ = "J.A.R.V.I.S."
__author__ = "SudhirDevOps1"
# GPL-3.0-only, because the GUI framework is PyQt6, which Riverbank
# distributes as GPL-3.0-only. This said "MIT" until the relicensing pass,
# which is exactly the kind of thing that survives in a metadata file nobody
# reads. A test asserts it agrees with LICENSE and pyproject.toml.
__license__ = "GPL-3.0-only"
__protocol__ = "DevOps"

def get_version() -> str:
    """Return the current semantic version string."""
    return __version__
