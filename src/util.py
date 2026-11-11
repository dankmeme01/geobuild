
from . import prelude
from pathlib import Path
import importlib.util
import sys

def load_script_with_env(path: str | Path, module_name: str) -> object:
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    for module_name, val in prelude.__dict__.items():
        if not module_name.startswith("__"):
            module.__dict__[module_name] = val

    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module

def run_module_entry_point(module: object, fname: str, *args, **kwargs) -> None:
    if hasattr(module, fname):
        func = getattr(module, fname)
        if callable(func):
            func(*args, **kwargs)