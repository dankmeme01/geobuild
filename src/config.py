from pathlib import Path
from subprocess import Popen, PIPE, STDOUT
import argparse
import platform
import sys

from .error import fatal_error
from .platform import Platform

def parse_cmake_vars(s: str) -> dict[str, str]:
    s = s.strip(';')
    parts = s.split(";;")
    vars = {}

    for part in parts:
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        vars[key] = value

    return vars

class Config:
    vars: dict[str, str]

    def __init__(self) -> None:
        parser = argparse.ArgumentParser()
        # parser.add_argument("--cmake-vars", type=str, default="")
        args = parser.parse_args()

        # read vars from stdin
        stdin_data = sys.stdin.read()
        self.vars = parse_cmake_vars(stdin_data)

    def var(self, key: str, default: str = "") -> str:
        return self.vars.get(key, default)

    def var_require(self, key: str) -> str:
        if key not in self.vars:
            fatal_error(f"Required variable '{key}' was not set in CMake")

        return self.vars[key]

    def bool_var(self, key: str, default: bool = False) -> bool:
        val = self.var(key, "ON" if default else "OFF")
        return val.lower() in ("1", "true", "yes", "on", "y")

    @property
    def geode_sdk_path(self) -> Path:
        return Path(self.var_require("geode-sdk_SOURCE_DIR"))

    @property
    def project_name(self) -> str:
        return self.var_require("CMAKE_PROJECT_NAME")

    @property
    def project_version(self) -> str:
        return self.var_require("CMAKE_PROJECT_VERSION")

    @property
    def project_dir(self) -> Path:
        # return Path(self.var_require(f"{self.project_name}_SOURCE_DIR"))
        return Path(self.var_require("CMAKE_SOURCE_DIR"))

    @property
    def build_dir(self) -> Path:
        # return Path(self.var_require(f"{self.project_name}_BINARY_DIR"))
        return Path(self.var_require("CMAKE_BINARY_DIR"))

    @property
    def _geobuild_build_dir(self) -> Path:
        return Path(self.var_require("CMAKE_CURRENT_BINARY_DIR"))

    @property
    def compiler_id(self) -> str:
        return self.var_require("CMAKE_CXX_COMPILER_ID")

    @property
    def compiler_version(self) -> str:
        return self.var_require("CMAKE_CXX_COMPILER_VERSION")

    @property
    def compiler_frontend(self) -> str:
        return self.var_require("CMAKE_CXX_COMPILER_FRONTEND_VARIANT")

    @property
    def is_clang(self) -> bool:
        return "clang" in self.compiler_id.lower()

    @property
    def is_clang_cl(self) -> bool:
        return self.is_clang and self.compiler_frontend == "MSVC"

    @property
    def platform(self) -> Platform:
        return Platform.parse(self.var_require("GEODE_TARGET_PLATFORM"))

    @property
    def is_cpp20(self) -> bool:
        return int(self.var_require("CMAKE_CXX_STANDARD")) >= 20

    @property
    def is_cpp23(self) -> bool:
        return int(self.var_require("CMAKE_CXX_STANDARD")) >= 23

    @property
    def is_cpp26(self) -> bool:
        return int(self.var_require("CMAKE_CXX_STANDARD")) >= 26

    def invoke_git(self, where: Path, *args) -> tuple[int, str]:
        proc = Popen(["git", *args], cwd=where, stdout=PIPE, stderr=STDOUT)
        assert proc.stdout

        output = proc.stdout.read().decode().strip()
        code = proc.wait()

        return (code, output)

    def is_sdk_at_least(self, ver: str) -> bool:
        code, output = self.invoke_git(self.geode_sdk_path, "merge-base", "--is-ancestor", ver, "HEAD")

        if code == 0:
            return True
        else:
            print(output)
            return False

    def get_sdk_commit(self) -> str | None:
        code, output = self.invoke_git(self.geode_sdk_path, "rev-parse", "HEAD")

        if code != 0:
            # fatal_error(f"Failed to get Geode SDK commit:\n{output}")
            return None
        return output

    def get_sdk_commit_or_tag(self) -> str | None:
        # check if we are on a tag
        code, output = self.invoke_git(self.geode_sdk_path, "describe", "--tags", "--exact-match")

        if code == 0 and output:
            return output

        return self.get_sdk_commit()

    def get_sdk_version(self) -> str | None:
        # unlike the funcs below that check for git tags, we determine version by the VERSION file
        version_file = self.geode_sdk_path / "VERSION"
        if not version_file.exists():
            return None

        return version_file.read_text().strip()

    def get_mod_commit(self) -> str | None:
        code, output = self.invoke_git(self.project_dir, "rev-parse", "HEAD")

        if code != 0:
            return None
        return output

    def host_desc(self) -> str:
        if sys.platform == "linux":
            data = platform.freedesktop_os_release()
            name = data.get("PRETTY_NAME", None) or data.get("NAME", "Unknown Linux")
            return f"{name} ({platform.uname().machine})"
        elif sys.platform == "darwin":
            ver, _, machine = platform.mac_ver()
            return f"macOS {ver} ({machine})"
        elif sys.platform == "win32":
            ver = platform.version()
            arch = platform.machine()
            return f"Windows {ver} ({arch})"
        else:
            return f"Unknown"