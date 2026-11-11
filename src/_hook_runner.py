import sys

from pathlib import Path
from .util import load_script_with_env, run_module_entry_point
from .build import HookContext
from .config import Platform

hook_fn_name = sys.argv[1]
project_dir = Path(sys.argv[2])
build_dir = Path(sys.argv[3])
platform = Platform.parse(sys.argv[4])

ctx = HookContext(project_dir, build_dir, platform)

script = project_dir / "geobuild.py"
if not script.is_file():
    print(f"geobuild.py not found in {project_dir}")
    exit(1)

# read and execute it
module = load_script_with_env(script, "_geobuild_hooks")
run_module_entry_point(module, hook_fn_name, ctx)