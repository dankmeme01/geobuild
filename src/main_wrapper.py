
import sys
import os
sys.path.append(os.path.dirname(__file__))

import traceback
import time

from .build import Build
from .error import GeobuildError, fatal_error
from .util import load_script_with_env, run_module_entry_point

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
        module = load_script_with_env(scr_path, "_geobuild_inner")
        run_module_entry_point(module, "main", build)

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