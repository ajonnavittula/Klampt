# Produces dependencies of Klampt
# Given KLAMPT_ROOT (optional)
# Produces
# - KLAMPT_LIBRARIES
# - KLAMPT_INCLUDE_DIRS
# - KLAMPT_DEFINITIONS
#

IF(NOT KLAMPT_ROOT)
  MESSAGE("KLAMPT_ROOT not defined, setting to .")
  SET(KLAMPT_ROOT .)
ELSE()
  MESSAGE("KLAMPT_ROOT set to ${KLAMPT_ROOT}")
ENDIF( )

SET(KLAMPT_CPP_ROOT ${KLAMPT_ROOT}/Cpp)
SET(KLAMPT_PYTHON_ROOT ${KLAMPT_ROOT}/Python)
SET(KLAMPT_DEPENDENCIES "${KLAMPT_CPP_ROOT}/Dependencies" CACHE PATH "Klamp't C++ dependency folder" FORCE)

#pick up stuff from KrisLibrary/CMakeModules
list(APPEND CMAKE_MODULE_PATH ${KLAMPT_DEPENDENCIES}/KrisLibrary/CMakeModules)

MESSAGE("Looking for Klampt dependencies in ${KLAMPT_DEPENDENCIES}")

IF(WIN32)
  SET(KRISLIBRARY_ROOT ${KLAMPT_DEPENDENCIES} CACHE PATH "KrisLibrary parent directory" FORCE)
  #some weird windows setting regarding QT
  if(POLICY CMP0020)
	cmake_policy(SET CMP0020 OLD)
  endif()
  
  IF(CMAKE_SIZEOF_VOID_P EQUAL 8)
    SET(KLAMPT_DEPENDENCY_LIB_DIR ${KLAMPT_DEPENDENCIES}/x64 CACHE PATH "Klamp't dependency folder for Windows libs")
  ELSE()
    SET(KLAMPT_DEPENDENCY_LIB_DIR ${KLAMPT_DEPENDENCIES} CACHE PATH "Klamp't dependency folder for Windows libs")
  ENDIF()
  
  SET(OPENGL_LIBRARY_DIR ${KLAMPT_DEPENDENCY_LIB_DIR})  #this is needed for glut32.lib / glui32.lib to be found in Cpp/Dependencies
  SET(GLEW_INCLUDE_DIR "${KLAMPT_DEPENDENCIES}/glew-2.0.0/include")
  SET(GLEW_LIBRARY "${KLAMPT_DEPENDENCY_LIB_DIR}/glew32.lib")

  SET(CURL_INCLUDE_DIR "${KLAMPT_DEPENDENCIES}/curl-7.64.1/include")
  SET(CURL_LIBRARY "${KLAMPT_DEPENDENCY_LIB_DIR}/libcurl.lib")
  
  FIND_PACKAGE(KrisLibrary REQUIRED)
  
  FIND_PATH(ODE_INCLUDE_DIR ode/ode.h
    PATHS ${KRISLIBRARY_ROOT}/ode-0.14/include  )
  FIND_LIBRARY(ODE_LIBRARY_DEBUG 
	NAMES ode_doubled
	PATHS ${KLAMPT_DEPENDENCY_LIB_DIR})
  FIND_LIBRARY(ODE_LIBRARY_RELEASE
	NAMES ode_double
	PATHS ${KLAMPT_DEPENDENCY_LIB_DIR})
  find_package_handle_standard_args(ODE
	DEFAULT_MSG
	ODE_INCLUDE_DIR
	ODE_LIBRARY_DEBUG
	ODE_LIBRARY_RELEASE)
  if(NOT ODE_FOUND)
    MESSAGE("ODE not found!")
  endif( )
  SET(ODE_DEFINITIONS "-DdDOUBLE" CACHE STRING "Open Dynamics Engine defines" FORCE)  
  SET(KLAMPT_DEFINITIONS ${KRISLIBRARY_DEFINITIONS} ${ODE_DEFINITIONS})
  SET(KLAMPT_LIBRARIES ${KRISLIBRARY_LIBRARIES} debug ${ODE_LIBRARY_DEBUG} optimized ${ODE_LIBRARY_RELEASE} )
  SET(KLAMPT_INCLUDE_DIRS  ${KRISLIBRARY_INCLUDE_DIRS} ${ODE_INCLUDE_DIR} )

ELSE(WIN32)

  SET(KRISLIBRARY_ROOT ${KLAMPT_DEPENDENCIES})
  FIND_PACKAGE(KrisLibrary REQUIRED)
  SET(KLAMPT_DEFINITIONS ${KRISLIBRARY_DEFINITIONS})
  SET(KLAMPT_INCLUDE_DIRS ${KRISLIBRARY_INCLUDE_DIRS})
  SET(KLAMPT_LIBRARIES ${KRISLIBRARY_LIBRARIES})

  # ODE
  SET(ODE_ROOT "${KLAMPT_DEPENDENCIES}/ode-0.14" CACHE PATH "Open Dynamics Engine path" FORCE)
  FIND_PACKAGE(ODE REQUIRED)
  IF(ODE_FOUND)
    MESSAGE("Open Dynamics Engine library found")
    MESSAGE("  Compiler definitions: ${ODE_DEFINITIONS}") 
    SET(KLAMPT_DEFINITIONS ${KLAMPT_DEFINITIONS} ${ODE_DEFINITIONS})
    SET(KLAMPT_INCLUDE_DIRS ${KLAMPT_INCLUDE_DIRS} ${ODE_INCLUDE_DIRS})
    SET(KLAMPT_LIBRARIES ${KLAMPT_LIBRARIES} ${ODE_LIBRARIES})

    #pthreads is needed -- but for some reason ODE does not report it
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pthread")
    FIND_LIBRARY(PTHREAD_LIBRARY "pthread")
    SET(KLAMPT_LIBRARIES ${KLAMPT_LIBRARIES} ${PTHREAD_LIBRARY})
  ENDIF(ODE_FOUND)

ENDIF(WIN32)

set(KLAMPT_ROS_VERSION "AUTO" CACHE STRING "Choose ROS integration (AUTO, ROS1, ROS2, NONE)")
set_property(CACHE KLAMPT_ROS_VERSION PROPERTY STRINGS AUTO ROS1 ROS2 NONE)
string(TOUPPER "${KLAMPT_ROS_VERSION}" KLAMPT_ROS_VERSION)
set(KLAMPT_SELECTED_ROS_VERSION "NONE")

if(KLAMPT_ROS_VERSION STREQUAL "ROS2" OR KLAMPT_ROS_VERSION STREQUAL "AUTO")
  find_package(rclcpp QUIET)
  if(rclcpp_FOUND)
    message("ROS 2 detected via rclcpp")
    find_package(std_msgs REQUIRED)
    find_package(geometry_msgs REQUIRED)
    find_package(sensor_msgs REQUIRED)
    find_package(trajectory_msgs REQUIRED)
    find_package(tf2 REQUIRED)
    find_package(tf2_ros REQUIRED)
    find_package(tf2_geometry_msgs REQUIRED)
    find_package(rosidl_typesupport_cpp REQUIRED)
    list(APPEND KLAMPT_INCLUDE_DIRS
      ${rclcpp_INCLUDE_DIRS}
      ${std_msgs_INCLUDE_DIRS}
      ${geometry_msgs_INCLUDE_DIRS}
      ${sensor_msgs_INCLUDE_DIRS}
      ${trajectory_msgs_INCLUDE_DIRS}
      ${tf2_INCLUDE_DIRS}
      ${tf2_ros_INCLUDE_DIRS}
      ${tf2_geometry_msgs_INCLUDE_DIRS})
    if(TARGET rclcpp::rclcpp)
      list(APPEND KLAMPT_LIBRARIES rclcpp::rclcpp)
    else()
      list(APPEND KLAMPT_LIBRARIES ${rclcpp_LIBRARIES})
    endif()
    foreach(_pkg
        builtin_interfaces
        std_msgs
        geometry_msgs
        sensor_msgs
        trajectory_msgs
        tf2
        tf2_ros
        tf2_geometry_msgs
        rosgraph_msgs
        statistics_msgs
        action_msgs
        unique_identifier_msgs
        rosidl_typesupport_cpp)
      if(TARGET ${_pkg}::${_pkg})
        list(APPEND KLAMPT_LIBRARIES ${_pkg}::${_pkg})
      endif()
      if(TARGET ${_pkg}::${_pkg}__rosidl_typesupport_cpp)
        list(APPEND KLAMPT_LIBRARIES ${_pkg}::${_pkg}__rosidl_typesupport_cpp)
      endif()
    endforeach()
    list(APPEND KLAMPT_DEFINITIONS "-DHAVE_ROS2=1")
    set(KLAMPT_SELECTED_ROS_VERSION "ROS2")
  elseif(KLAMPT_ROS_VERSION STREQUAL "ROS2")
    message(WARNING "KLAMPT_ROS_VERSION set to ROS2 but rclcpp was not found")
  endif()
endif()

if((KLAMPT_ROS_VERSION STREQUAL "ROS1" OR KLAMPT_ROS_VERSION STREQUAL "AUTO") AND
   KLAMPT_SELECTED_ROS_VERSION STREQUAL "NONE")
  SET(ROSDEPS tf rosconsole roscpp roscpp_serialization rostime )
  FIND_PACKAGE(ROS)
  IF(ROS_FOUND)
    MESSAGE("ROS 1 found, version " ${ROS_VERSION})
    LIST(APPEND KLAMPT_INCLUDE_DIRS ${ROS_INCLUDE_DIR})
    LIST(APPEND KLAMPT_LIBRARIES ${ROS_LIBRARIES})
    LIST(APPEND KLAMPT_DEFINITIONS "-DHAVE_ROS1=1")
    set(KLAMPT_SELECTED_ROS_VERSION "ROS1")
  ELSE(ROS_FOUND)
    IF(KLAMPT_ROS_VERSION STREQUAL "ROS1")
      MESSAGE(WARNING "KLAMPT_ROS_VERSION set to ROS1 but ROS was not found")
    ENDIF()
  ENDIF(ROS_FOUND)
endif()

if(KLAMPT_SELECTED_ROS_VERSION STREQUAL "NONE" AND NOT KLAMPT_ROS_VERSION STREQUAL "NONE")
  message(STATUS "ROS not found; building without ROS support")
endif()

LIST(REMOVE_DUPLICATES KLAMPT_INCLUDE_DIRS)
LIST(REMOVE_DUPLICATES KLAMPT_LIBRARIES)
