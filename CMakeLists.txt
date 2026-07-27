cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)
project(DTIALPS)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/niyaziacer/SlicerDTIALPS")
set(EXTENSION_CATEGORY "Diffusion")
set(EXTENSION_CONTRIBUTORS "Niyazi Acer (Erciyes University)")
set(EXTENSION_DESCRIPTION "Automatically computes the DTI-ALPS (Diffusion Tensor Image Analysis along the Perivascular Space) index from DSI Studio QSDR output (tensor components + FA).")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/niyaziacer/SlicerDTIALPS/main/DTIALPS/Resources/Icons/DTIALPS.png")
set(EXTENSION_SCREENSHOTURLS "https://raw.githubusercontent.com/niyaziacer/SlicerDTIALPS/main/Screenshots/Screenshot1.png")
set(EXTENSION_DEPENDS "NA")

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(DTIALPS)

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
