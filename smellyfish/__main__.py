import os
import sys

if not __package__:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from smellyfish.app import main  # noqa: E402

sys.exit(main())
