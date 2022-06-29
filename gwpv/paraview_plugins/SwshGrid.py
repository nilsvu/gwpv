# SwshGrid Paraview source

import numpy as np
import re
from vtkmodules.vtkCommonDataModel import vtkDataSet
from vtkmodules.util.vtkAlgorithm import VTKPythonAlgorithmBase
from vtkmodules.numpy_interface import dataset_adapter as dsa
from paraview.util.vtkAlgorithm import smproxy, smproperty, smdomain
from paraview import util
from paraview.vtk.util import numpy_support as vtknp
import logging
logger = logging.getLogger(__name__)
import time
from gwpv import swsh_cache


# Reproduces `spherical_functions.LM_index` so we don't need to import the
# `spherical_functions` module when using a cached SWSH grid
def LM_index(ell, m, ell_min):
    return ell * (ell + 1) - ell_min ** 2 + m


@smproxy.source(name="SwshGrid", label="SWSH Grid")
class SwshGrid(VTKPythonAlgorithmBase):
    def __init__(self):
        VTKPythonAlgorithmBase.__init__(
            self,
            nInputPorts=0,
            nOutputPorts=1,
            # Choosing `vtkUniformGrid` output for the following reasons:
            # - `vtkRectilinearGrid` doesn't support volume rendering
            #   (in Paraview v5.7.0 at least)
            # - The unstructured grids don't support the 'GPU Based'
            #   volume rendering mode, which can do shading and looks nice
            outputType='vtkUniformGrid')

    @smproperty.intvector(name="SpinWeight", default_values=-2)
    def SetSpinWeight(self, value):
        self.spin_weight = value
        self.Modified()

    @smproperty.intvector(name="EllMax", default_values=2)
    def SetEllMax(self, value):
        self.ell_max = value
        self.Modified()

    @smproperty.doublevector(name="Size", default_values=10.)
    def SetSize(self, value):
        self.size = value
        self.Modified()

    @smproperty.intvector(name="SpatialResolution", default_values=100)
    def SetSpatialResolution(self, value):
        self.num_points_per_dim = value
        self.Modified()

    @smproperty.intvector(name="ClipYNormal", default_values=False)
    @smdomain.xml('<BooleanDomain name="bool"/>')
    def SetClipYNormal(self, value):
        self.clip_y_normal = value
        self.Modified()

    @smproperty.stringvector(name="SwshCacheDirectory", default_values="")
    def SetSwshCacheDirectory(self, value):
        self.swsh_cache_dir = value
        self.Modified()

    def RequestInformation(self, request, inInfo, outInfo):
        logger.debug("Requesting information...")
        # For the `vtkUniformGrid` output we need to provide extents
        # so that it gets rendered at all.
        N = self.num_points_per_dim
        util.SetOutputWholeExtent(self, [0, N - 1, 0, N - 1, 0, N - 1])
        logger.debug("Information object: {}".format(outInfo.GetInformationObject(0)))
        return 1

    def RequestData(self, request, inInfo, outInfo):
        logger.debug("Requesting data...")
        info = outInfo.GetInformationObject(0)
        logger.debug("Information object: {}".format(info))
        update_extents = info.Get(self.GetExecutive().UPDATE_EXTENT())
        logger.debug("Responsible for updating these extents: {}".format(
            update_extents))

        output = dsa.WrapDataObject(vtkDataSet.GetData(outInfo))

        logger.info("Computing SWSH grid...")
        start_time = time.time()

        # Setup grid
        # TODO: Take the `update_extents` into account to support rendering
        # in parallel
        N = self.num_points_per_dim
        N_y = N // 2 if self.clip_y_normal else N
        size = self.size
        spacing = 2. * size / N
        output.SetDimensions(N, N_y, N)
        output.SetOrigin(*(3 * (-size, )))
        output.SetSpacing(*(3 * (spacing, )))

        # Compute the SWSHs on the grid
        swsh_grid, r = swsh_cache.cached_swsh_grid(size=size,
                                                   num_points=N,
                                                   spin_weight=self.spin_weight,
                                                   ell_max=self.ell_max,
                                                   clip_y_normal=self.clip_y_normal,
                                                   clip_z_normal=False,
                                                   cache_dir=self.swsh_cache_dir)

        # Expose radial coordinate to VTK
        r_vtk = vtknp.numpy_to_vtk(r, deep=False)
        r_vtk.SetName('RadialCoordinate')
        output.GetPointData().AddArray(r_vtk)

        for l in range(abs(self.spin_weight), self.ell_max + 1):
            for m in range(1, l + 1):
                mode_profile = swsh_grid[:, LM_index(l, m, 0)] + swsh_grid[:, LM_index(l, -m, 0)]
                mode_name = "Y_l{}_m{}".format(l, m)
                # Expose complex field to VTK as two arrays of floats
                mode_real_vtk = vtknp.numpy_to_vtk(np.real(mode_profile), deep=True)
                mode_imag_vtk = vtknp.numpy_to_vtk(np.imag(mode_profile), deep=True)
                mode_abs_vtk = vtknp.numpy_to_vtk(np.abs(mode_profile), deep=True)
                mode_real_vtk.SetName(mode_name + " Real")
                mode_imag_vtk.SetName(mode_name + " Imag")
                mode_abs_vtk.SetName(mode_name + " Abs")
                output.GetPointData().AddArray(mode_real_vtk)
                output.GetPointData().AddArray(mode_imag_vtk)
                output.GetPointData().AddArray(mode_abs_vtk)

        logger.info("SWSH grid computed in {:.3f}s.".format(time.time() -
                                                            start_time))
        return 1
