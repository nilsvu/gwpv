# Waveform data ParaView reader
import numpy as np
import h5py
import logging
import time
from paraview.vtk.util import numpy_support as vtknp
from paraview.vtk.util import keys as vtkkeys
from paraview.util.vtkAlgorithm import smproxy, smproperty, smdomain, smhint
from vtkmodules.numpy_interface import dataset_adapter as dsa
from vtkmodules.util.vtkAlgorithm import VTKPythonAlgorithmBase
from vtkmodules.vtkCommonDataModel import vtkTable

logger = logging.getLogger(__name__)


@smproxy.reader(name="WaveformDataReader",
                label="Waveform Data Reader",
                extensions="h5",
                file_description="HDF5 files")
class WaveformDataReader(VTKPythonAlgorithmBase):
    WAVEFORM_MODES_KEY = vtkkeys.MakeKey(vtkkeys.StringVectorKey,
                                         "WAVEFORM_MODES",
                                         "WaveformDataReader")

    def __init__(self):
        VTKPythonAlgorithmBase.__init__(self,
                                        nInputPorts=0,
                                        nOutputPorts=1,
                                        outputType='vtkTable')
        self._filename = None
        self._subfile = None
        self.mode_names = []

    @smproperty.stringvector(name="FileName")
    @smdomain.filelist()
    @smhint.filechooser(extensions="h5", file_description="HDF5 files")
    def SetFileName(self, value):
        self._filename = value
        self.Modified()

    @smproperty.stringvector(name="Subfile",
                             default_values=['Extrapolated_N2.dir'])
    def SetSubfile(self, value):
        self._subfile = value
        self.Modified()

    def RequestInformation(self, request, inInfo, outInfo):
        logger.debug("Requesting information...")
        info = outInfo.GetInformationObject(0)
        # Add the modes provided by the data file to the information that
        # propagates down the pipeline. This allows subsequent filters to select
        # a subset of modes to display, for example.

        # check if analytical data was given
        if self._filename[-12:] == "analytics.h5":

            with h5py.File(self._filename, 'r') as f:
                self.mode_names = list(
                    map(
                        lambda dataset_name: dataset_name.replace('.dat', ''),
                        filter(
                            lambda dataset_name: dataset_name.startswith(
                                'Y_'), f[self._subfile].keys())))
            if len(self.mode_names) == 0:
                logger.warning(
                    "No waveform mode datasets (prefixed 'Y_') found in file '{}'."
                    .format(self._filename + ':' + 'self._subfile'))
            logger.debug("Set MODE_ARRAYS: {}".format(self.mode_names))
            info.Remove(WaveformDataReader.WAVEFORM_MODES_KEY)
            for mode_name in self.mode_names:
                info.Append(WaveformDataReader.WAVEFORM_MODES_KEY, mode_name)
            # Make the `WAVEFORM_MODES` propagate downstream.
            # TODO: This doesn't seem to be working...
            request.AppendUnique(self.GetExecutive().KEYS_TO_COPY(),
                                 WaveformDataReader.WAVEFORM_MODES_KEY)

        elif self._filename is not None and self._subfile is not None:

            with h5py.File(self._filename, 'r') as f:
                self.mode_names = list(
                    map(
                        lambda dataset_name: dataset_name.replace('.dat', ''),
                        filter(
                            lambda dataset_name: dataset_name.startswith(
                                'Y_'), f[self._subfile].keys())))
            if len(self.mode_names) == 0:
                logger.warning(
                    "No waveform mode datasets (prefixed 'Y_') found in file '{}'."
                    .format(self._filename + ':' + 'self._subfile'))
            logger.debug("Set MODE_ARRAYS: {}".format(self.mode_names))
            info.Remove(WaveformDataReader.WAVEFORM_MODES_KEY)
            for mode_name in self.mode_names:
                info.Append(WaveformDataReader.WAVEFORM_MODES_KEY, mode_name)
            # Make the `WAVEFORM_MODES` propagate downstream.
            # TODO: This doesn't seem to be working...
            request.AppendUnique(self.GetExecutive().KEYS_TO_COPY(),
                                 WaveformDataReader.WAVEFORM_MODES_KEY)
        logger.debug("Information object: {}".format(info))
        return 1

    def RequestData(self, request, inInfo, outInfo):
        logger.info("Loading waveform data...")
        start_time = time.time()

        output = dsa.WrapDataObject(vtkTable.GetData(outInfo))
        logger.warning(self._filename)

        # check if analytical data was given
        if self._filename[-12:] == "analytics.h5":

            with h5py.File(self._filename, 'r') as f:
                strain = f[self._subfile]
                t = np.real(strain['analytics'][1:, 0])
                col_time = vtknp.numpy_to_vtk(t, deep=False)
                col_time.SetName('Time')
                output.AddColumn(col_time)

                for i in range(1000):
                    col_mode = vtknp.numpy_to_vtk(np.real(strain['analytics'][1:, i]),
                                                  deep=False)
                    col_mode.SetName('R Theta = '+str(i) + 'Phi = '+str(i))
                    output.AddColumn(col_mode)

                for i in range(1000):
                    col_mode = vtknp.numpy_to_vtk(np.imag(strain['analytics'][1:, i]),
                                                  deep=False)
                    col_mode.SetName('Im Theta = '+str(i) + 'Phi = '+str(i))
                    output.AddColumn(col_mode)

        elif self._filename is not None and self._subfile is not None and len(
                self.mode_names) > 0:

            with h5py.File(self._filename, 'r') as f:
                strain = f[self._subfile]
                t = strain['Y_l2_m2.dat'][:, 0]
                col_time = vtknp.numpy_to_vtk(t, deep=False)
                col_time.SetName('Time')
                output.AddColumn(col_time)

                for mode_name in self.mode_names:
                    logger.debug("Reading mode '{}'...".format(mode_name))
                    col_mode = vtknp.numpy_to_vtk(strain[mode_name +
                                                         '.dat'][:, 1:],
                                                  deep=False)
                    col_mode.SetName(mode_name)
                    output.AddColumn(col_mode)

        logger.info("Waveform data loaded in {:.3f}s.".format(time.time() -
                                                              start_time))

        return 1
