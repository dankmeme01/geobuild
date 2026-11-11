from pathlib import Path
import subprocess
import shutil

LAUNCHER_DIR = Path("/sdcard/Android/media/com.geode.launcher")
GEODE_DIR = LAUNCHER_DIR / "game" / "geode"
MODS_DIR = GEODE_DIR / "mods"

def _run_adb(args: list[str], check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
    adb_exe = Path(shutil.which("adb") or "adb")
    cmd = [str(adb_exe)] + args
    return subprocess.run(cmd, check=check, capture_output=capture_output, text=True)

def is_device_connected() -> bool:
    try:
        proc = _run_adb(["get-state"], check=False, capture_output=True)
        return proc.returncode == 0 and proc.stdout.strip() == "device"
    except FileNotFoundError:
        return False

def install(file: str | Path):
    file = Path(file)
    if not file.exists():
        raise FileNotFoundError(f"File {file} does not exist")
    elif not file.is_file():
        raise ValueError(f"Path {file} is not a file")

    dest = MODS_DIR / file.name
    proc = _run_adb(["push", str(file), str(dest)])
    print(proc.stdout)

def launch_game():
    _run_adb(["shell", "am", "force-stop", "com.geode.launcher"])
    _run_adb(["shell", "am", "start", "-n", "com.geode.launcher/com.geode.launcher.GeometryDashActivity"])
