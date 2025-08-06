# Waveform data ParaView reader

import logging
import time

import h5py
import numpy as np
import sxs
from paraview.util.vtkAlgorithm import smdomain, smhint, smproperty, smproxy
from paraview.vtk.util import keys as vtkkeys
from paraview.vtk.util import numpy_support as vtknp
from vtkmodules.numpy_interface import dataset_adapter as dsa
from vtkmodules.util.vtkAlgorithm import VTKPythonAlgorithmBase
from vtkmodules.vtkCommonDataModel import vtkTable

from gwpv.plugin_util.all_subfiles import all_subfiles

logger = logging.getLogger(__name__)


@smproxy.reader(
    name="WaveformDataReader",
    label="Waveform Data Reader",
    extensions="h5",
    file_description="HDF5 files",
)
class WaveformDataReader(VTKPythonAlgorithmBase):
    """Read waveform data from an HDF5 file.

    This plugin currently assumes the data in the 'Subfile' is stored in the
    SpEC waveform file format. It is documented in Appendix A.3.1 in the 2019
    SXS catalog paper (https://arxiv.org/abs/1904.04831). Specifically:

    - Each mode is stored in a dataset named 'Y_l{l}_m{m}.dat'. So the structure
      of the HDF5 file is:

        {FileName}/{Subfile}/Y_l{l}_m{m}.dat

      The subfile should contain at least the (2,2) mode (named Y_l2_m2.dat).
    - For a typical SpEC simulation you would read the modes from the
      'rhOverM_Asymptotic_GeometricUnits_CoM.h5' file and the
      'Extrapolated_N2.dir' subfile.
    - Each 'Y_l{l}_m{m}.dat' dataset has three columns:

        1. Time
        2. r * Re(h_lm)
        3. r * Im(h_lm)

      The 'Time' column should be the same for all datasets. It will only be
      read from the (2,2) mode dataset.
    """

    WAVEFORM_MODES_KEY = vtkkeys.MakeKey(
        vtkkeys.StringVectorKey, "WAVEFORM_MODES", "WaveformDataReader"
    )

    def __init__(self):
        VTKPythonAlgorithmBase.__init__(
            self, nInputPorts=0, nOutputPorts=1, outputType="vtkTable"
        )
        self._filename = None
        self._sxs_location = None
        self._subfile = None
        self.waveform_data = None
        self.mode_names = []

    @smproperty.stringvector(name="FileName")
    @smdomain.filelist()
    @smhint.filechooser(extensions="h5", file_description="HDF5 files")
    def SetFileName(self, value):
        self._filename = value
        self.Modified()

    @smproperty.stringvector(name="SxsLocation", number_of_elements="1")
    def SetSxsLocation(self, value):
        self._sxs_location = value
        self.Modified()

    @smproperty.stringvector(name="SubfileList", information_only="1")
    def GetSubfiles(self):
        if self._filename and self._filename != "None":
            with h5py.File(self._filename, "r") as open_h5file:
                return list(all_subfiles(open_h5file))
        else:
            return []

    @smproperty.stringvector(name="Subfile", number_of_elements="1")
    @smdomain.xml(
        """<StringListDomain name="list">
                <RequiredProperties>
                    <Property name="SubfileList" function="SubfileList"/>
                </RequiredProperties>
            </StringListDomain>
        """
    )
    def SetSubfile(self, value):
        if value == "None":
            self._subfile = None
        else:
            self._subfile = value
        self.Modified()

    def RequestInformation(self, request, inInfo, outInfo):
        logger.debug("Requesting information...")
        info = outInfo.GetInformationObject(0)
        # Add the modes provided by the data file to the information that
        # propagates down the pipeline. This allows subsequent filters to select
        # a subset of modes to display, for example.
        if self._filename is not None and self._subfile is not None:
            self.waveform_data = sxs.load(self._filename, group=self._subfile)
        elif self._sxs_location is not None:
            self.waveform_data = sxs.load(self._sxs_location, group=self._subfile)
            if isinstance(self.waveform_data, sxs.simulations.simulation.SimulationBase):
                self.waveform_data = self.waveform_data.h
        self.mode_names = [f"Y_l{l}_m{m}" for l, m in self.waveform_data.LM]
        if len(self.mode_names) == 0:
            logger.warning(
                "No waveform mode datasets found in file."
            )
        logger.debug("Set MODE_ARRAYS: {}".format(self.mode_names))
        info.Remove(WaveformDataReader.WAVEFORM_MODES_KEY)
        for mode_name in self.mode_names:
            info.Append(WaveformDataReader.WAVEFORM_MODES_KEY, mode_name)
        # Make the `WAVEFORM_MODES` propagate downstream.
        # TODO: This doesn't seem to be working...
        request.AppendUnique(
            self.GetExecutive().KEYS_TO_COPY(),
            WaveformDataReader.WAVEFORM_MODES_KEY,
        )
        logger.debug(f"Information object: {info}")
        return 1

    def RequestData(self, request, inInfo, outInfo):
        logger.info("Loading waveform data...")
        start_time = time.time()

        output = dsa.WrapDataObject(vtkTable.GetData(outInfo))

        if self.mode_names:
            # Read time
            col_time = vtknp.numpy_to_vtk(self.waveform_data.time, deep=False)
            col_time.SetName("Time")
            output.AddColumn(col_time)
            # Read modes
            for l, m in self.waveform_data.LM:
                mode_name = f"Y_l{l}_m{m}"
                logger.debug(f"Reading mode '{mode_name}'...")
                mode_data = self.waveform_data[
                    :, self.waveform_data.index(l, m)
                ]
                col_mode = vtknp.numpy_to_vtk(
                    np.array([np.real(mode_data), np.imag(mode_data)]).T
                )
                col_mode.SetName(mode_name)
                output.AddColumn(col_mode)

        logger.info(f"Waveform data loaded in {time.time() - start_time:.3f}s.")

        return 1
