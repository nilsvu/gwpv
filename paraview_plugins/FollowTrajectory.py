# Follow Trajectory Paraview filter

import numpy as np
from vtkmodules.vtkCommonDataModel import vtkPolyData
from vtkmodules.util.vtkAlgorithm import VTKPythonAlgorithmBase
from vtkmodules.numpy_interface import dataset_adapter as dsa
from paraview.util.vtkAlgorithm import smproxy, smproperty, smdomain
from paraview.vtk.util import numpy_support as vtknp
from paraview import vtk
import gwpv.plugin_util.timesteps as timesteps_util
import logging
import itertools

logger = logging.getLogger(__name__)


@smproxy.filter(label="Follow Trajectory")
@smproperty.input(name="TrajectoryData", port_index=0)
@smdomain.datatype(dataTypes=["vtkPolyData"])
class FollowTrajectory(VTKPythonAlgorithmBase):
    def __init__(self):
        VTKPythonAlgorithmBase.__init__(self,
                                        nInputPorts=1,
                                        nOutputPorts=1,
                                        outputType='vtkPolyData')

    def FillInputPortInformation(self, port, info):
        info.Set(self.INPUT_REQUIRED_DATA_TYPE(), 'vtkPolyData')

    def _get_trajectory_data(self):
        return dsa.WrapDataObject(self.GetInputDataObject(0, 0))

    def _get_timesteps(self):
        logger.debug("Getting time range from data...")
        trajectory_data = self._get_trajectory_data()
        point_times = trajectory_data.PointData['Time']
        # Using a few timesteps within the data range so we can animate through
        # them in the GUI
        return np.linspace(point_times[0], point_times[-1], 100)

    @smproperty.doublevector(name="TimestepValues",
                             information_only="1",
                             si_class="vtkSITimeStepsProperty")
    def GetTimestepValues(self):
        return self._get_timesteps().tolist()

    def RequestInformation(self, request, inInfo, outInfo):
        logger.debug("Requesting information...")
        # This needs the time data from the trajectory file, so we may have to
        # set the `TIME_RANGE` and `TIME_STEPS` already in the
        # TrajectoryDataReader.
        timesteps_util.set_timesteps(self,
                                     self._get_timesteps(),
                                     logger=logger)
        return 1

    def RequestData(self, request, inInfo, outInfo):
        logger.debug("Requesting data...")
        input = self.GetInputDataObject(0, 0)
        trajectory_data = dsa.WrapDataObject(input)
        output = dsa.WrapDataObject(vtkPolyData.GetData(outInfo))

        # Retrieve current time
        time = timesteps_util.get_timestep(self, logger=logger)

        # Retrieve trajectory data
        trajectory_times = trajectory_data.PointData['Time']
        trajectory_points = trajectory_data.Points

        # Interpolate along the trajectory to find current position
        current_position = [
            np.interp(time, trajectory_times, trajectory_points[:, i])
            for i in range(3)
        ]

        # Expose to VTK
        points_vtk = vtk.vtkPoints()
        verts_vtk = vtk.vtkCellArray()
        verts_vtk.InsertNextCell(1)
        points_vtk.InsertPoint(0, *current_position)
        verts_vtk.InsertCellPoint(0)
        output.SetPoints(points_vtk)
        output.SetVerts(verts_vtk)

        # Interpolate remaining point data along the trajectory
        for dataset in trajectory_data.PointData.keys():
            if dataset == 'Time':
                continue
            point_data = trajectory_data.PointData[dataset]
            data_at_position = np.zeros(point_data.shape[1:])
            if len(data_at_position.shape) > 0:
                for i in itertools.product(
                        *map(range, data_at_position.shape)):
                    point_data_i = point_data[(slice(None), ) + i]
                    if len(trajectory_times) == len(point_data_i):
                        data_at_position[i] = np.interp(
                            time, trajectory_times, point_data_i)
                    else:
                        logger.warning(
                            "Unable to interpolate trajectory dataset {}[{}]: Length of dataset ({}) does not match length of trajectory times ({}).".format(
                                dataset, i, len(point_data_i), len(trajectory_times)))
            else:
                data_at_position = np.interp(time, trajectory_times,
                                             point_data)
            data_vtk = vtknp.numpy_to_vtk(np.array([data_at_position]))
            data_vtk.SetName(dataset)
            output.GetPointData().AddArray(data_vtk)
        return 1
