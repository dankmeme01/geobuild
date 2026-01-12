from pathlib import Path
from threading import Thread
from hashlib import sha256
import time
import json
import os

try:
    import requests
except ImportError:
    requests = None

from .config import Config
from .cmake import *
from .platform import Platform
from .error import fatal_error

class Build:
    def __init__(self) -> None:
        self.finalized = False
        self.checked_updates = False
        self.mod_json = None
        self.config = Config()
        self._cmake = CMakeFile(self.config)

    def _to_path(self, p: Path | str) -> Path:
        if not isinstance(p, Path):
            p = self.config.project_dir / p

        return p.resolve()

    @property
    def platform(self) -> Platform:
        return self.config.platform

    def add_option(self, name: str, default: bool = False, desc: str = "") -> bool:
        self._cmake.options.append(CMakeOption(name, default, desc))
        return self.config.bool_var(name, default)

    def message(self, msg: str):
        self._cmake.messages.append(msg)

    def set_variable(self, key: str, value: str):
        self._cmake.vars[key] = value

    def set_cache_variable(self, key: str, value: str, type: str = "STRING", force: bool = False, desc: str = ""):
        """Sets a CMake cache variable, akin to a set(... CACHE ...) call in CMake."""
        self._cmake.cache_vars[key] = CMakeCacheVariable(key, value, type, force, desc)

    def add_definition(self, key: str, value: str = "", privacy: Privacy = Privacy.PRIVATE, target: str | None = None):
        """Adds a compile definition to the given target, akin to a #define statement or a target_compile_definitions call in CMake.
           If the target is None, ${PROJECT_NAME} is assumed."""

        self._cmake.defs[key] = CMakeDefinition(key, value, target, privacy)

    def link_library(self, name: str | Path, privacy: Privacy = Privacy.PRIVATE, target: str | None = None):
        """Links a single library to the given target. If the target is None, ${PROJECT_NAME} is assumed."""
        self._cmake.libraries.append(CMakeLibrary(name, privacy, target))

    def link_libraries(self, *names: str | Path, privacy: Privacy = Privacy.PRIVATE, target: str | None = None):
        """Links multiple libraries to the given target. If the target is None, ${PROJECT_NAME} is assumed."""
        for name in names:
            self._cmake.libraries.append(CMakeLibrary(name, privacy, target))

    def add_source_dir(self, path: Path | str, recursive: bool = True):
        """Adds all source files in the given directory as source files to the build, using CMake glob.
           It's advised that the path ends in '*.cpp' or similar, otherwise multiple extensions will be globbed: .c, .cpp, .m, .mm"""

        path = self._to_path(path)

        if not path.is_dir() and '*' in path.name:
            if not path.parent.exists():
                raise FileNotFoundError(f"Source directory {path.parent} does not exist")

            self._cmake.glob_dirs.add((path, recursive))
            if path.name.endswith(('.mm', '.m')):
                for source_file in path.parent.glob(path.name):
                    self._cmake.raw_statements.append(f"set_source_files_properties({source_file} PROPERTIES SKIP_PRECOMPILE_HEADERS ON)")
        else:
            self.add_source_dir(path / "*.c", recursive)
            self.add_source_dir(path / "*.cpp", recursive)
            if self.platform.is_apple():
                self.add_source_dir(path / "*.m", recursive)
                self.add_source_dir(path / "*.mm", recursive)

    def add_source_file(self, path: Path | str):
        self._cmake.source_files.add(self._to_path(path))

    def add_include_dir(self, path: Path | str, privacy: Privacy = Privacy.PRIVATE, target: str | None = None):
        self._cmake.include_dirs.append(CMakeIncludeDir(self._to_path(path), privacy, target))

    def add_compile_option(self, option: str, privacy: Privacy = Privacy.PRIVATE, target: str | None = None):
        self._cmake.compile_options.append(CMakeCompileOption(option, privacy, target))

    def add_compile_options(self, *option: str, privacy: Privacy = Privacy.PRIVATE, target: str | None = None):
        for opt in option:
            self.add_compile_option(opt, privacy, target)

    def add_link_option(self, option: str, privacy: Privacy = Privacy.PRIVATE, target: str | None = None):
        self._cmake.link_options.append(CMakeLinkOption(option, privacy, target))

    def add_link_options(self, *option: str, privacy: Privacy = Privacy.PRIVATE, target: str | None = None):
        for opt in option:
            self.add_link_option(opt, privacy, target)

    def add_precompile_headers(self, *headers: Path | str, privacy: Privacy = Privacy.PRIVATE, target: str | None = None):
        self._cmake.pch.append(CMakePCH(list(headers), privacy, target))

    def add_cpm_dep(
        self,
        repo: str,
        tag: str,
        options: dict | None = None,
        name: str | None = None,
        link_name: str | None = None,
        privacy: Privacy = Privacy.PRIVATE,
    ):
        if options is None:
            options = {}

        if repo.startswith("gh:"):
            repo = repo[3:]

        if repo.count('/') == 1:
            repo = f"https://github.com/{repo}.git"

        if name is None:
            # try to get from url
            name = repo.split('/')[-1]
            if name.endswith(".git"):
                name = name[:-4]

        self._cmake.deps.append(CPMDep(name, repo, tag, options, privacy))
        self.link_library(link_name or name, privacy)

    def add_raw_statement(self, statement: str):
        self._cmake.raw_statements.append(statement)

    def enable_lto(self):
        self.set_variable("CMAKE_INTERPROCEDURAL_OPTIMIZATION", "ON")

    def silence_warnings_for(self, lib: str):
        opt = "/w" if self.config.is_clang_cl else "-w"
        self.add_compile_option(opt, Privacy.PRIVATE, lib)

    def enable_mod_json_generation(self, template: str | Path | dict):
        if isinstance(template, dict):
            self.mod_json = template
        else:
            path = self._to_path(template)
            self.mod_json = json.loads(path.read_text())
            self.reconfigure_if_changed(path)

        if not self.mod_json:
            fatal_error("Mod JSON template is empty")

    def reconfigure_if_changed(self, path: Path | str):
        path = self._to_path(path)
        if not path.exists():
            return

        uid = sha256(str(path).encode()).hexdigest()[:16]
        dest_path = self.config._geobuild_build_dir / f"_geobuild-reconfigure-{uid}"

        self._cmake.configures.add(CMakeConfigure(
            path=path,
            dest_path=dest_path,
            copyonly=True
        ))

    def add_geode_dep(self, mod_id: str, version_or_spec: str | dict):
        if not self.mod_json:
            fatal_error("Cannot call add_geode_dep when before enabling mod.json generation")

        assert self.mod_json and "dependencies" in self.mod_json
        deps = self.mod_json["dependencies"]

        deps[mod_id] = version_or_spec

    def verify_sdk_at_least(self, tag_or_commit: str):
        """Verifies that the installed Geode SDK is newer or equal to the given tag or commit hash."""

        if not self.config.is_sdk_at_least(tag_or_commit):
            msg = "Geode version mismatch! Please update Geode SDK to build this mod.\n"
            if 'v' in tag_or_commit or '.' in tag_or_commit:
                msg += f"Required Geode version: {tag_or_commit}\n"
            else:
                msg += f"Geode nightly is required (at least commit {tag_or_commit}), run `geode sdk update nightly`\n"

            msg += f"Current Geode version: {self.config.get_sdk_commit_or_tag() or 'unknown'}\n"

            fatal_error(msg)

    def finalize(self):
        if self.finalized:
            return

        self.finalized = True

        # check if any source dirs exist, otherwise add a default one
        if not self._cmake.glob_dirs and not self._cmake.source_files:
            default_src = self.config.project_dir / "src"
            self.add_source_dir(default_src, recursive=True)

        self._cmake.save(self.config.build_dir / "geobuild-gen.cmake")

        # save mod json, if applicable
        if self.mod_json:
            path = self.config.project_dir / "mod.json"
            path.write_text(json.dumps(self.mod_json, indent=4))

        # determine if we should check for updates using the last update file & env var
        do_check = truthy(self.config.var("GEOBUILD_UPDATE_CHECK", os.environ.get("GEOBUILD_UPDATE_CHECK", "0")))
        if do_check:
            p = Path(self.config.build_dir / "_geobuild-last-update.txt")
            if not p.exists() or (time.time() - p.stat().st_mtime) > 60 * 60 * 24:
                if self.check_for_updates():
                    p.touch(exist_ok=True)

    # Auto update stuff

    def _gh_request(self, url: str):
        assert requests

        headers = {}
        # check for github token
        gh_token = self.config.var("GITHUB_TOKEN", os.environ.get("GITHUB_TOKEN") or "").strip()
        if gh_token:
            headers["Authorization"] = f"Bearer {gh_token}"

        r = requests.get(url, headers=headers)

        if not r.ok:
            print(f"Request for {url} failed: {r.status_code} {r.reason}")
            return None

        return r.json()

    def get_last_gh_release(self, repo: str) -> str | None:
        assert requests

        url = repo.replace(".git", "").replace("github.com", "api.github.com/repos") + "/tags"
        tags = self._gh_request(url)

        if not isinstance(tags, list) or len(tags) == 0:
            print(f"No tags found for {repo}")
            return None

        return tags[0]["name"]

    def get_last_gh_commit(self, repo: str) -> str | None:
        assert requests

        url = repo.replace(".git", "").replace("github.com", "api.github.com/repos") + "/commits"
        commits = self._gh_request(url)

        if not isinstance(commits, list) or len(commits) == 0:
            print(f"No commits found for {repo}")
            return None

        return commits[0]["sha"]

    def check_for_updates(self) -> bool:
        if not requests:
            print("WARN: requests module not found, cannot check for updates.")
            return False

        if self.checked_updates:
            return False

        self.checked_updates = True

        start_time = time.time()
        print(f"Checking for CPM/Geode dep updates...")

        threads = []

        def do_fetch(dep: CPMDep):
            use_tag = '.' in dep.tag or 'v' in dep.tag

            if use_tag:
                tag = self.get_last_gh_release(dep.repo)
                if not tag:
                    print(f"Failed to fetch latest release for {dep.repo}")
                    return

                current, latest = dep.tag, tag
            else:
                commit = self.get_last_gh_commit(dep.repo)
                if not commit:
                    print(f"Failed to fetch latest commit for {dep.repo}")
                    return

                shortest_len = min(len(dep.tag), len(commit))

                current, latest = dep.tag[:shortest_len], commit[:shortest_len]

            if current != latest:
                print(f"Update available for {dep.name}: {current} -> {latest}")
            else:
                print(f"{dep.name} is up to date ({latest})")

        for dep in self._cmake.deps:
            threads.append(Thread(target=do_fetch, args=(dep,)))

        # check for a geobuild update, for this we have to find what version of geobuild the user has right now
        if dep := self._make_self_dependency():
            threads.append(Thread(target=do_fetch, args=(dep,)))

        [t.start() for t in threads]
        [t.join() for t in threads]

        print(f"Update check complete in {time.time() - start_time:.3f}s")

        return True

    def _make_self_dependency(self) -> CPMDep | None:
        cmake = (self.config.project_dir / "CMakeLists.txt").read_text()

        version = None

        if "dankmeme01/geobuild" in cmake:
            remainder = cmake[cmake.index("dankmeme01/geobuild") + len("dankmeme01/geobuild") + 1:]
            ver = remainder.partition('"')[0]
            if ver:
                version = ver.strip()

        if not version:
            return None

        return CPMDep(
            "geobuild",
            "https://github.com/dankmeme01/geobuild",
            version,
            {},
            Privacy.PRIVATE,
        )

