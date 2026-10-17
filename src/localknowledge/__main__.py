"""Run private workers before loading CLI/Tkinter in a frozen executable."""
import sys
from .runtime import dispatch_private_worker

_worker_result = dispatch_private_worker(sys.argv[1:])
if _worker_result is not None:
    raise SystemExit(_worker_result)
from .cli import main
raise SystemExit(main())
