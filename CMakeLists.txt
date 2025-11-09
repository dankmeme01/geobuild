cmake_minimum_required(VERSION 3.21)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_VISIBILITY_PRESET hidden)

set(_vars_file "${CMAKE_CURRENT_BINARY_DIR}/_geobuild_vars.txt")
set(_user_script_file "${CMAKE_SOURCE_DIR}/geobuild.py")

find_package(Python3 REQUIRED)

# trick to reconfigure when user script changes
if (EXISTS ${_user_script_file})
    configure_file(${_user_script_file} ${CMAKE_CURRENT_BINARY_DIR}/user-geobuild.py COPYONLY)
endif()

# help with python intellisense, allow the user to import prelude easily
file(REMOVE_RECURSE "${CMAKE_BINARY_DIR}/geobuild")
file(COPY "${CMAKE_CURRENT_SOURCE_DIR}/src/" DESTINATION "${CMAKE_BINARY_DIR}/geobuild")

# get all cmake variables, write to a file and pass to the script
set(GEOBUILD_ALL_VARS "")
get_cmake_property(GEOBUILD__CACHE_VARS VARIABLES)

foreach(var ${GEOBUILD__CACHE_VARS})
    # skip some that really aren't needed
    if (var MATCHES "^^(ARGV|CMAKE_CXX11|CMAKE_CXX23|CMAKE_CXX_COMPILE_|CMAKE_C_COMPILE_|CMAKE_CXX_LINK|CMAKE_C_LINK|CMAKE_INSTALL|CMAKE_LINK|CMAKE_RC|existing_symlinks|__|_Python|Python)")
        continue()
    endif()

    list(APPEND GEOBUILD_ALL_VARS "${var}=${${var}};")
endforeach()

file(WRITE "${_vars_file}" "${GEOBUILD_ALL_VARS}")

execute_process(
    COMMAND ${Python3_EXECUTABLE} -m src.main_wrapper
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    INPUT_FILE "${_vars_file}"
    RESULT_VARIABLE GEOBUILD_RESULT
)

if (NOT GEOBUILD_RESULT EQUAL 0)
    message(FATAL_ERROR "Geobuild script failed with exit code ${GEOBUILD_RESULT}, see above for details")
endif()
