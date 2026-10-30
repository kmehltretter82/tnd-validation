#!/usr/bin/env python3
"""Apply resource limits before execing the trusted source parser.

This launcher limits one process tree's resource consumption; it is not a
filesystem, network, or privilege isolation boundary.
"""

from __future__ import annotations

import os
import resource
import sys

CPU_SECONDS = 60
# Lean reserves substantial virtual address space even for a tiny corpus.
# This caps virtual memory, not physical RSS; enforce a separate cgroup memory
# limit in the eventual production sandbox.
ADDRESS_SPACE_BYTES = 16 * 1024 * 1024 * 1024


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: limited.py EXECUTABLE [ARG ...]")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if sys.platform.startswith("linux"):
        resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS))
        resource.setrlimit(resource.RLIMIT_AS, (ADDRESS_SPACE_BYTES, ADDRESS_SPACE_BYTES))
    os.execv(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
