# Geobuild

Geobuild is a build system extension for [Geode](https://github.com/geode-sdk/geode) mods written in Python, allowing you to write configuration for your mod in that language as well.

## Why?

Beginners find CMake confusing and complicated. Experts find CMake even more confusing and complicated. Geobuild makes it possible to move most of your CMake configuration into a single Python file, making it easier to write and maintain. No need to deal with horrors of downloading files, parsing JSON or doing math expressions in CMake: simply do it all in Python!

Besides just making it simpler to write build configuration, Geobuild has some other features that make developing Geode mods a much nicer experience:

* Reduced CMakeLists.txt clutter
* Automatic checking for updates of Geode/CMake dependencies (disabled by default)
* Ability to generate the mod.json from a template and add custom things to it
* Allow you to run *whatever you want*. Whether it is generating some build configuration files, downloading binaries, this is not CMake so you are only limited by your imagination and PyPI :)

## Usage

Converting your mod to Geobuild is pretty simple if you don't do much advanced logic in your CMake file. For example, here's a complete [example mod CMakeLists.txt](https://github.com/geode-sdk/example-mod/blob/minimal/CMakeLists.txt) rewritten to use Geobuild:

```cmake
cmake_minimum_required(VERSION 3.21)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if ("${CMAKE_SYSTEM_NAME}" STREQUAL "iOS" OR IOS)
    set(CMAKE_OSX_ARCHITECTURES "arm64")
else()
    set(CMAKE_OSX_ARCHITECTURES "arm64;x86_64")
endif()
set(CMAKE_CXX_VISIBILITY_PRESET hidden)

project(Template VERSION 1.0.0)

if (NOT DEFINED ENV{GEODE_SDK})
    message(FATAL_ERROR "Unable to find Geode SDK! Please define GEODE_SDK environment variable to point to Geode")
else()
    message(STATUS "Found Geode: $ENV{GEODE_SDK}")
endif()

add_subdirectory($ENV{GEODE_SDK} ${CMAKE_CURRENT_BINARY_DIR}/geode)

CPMAddPackage("gh:dankmeme01/geobuild#main")
include("${CMAKE_CURRENT_BINARY_DIR}/geobuild-gen.cmake")
```

Few notes here:

* You **must** remove the `add_library` and `setup_geode_mod` lines, as well as globbing sources. These parts are handled by Geobuild.
* Including Geobuild must be after `add_subdirectory` is called with the path to Geode

This alone will be almost identical to the original example mod CMakeLists. Now, to actually modify the configuration, you will need to create a `geobuild.py` file at the root of your repository. Here's a simple quick start:

```py
# These lines are optional, but they will provide working Python intellisense,
# once you build your project at least once.
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .build.geobuild.prelude import *

def main(build: Build):
    build.add_source_dir("src/*.cpp")
```

## In-depth details

Here are some examples of what you can do with Geobuild:

Adding CMake options (like the `option()` command), setting variables:

```py
# add LTO on release builds, can be set via `-DRELEASE_BUILD=ON`
release = build.add_option("RELEASE_BUILD")
# add debug define and stuff
debug = build.add_option("DEBUG_BUILD")

if release:
    build.enable_lto()

if debug:
    build.add_definition("DEBUG_BUILD", "1")

build.set_variable("GEODE_DISABLE_PRECOMPILED_HEADERS", "ON") # or set_cache_variable
```

Check the host/target environment:

```py
host = build.config.host_desc()
target = build.platform

if target.is_apple():
    print("Stinky")

print(f"Building on {host} for {target}")

# Verify the Geode SDK version is new enough
# This can also be a commit hash, useful if your mod requires nightly
build.verify_sdk_at_least("v4.9.0")

# To manually throw in the towel, simply call fatal_error
if not build.config.is_clang:
    fatal_error("This mod requires clang to build")
```

Add compile definitions, source dirs, include dirs, compile options, link libraries:

```py
# Equivalent to target_compile_definitions(${PROJECT_NAME} PRIVATE MY_MACRO="123")
build.add_definition("MY_MACRO", "\"123\"")
# Privacy and target can be changed
build.add_definition("MY_MACRO", "\"123\"", privacy=Privacy.PUBLIC, target="geode")

# Source dirs may be either a Path or a string,
# if it doesn't end in a glob expression, multiple extensions will be globbed: .c, .cpp, .m, .mm
build.add_source_dir("src/*.cpp")
build.add_source_dir(build.config.project_dir / "external")
build.add_source_file("src/main.cpp")

# Add src/ as an include directory, allowing includes with angled (<...>) brackets
build.add_include_dir("src/")

# Make sure to check the compiler before using compiler options!
if build.config.compiler_frontend == "MSVC":
    build.add_compile_option("/w")
else:
    build.add_compile_option("-Wno-everything")

# (there is also a shorthand for disabling all warnings on a dependency)
build.silence_warnings_for("geode")

# link_library / link_libraries can be used to link any amount of libraries
if build.platform == Platform.Windows:
    build.link_libraries("ws2_32", "iphlapi", "kernel32")
elif build.platform.is_android():
    build.link_library("android")
```

Add CPM dependencies:
```py
# The gh: part is optional; this also can be a full URL
# This automatically links to the library as well.
build.add_cpm_dep("gh:GlobedGD/argon", "v1.2.0")

# If you want to add options to the library or if the library's target name
# is different from the repo name, use `link_name` and `options` params
build.add_cpm_dep("dankmeme01/qunet-cpp", "main",
    options={"QUNET_DEBUG": debug},
    link_name="qunet"
)
```

Add geode dependencies and codegen mod.json:

```py
# This code assumes there's a 'mod.json.template' file in the repository root.
# It is also possible to pass a dictionary with the contents of the mod JSON.
build.enable_mod_json_generation("mod.json.template")

# As an example, add a dependency only if a certain flag is set.
# This is something that would be very annoying to do with plain CMake,
# and Geobuild makes it very simple.
var = build.add_option("USE_ALPHAS_UTILS")
if var:
    build.add_definition("USE_ALPHAS_UTILS", "1")
    build.add_geode_dep("alphalaneous.alphas_geode_utils", ">=1.1.8")

# After Geobuild is done running, a mod.json will be generated in the repo root.
# Do not commit this! Add it to .gitignore and only commit the template file.
```

Update checks for CPM deps (requires the `requests` module to be installed)

```py
# You probably shouldn't forcibly do this every reconfiguration, but it is an option.
# Call this after all CPM dependencies have been added.
build.check_for_updates()

# Instead of manually calling this, you can set either the `GEOBUILD_UPDATE_CHECK` environment variable
# or the CMake flag `-DGEOBUILD_UPDATE_CHECK` to 'ON', and in that case,
# Geobuild will automatically check for updates every 24 hours.
```
