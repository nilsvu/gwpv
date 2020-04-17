# SwshGrid Paraview source

import numpy as np
import re
from vtkmodules.vtkCommonDataModel import vtkDataSet
from vtkmodules.util.vtkAlgorithm import VTKPythonAlgorithmBase
from vtkmodules.numpy_interface import dataset_adapter as dsa
from paraview.util.vtkAlgorithm import smproxy, smproperty
from paraview import util
from paraview.vtk.util import numpy_support as vtknp
import logging
logger = logging.getLogger(__name__)
import time

logger.info(
    "Loading spherical_functions module (compiling SWSHs with numba)...")
import spherical_functions as sf
import quaternion as qt
logger.info("Spherical_functions module loaded.")


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
        num_points_per_dim = self.num_points_per_dim
        size = self.size
        spacing = 2. * size / num_points_per_dim
        output.SetDimensions(*(3 * (num_points_per_dim, )))
        output.SetOrigin(*(3 * (-size, )))
        output.SetSpacing(*(3 * (spacing, )))
        X = np.linspace(-size, size, num_points_per_dim)
        x, y, z = map(
            lambda arr: arr.flatten(order='F'),
            np.meshgrid(*(3 * (X, )), indexing='ij', copy=False, sparse=False))
        r = np.sqrt(x**2 + y**2 + z**2)
        th = np.arccos(z / r)
        phi = np.arctan2(y, x)
        rotations = qt.from_spherical_coords(th, phi)

        # Expose radial coordinate to VTK
        r_vtk = vtknp.numpy_to_vtk(r, deep=False)
        r_vtk.SetName('RadialCoordinate')
        output.GetPointData().AddArray(r_vtk)

        # Compute the SWSHs on the grid
        spin_weight = self.spin_weight
        ell_max = self.ell_max
        swsh_grid = sf.SWSH_grid(rotations, s=spin_weight, ell_max=ell_max)
        for l, m in sf.LM_range(abs(spin_weight), ell_max):
            mode_profile = swsh_grid[:, sf.LM_index(l, m, 0)]
            mode_name = "Y_l{}_m{}".format(l, m)
            # Expose complex field to VTK as 2D array of floats
            mode_profile_as_floats = np.transpose(
                np.vstack((np.real(mode_profile), np.imag(mode_profile))))
            mode_vtk = vtknp.numpy_to_vtk(mode_profile_as_floats, deep=False)
            mode_vtk.SetName(mode_name)
            output.GetPointData().AddArray(mode_vtk)

        logger.info("SWSH grid computed in {:.3f}s.".format(time.time() -
                                                            start_time))
        return 1
