# SPDX-License-Identifier: Apache-2.0
"""Support `python -m commentdesk`, with the same exit codes as the script."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
