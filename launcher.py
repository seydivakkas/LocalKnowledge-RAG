"""PyInstaller script entry: package absolute imports work in frozen --onedir."""
from __future__ import annotations
import sys
from localknowledge.runtime import dispatch_private_worker


def main() -> int:
    status = dispatch_private_worker(sys.argv[1:])
    if status is not None:
        return status
    from localknowledge.cli import main as cli_main
    return int(cli_main())


if __name__ == '__main__':
    raise SystemExit(main())
