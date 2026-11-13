"""Prints the release notes of one version as markdown: python tools/release_notes.py 1.3.1
With --versions it lists all versions that have notes."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smellyfish.changelog import CHANGELOG, markdown  # noqa: E402

if __name__ == "__main__":
    if "--versions" in sys.argv:
        print("\n".join(e["version"] for e in CHANGELOG))
    else:
        sys.stdout.write(markdown(sys.argv[1]) if len(sys.argv) > 1 else "")
