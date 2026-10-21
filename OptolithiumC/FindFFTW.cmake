  # - Find FFTW
  # Find the native FFTW includes and library
  #
  # FFTW_INCLUDES - where to find fftw3.h
  # FFTW_LIBRARIES - List of libraries when using FFTW.
  # FFTW_FOUND - True if FFTW found.
  if (FFTW_INCLUDES)
      # Already in cache, be silent
      set (FFTW_FIND_QUIETLY TRUE )
  endif (FFTW_INCLUDES)

  # On Linux distributions usually ship only the shared runtime (libfftw3.so.3)
  # without the development headers. Allow a local prefix to provide them:
  #   cmake -DFFTW_ROOT=/path/to/prefix ...
  # The prefix must contain include/fftw3.h and lib/libfftw3.so.
  if (NOT FFTW_ROOT)
      set (FFTW_ROOT "$ENV{FFTW_ROOT}" CACHE PATH "Root of a local FFTW installation prefix")
  endif (NOT FFTW_ROOT)

  find_path (FFTW_INCLUDES fftw3.h
      HINTS
          "${FFTW_ROOT}/include"
          "$ENV{FFTW_ROOT}/include"
      PATHS
          "${CMAKE_CURRENT_SOURCE_DIR}/libs/fftw3-win32"
          /usr/local/include
          /usr/include
      NO_DEFAULT_PATH)
  if (NOT FFTW_INCLUDES)
      find_path (FFTW_INCLUDES fftw3.h
          HINTS
              "${FFTW_ROOT}/include"
              "$ENV{FFTW_ROOT}/include"
          PATHS
              "${CMAKE_CURRENT_SOURCE_DIR}/libs/fftw3-win32"
              /usr/local/include
              /usr/include)
  endif (NOT FFTW_INCLUDES)

  find_library (FFTW_LIBRARIES NAMES fftw3 libfftw3.so.3 libfftw3.so fftw3-3
      HINTS
          "${FFTW_ROOT}/lib"
          "$ENV{FFTW_ROOT}/lib"
      PATHS
          /usr/local/lib
          /usr/lib64
          /usr/lib
      NO_DEFAULT_PATH)
  if (NOT FFTW_LIBRARIES)
      find_library (FFTW_LIBRARIES NAMES fftw3 libfftw3.so.3 libfftw3.so fftw3-3
          HINTS
              "${FFTW_ROOT}/lib"
              "$ENV{FFTW_ROOT}/lib"
          PATHS
              /usr/local/lib
              /usr/lib64
              /usr/lib)
  endif (NOT FFTW_LIBRARIES)

  # handle the QUIETLY and REQUIRED arguments and set FFTW_FOUND to TRUE if
  # all listed variables are TRUE
  include (FindPackageHandleStandardArgs)
  find_package_handle_standard_args (FFTW DEFAULT_MSG FFTW_LIBRARIES FFTW_INCLUDES)
  mark_as_advanced (FFTW_LIBRARIES FFTW_INCLUDES FFTW_ROOT)
