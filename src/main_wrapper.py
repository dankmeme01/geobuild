
import sys
import os
sys.path.append(os.path.dirname(__file__))

from pathlib import Path
import importlib.util
import traceback
import time

from .build import Build
from .error import GeobuildError, fatal_error
from . import prelude

def handle_fatal_exc(msg: str):
    print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print(f"!! Build halted due to error:")
    for line in msg.splitlines():
        print(f"!! {line}")
    print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", flush=True)
    exit(1)

def main():
    start_time = time.time()

    build = Build()
    scr_path = build.config.project_dir / "geobuild.py"

    if scr_path.is_file():
        # read and execute it
        spec = importlib.util.spec_from_file_location("_geobuild_inner", scr_path)
        assert spec is not None and spec.loader is not None

        module = importlib.util.module_from_spec(spec)
        for name, val in prelude.__dict__.items():
            if not name.startswith("__"):
                module.__dict__[name] = val

        sys.modules["_geobuild_inner"] = module
        spec.loader.exec_module(module)

        if hasattr(module, "main"):
            func = getattr(module, "main")
            if callable(func):
                func(build)

    build.finalize()

    print(f"Geobuild script completed in {time.time() - start_time:.3f}s!")


if __name__ == "__main__":
    try:
        main()
    except GeobuildError as e:
        handle_fatal_exc(str(e))
    except Exception as e:
        # print the full trace
        traceback.print_exc(file=sys.stdout)

        handle_fatal_exc(f"Unhandled exception: {str(e)}")