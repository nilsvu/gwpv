# WaveformToVolume Paraview filter

# Load the `WaveformDataReader` to access its VTK keys
# sys.path.append(os.path.dirname(__file__))
# from WaveformDataReader import WaveformDataReader

import numpy as np
import logging
import time
from vtkmodules.vtkCommonDataModel import vtkUniformGrid
from vtkmodules.vtkCommonCore import vtkDataArraySelection
from vtkmodules.util.vtkAlgorithm import VTKPythonAlgorithmBase
from vtkmodules.numpy_interface import dataset_adapter as dsa
from paraview.util.vtkAlgorithm import smproxy, smproperty, smdomain
from paraview import util
from paraview.vtk.util import numpy_support as vtknp
import gwpv.plugin_util.timesteps as timesteps_util
import gwpv.plugin_util.data_array_selection as das_util
from gwpv import swsh_cache

logger = logging.getLogger(__name__)


def get_mode_name(l, abs_m):
    return "({}, {}) Mode".format(l, abs_m)


# Reproduces `spherical_functions.LM_index` so we don't need to import the
# `spherical_functions` module when using a cached SWSH grid
def LM_index(ell, m, ell_min):
    return ell * (ell + 1) - ell_min ** 2 + m


def smoothstep(x):
    return np.where(x < 0, 0, np.where(x <= 1, 3 * x**2 - 2 * x**3, 1))


def activation(x, width):
    return smoothstep(x / width)


def deactivation(x, width, outer):
    return smoothstep((outer - x) / width)


# Caching
# When using SwshGrid input this is not necessary anymore
# These are global variables because setting them on the filter object appears
# to trigger a "ModifiedEvent" so the data is recomputed.
_cached_swsh_grid = None
_cached_r = None
_cached_grid_id = None
def cached_swsh_grid(size, radial_scale, activation_offset, activation_width, deactivation_width, add_one_over_r_scaling, **swsh_grid_kwargs):
    global _cached_swsh_grid, _cached_r, _cached_grid_id
    grid_id = dict(size=size,
                   radial_scale=radial_scale,
                   activation_offset=activation_offset,
                   activation_width=activation_width,
                   deactivation_width=deactivation_width,
                   add_one_over_r_scaling=add_one_over_r_scaling)
    grid_id.update(swsh_grid_kwargs)
    if _cached_grid_id == grid_id:
        logger.debug("Using cached SWSHs grid from memory.")
        return _cached_swsh_grid, _cached_r
    else:
        logger.debug("No SWSH grid in memory, retrieving from disk cache.")
        swsh_grid, r = swsh_cache.cached_swsh_grid(size=size,
                                                   **swsh_grid_kwargs)
        # Apply screening
        screen = activation(r - activation_offset,
                            activation_width) * deactivation(
                                r, deactivation_width, size)
        swsh_grid *= screen.reshape(screen.shape + (1, ))
        # Apply radial scale
        r *= radial_scale
        if add_one_over_r_scaling:
            swsh_grid /= (r + 1.e-30).reshape(r.shape + (1,))
        # Cache and return
        _cached_swsh_grid = swsh_grid
        _cached_r = r
        _cached_grid_id = grid_id
        return swsh_grid, r


has_shown_warning_nonuniformly_sampled = False


@smproxy.filter(label="Waveform To Volume")
@smproperty.input(name="WaveformData", port_index=0)
@smdomain.datatype(dataTypes=["vtkTable"])
# TODO: We should be able to use a `SwshGrid` as a second input to this filter
# and use this class to compute the volume data for the waveform without having
# to generate the grid. Multiple inputs work fine, but for some reason
# `pv.LoadPlugin` doesn't load `SwshGrid`.
# @smproperty.input(name="GridData", port_index=1)
# @smdomain.datatype(dataTypes=["vtkUniformGrid"])
class WaveformToVolume(VTKPythonAlgorithmBase):
    def __init__(self):
        VTKPythonAlgorithmBase.__init__(
            self,
            # nInputPorts=2,
            nInputPorts=1,
            nOutputPorts=1,
            # Choosing `vtkUniformGrid` for the output for the following reasons:
            # - `vtkRectilinearGrid` doesn't support volume rendering
            #   (in Paraview v5.7.0 at least)
            # - The unstructured grids don't support the 'GPU Based'
            #   volume rendering mode, which can do shading and looks nice
            outputType='vtkUniformGrid')
        self.modes_selection = vtkDataArraySelection()
        # TODO: We should really retrieve the available modes from the input
        # info in `RequestInformation`, but the `WAVEFORM_MODES` keys is not
        # propagating downstream for some reason...
        # modes_arrays_key = WaveformDataReader.MODES_ARRAYS_KEY
        # if waveform_data_info.Has(modes_arrays_key):
        #     for i in range(waveform_data_info.Length(modes_arrays_key)):
        #         self.modes_selection.AddArray(waveform_data_info.Get(
        #             modes_arrays_key, i))
        for l in range(2, 5 + 1):
            for m in range(0, l + 1):
                self.modes_selection.AddArray(get_mode_name(l, m))
        self.modes_selection.AddObserver(
            "ModifiedEvent", das_util.create_modified_callback(self))
        self.polarizations_selection = vtkDataArraySelection()
        self.polarizations_selection.AddArray("Plus")
        self.polarizations_selection.AddArray("Cross")
        self.polarizations_selection.AddObserver(
            "ModifiedEvent", das_util.create_modified_callback(self))

    def FillInputPortInformation(self, port, info):
        # When using multiple inputs we (may) have to set their data types here
        # info.Set(self.INPUT_REQUIRED_DATA_TYPE(),
        #          'vtkTable' if port == 0 else 'vtkUniformGrid')
        info.Set(self.INPUT_REQUIRED_DATA_TYPE(), 'vtkTable')

    def _get_waveform_data(self):
        return dsa.WrapDataObject(self.GetInputDataObject(0, 0))

    # def _get_grid_data(self):
    #     return dsa.WrapDataObject(self.GetInputDataObject(1, 0))

    @smproperty.dataarrayselection(name="Modes")
    def GetModes(self):
        return self.modes_selection

    @smproperty.intvector(name="StoreIndividualModes", default_values=False)
    def SetStoreIndividualModes(self, value):
        self.store_individual_modes = value
        self.Modified()

    @smproperty.intvector(name="NormalizeEachMode", default_values=False)
    def SetNormalizeEachMode(self, value):
        self.normalize_each_mode = value
        self.Modified()

    @smproperty.dataarrayselection(name="Polarizations")
    def GetPolarizations(self):
        return self.polarizations_selection

    # Not needed when using SwshGrid input
    @smproperty.doublevector(name="Size", default_values=100)
    def SetSize(self, value):
        self.size = value
        self.Modified()

    # Not needed when using SwshGrid input
    @smproperty.intvector(name="SpatialResolution", default_values=100)
    def SetSpatialResolution(self, value):
        self.num_points_per_dim = value
        self.Modified()

    @smproperty.intvector(name="KeepEveryNthTimestep", default_values=1)
    def SetKeepEveryNthTimestep(self, value):
        self.keep_every_n_timestep = value
        self.Modified()

    # Not needed when using SwshGrid input
    @smproperty.intvector(name="EllMax", default_values=2)
    def SetEllMax(self, value):
        self.ell_max = value
        self.Modified()

    @smproperty.doublevector(name="RadialScale", default_values=10)
    def SetRadialScale(self, value):
        self.radial_scale = value
        self.Modified()

    @smproperty.intvector(name="ClipYNormal", default_values=False)
    @smdomain.xml('<BooleanDomain name="bool"/>')
    def SetClipYNormal(self, value):
        self.clip_y_normal = value
        self.Modified()

    @smproperty.intvector(name="ClipZNormal", default_values=False)
    @smdomain.xml('<BooleanDomain name="bool"/>')
    def SetClipZNormal(self, value):
        self.clip_z_normal = value
        self.Modified()

    @smproperty.intvector(name="OneOverRScaling", default_values=False)
    @smdomain.xml('<BooleanDomain name="bool"/>')
    def SetOneOverRScaling(self, value):
        self.add_one_over_r_scaling = value
        self.Modified()

    @smproperty.intvector(name="InvertRotationDirection", default_values=False)
    @smdomain.xml('<BooleanDomain name="bool"/>')
    def SetInvertRotationDirection(self, value):
        self.invert_rotation_direction = value
        self.Modified()

    @smproperty.doublevector(name="ActivationOffset", default_values=10)
    def SetActivationOffset(self, value):
        self.activation_offset = value
        self.Modified()

    @smproperty.doublevector(name="ActivationWidth", default_values=10)
    def SetActivationWidth(self, value):
        self.activation_width = value
        self.Modified()

    @smproperty.doublevector(name="DeactivationWidth", default_values=10)
    def SetDeactivationWidth(self, value):
        self.deactivation_width = value
        self.Modified()

    @smproperty.stringvector(name="SwshCacheDirectory", default_values="")
    def SetSwshCacheDirectory(self, value):
        self.swsh_cache_dir = value
        self.Modified()

    def _get_timesteps(self):
        logger.debug("Getting time range from data...")
        waveform_data = self._get_waveform_data()
        ts = waveform_data.RowData['Time']
        # Using a few timesteps within the data range so we can animate through
        # them in the GUI
        return np.linspace(ts[0], ts[-1], 100)

    @smproperty.doublevector(name="TimestepValues",
                             information_only="1",
                             si_class="vtkSITimeStepsProperty")
    def GetTimestepValues(self):
        return self._get_timesteps().tolist()

    def RequestInformation(self, request, inInfo, outInfo):
        logger.debug("Requesting information...")
        waveform_data_info = inInfo[0].GetInformationObject(0)
        # Careful with printing these information objects, their stream operator
        # may randomly crash...
        # logger.debug("Waveform data info: {}".format(waveform_data_info))
        # grid_info = inInfo[1].GetInformationObject(0)
        info = outInfo.GetInformationObject(0)

        # For the `vtkUniformGrid` output we need to provide extents
        # so that it gets rendered at all.
        # When using the SwshGrid input we can retrieve them from the
        # information object and pass them on.
        # grid_extents = grid_info.Get(self.GetExecutive().WHOLE_EXTENT())
        N = self.num_points_per_dim
        N_y = N // 2 if self.clip_y_normal else N
        N_z = N // 2 if self.clip_z_normal else N
        grid_extents = [0, N - 1, 0, N_y - 1, 0, N_z - 1]
        util.SetOutputWholeExtent(self, grid_extents)

        # This needs the time data from the waveform file, so we may have to
        # set the `TIME_RANGE` and `TIME_STEPS` already in the
        # WaveformDataReader.
        timesteps_util.set_timesteps(self,
                                     self._get_timesteps(),
                                     logger=logger)

        # logger.debug("Information object: {}".format(info))
        return 1

    def RequestData(self, request, inInfo, outInfo):
        logger.debug("Requesting data...")
        waveform_data = self._get_waveform_data()
        # grid_data = self._get_grid_data()
        output = dsa.WrapDataObject(vtkUniformGrid.GetData(outInfo))

        t = timesteps_util.get_timestep(self, logger=logger)
        N = self.num_points_per_dim
        D = self.size

        # We may have to forward the grid data here when using SwshGrid input
        # output.SetDimensions(*grid_data.GetDimensions())
        # output.SetOrigin(*grid_data.GetOrigin())
        # output.SetSpacing(*grid_data.GetSpacing())
        dx = 2. * D / N
        N_y = N // 2 if self.clip_y_normal else N
        N_z = N // 2 if self.clip_z_normal else N
        output.SetDimensions(N, N_y, N_z)
        output.SetOrigin(-D, -D, -D)
        output.SetSpacing(dx, dx, dx)

        # Compute the SWSHs on the grid
        # This section can be deleted when using SwshGrid input
        spin_weight = -2
        ell_max = self.ell_max
        swsh_grid, r = cached_swsh_grid(
            size=D,
            num_points=N,
            spin_weight=spin_weight,
            ell_max=ell_max,
            radial_scale=self.radial_scale,
            clip_y_normal=self.clip_y_normal,
            clip_z_normal=self.clip_z_normal,
            activation_offset=self.activation_offset,
            activation_width=self.activation_width,
            deactivation_width=self.deactivation_width,
            add_one_over_r_scaling=self.add_one_over_r_scaling,
            cache_dir=self.swsh_cache_dir)

        logger.info("Computing volume data at t={}...".format(t))
        start_time = time.time()

        # Compute scaled waveform phase on the grid
        # r = vtknp.vtk_to_numpy(grid_data.GetPointData()['RadialCoordinate'])
        phase = t - r

        # Invert rotation direction
        rotation_direction = -1. if self.invert_rotation_direction else 1.

        # Compute strain in the volume from the input waveform data
        skip_timesteps = self.keep_every_n_timestep
        waveform_timesteps = waveform_data.RowData['Time'][::skip_timesteps]
        strain = np.zeros(len(r), dtype=np.complex)
        # Optimization for when the waveform is sampled uniformly
        # TODO: Cache this
        
        # Here the analytical data gets recognized, by checking if the given data is simulation-data,
        # if not the program treats the data as analytical  created with creator.py
        if type(waveform_data.RowData['Y_l2_m2'][5]) is dsa.VTKNoneArray:

            indexx = list(map(abs, list(waveform_timesteps - t))).index(
                np.min(list(map(abs, list(waveform_timesteps - t)))))
            for i in range(1000):
                strain[i] = waveform_data.RowData['R Theta = ' + str(i) + 'Phi = ' + str(i)][indexx] + 1j * \
                            waveform_data.RowData['Im Theta = ' + str(i) + 'Phi = ' + str(i)][indexx]
        else:


            dt = np.diff(waveform_timesteps)
            waveform_uniformly_sampled = np.allclose(dt, dt[0])
            global has_shown_warning_nonuniformly_sampled
            if waveform_uniformly_sampled:
                dt = dt[0]
                logger.debug("Waveform sampled uniformly with dt={:.2e}, using optimized interpolation:".format(dt))
                waveform_start_time = waveform_timesteps[0]
                waveform_start_index = min(len(waveform_timesteps) - 2, max(
                    0, int(np.floor((np.min(phase) - waveform_start_time) / dt))))
                waveform_stop_index = max(waveform_start_index + 1, min(
                    len(waveform_timesteps),
                    int(np.ceil((np.max(phase) - waveform_start_time) / dt))))
                if waveform_stop_index == len(waveform_timesteps):
                    waveform_stop_index = -1
                logger.debug(
                    "Restricting interpolation to waveform indices {}, that's between waveform times {}. We will interpolate to times between {} (should be contained in restricted waveform range except for boundary effects)."
                    .format((waveform_start_index, waveform_stop_index),
                            (waveform_timesteps[waveform_start_index],
                             waveform_timesteps[waveform_stop_index]),
                            (np.min(phase), np.max(phase))))
                waveform_timesteps = waveform_timesteps[waveform_start_index:waveform_stop_index]
            elif not has_shown_warning_nonuniformly_sampled:
                logger.warning("Waveform is not sampled uniformly so interpolation is slightly more expensive.")
                has_shown_warning_nonuniformly_sampled = True
            # for i in range(self.modes_selection.GetNumberOfArrays()):
            #     mode_name = self.modes_selection.GetArrayName(i)
            for l in range(abs(spin_weight), ell_max + 1):
                for abs_m in range(0, l + 1):
                    mode_name = get_mode_name(l, abs_m)
                    strain_mode = np.zeros(len(r), dtype=np.complex)
                    if not self.modes_selection.ArrayIsEnabled(mode_name):
                        continue
                    for sign_m in (-1, 1):
                        m = abs_m * sign_m
                        dataset_name = "Y_l{}_m{}".format(l, m)
                        mode_profile = swsh_grid[:, LM_index(l, m, 0)]
                        # mode_profile = vtknp.vtk_to_numpy(grid_data.GetPointData()[dataset_name])
                        waveform_mode_data = waveform_data.RowData[dataset_name][::skip_timesteps]
                        if isinstance(waveform_mode_data, dsa.VTKNoneArray):
                            logger.warning(
                                "Dataset '{}' for mode {} not available in waveform data, skipping."
                                .format(dataset_name, (l, m)))
                            continue
                        # TODO: Make sure inverting the rotation direction like this
                        # is correct.
                        waveform_mode_data = waveform_mode_data[:, 0] + rotation_direction * 1j * waveform_mode_data[:, 1]
                        if self.normalize_each_mode:
                            waveform_mode_data /= np.max(np.abs(waveform_mode_data))
                        if waveform_uniformly_sampled:
                            waveform_mode_data = waveform_mode_data[waveform_start_index:waveform_stop_index]
                        mode_data = np.interp(phase,
                                              waveform_timesteps,
                                              waveform_mode_data,
                                              left=0.,
                                              right=0.)
                        strain_mode += mode_data * mode_profile
                    strain += strain_mode
                    # Expose individual modes in output
                    if self.store_individual_modes:
                        if self.polarizations_selection.ArrayIsEnabled("Plus"):
                            strain_mode_real_vtk = vtknp.numpy_to_vtk(
                                np.real(strain_mode), deep=True)
                            strain_mode_real_vtk.SetName(mode_name + ' Plus')
                            output.GetPointData().AddArray(strain_mode_real_vtk)
                        if self.polarizations_selection.ArrayIsEnabled("Cross"):
                            strain_mode_imag_vtk = vtknp.numpy_to_vtk(
                                np.imag(strain_mode), deep=True)
                            strain_mode_imag_vtk.SetName(mode_name + ' Cross')
                            output.GetPointData().AddArray(strain_mode_imag_vtk)
        if self.polarizations_selection.ArrayIsEnabled("Plus"):
            strain_real_vtk = vtknp.numpy_to_vtk(np.real(strain), deep=True)
            strain_real_vtk.SetName('Plus strain')
            output.GetPointData().AddArray(strain_real_vtk)
        if self.polarizations_selection.ArrayIsEnabled("Cross"):
            strain_imag_vtk = vtknp.numpy_to_vtk(np.imag(strain), deep=True)
            strain_imag_vtk.SetName('Cross strain')
            output.GetPointData().AddArray(strain_imag_vtk)

        logger.info("Volume data computed in {:.3f}s.".format(time.time() -
                                                              start_time))
        return 1
    
