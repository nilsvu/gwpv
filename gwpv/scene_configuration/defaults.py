import h5py
import numpy as np
import logging
from . import parse_as
from . import color

logger = logging.getLogger(__name__)


def report_default(key, value):
    logger.info("Using default '{}': {}".format(key, value))


def apply_defaults(scene):

    # WaveformToVolume
    # TODO: make this more robust, work with multiple waveform volume renderings
    if 'WaveformToVolume' not in scene:
        scene['WaveformToVolume'] = {}
    waveform_to_volume_config = scene['WaveformToVolume']
    if 'Size' not in waveform_to_volume_config:
        waveform_to_volume_config['Size'] = 100
        report_default('WaveformToVolume.Size',
                       waveform_to_volume_config['Size'])
    if 'RadialScale' not in waveform_to_volume_config:
        waveform_to_volume_config['RadialScale'] = 10
        report_default('WaveformToVolume.Size',
                       waveform_to_volume_config['Size'])
    if 'VolumeRepresentation' not in scene:
        scene['VolumeRepresentation'] = {}
    vol_rep = scene['VolumeRepresentation']
    if 'ColorBy' not in vol_rep:
        vol_rep['ColorBy'] = 'Plus strain'

    # Animation
    if 'Animation' not in scene:
        scene['Animation'] = {}
    animation_config = scene['Animation']
    # Animation.Speed, Animation.Crop
    if 'FreezeTime' not in animation_config and (
            'Speed' not in animation_config or 'Crop' not in animation_config):
        waveform_file_and_subfile = parse_as.file_and_subfile(
            scene['Datasources']['Waveform'])
        with h5py.File(waveform_file_and_subfile[0], 'r') as waveform_file:
            waveform_data = waveform_file[waveform_file_and_subfile[1]]
            mode_data = waveform_data['Y_l2_m2.dat']
            t0, t1 = mode_data[0, 0], mode_data[-1, 0]
        if 'Crop' not in animation_config:
            domain_radius = scene['WaveformToVolume']['Size'] * scene[
                'WaveformToVolume']['RadialScale']
            animation_config['Crop'] = (t0 + domain_radius, t1 + domain_radius)
            report_default('Animation.Crop', animation_config['Crop'])
        if 'Speed' not in animation_config:
            default_length_in_s = 20
            animation_config['Speed'] = (
                animation_config['Crop'][1] -
                animation_config['Crop'][0]) / default_length_in_s
            report_default('Animation.Speed', animation_config['Speed'])

    # CameraShots
    if 'CameraShots' not in scene:
        camera_distance = scene['WaveformToVolume']['Size']
        scene['CameraShots'] = [{
            'Position': [-camera_distance, 0., 0.],
            'ViewUp': [0., 0., 1.],
            'FocalPoint': [0., 0., 0.],
            'ViewAngle': 60.
        }]

    if 'Horizons' in scene['Datasources'] and 'Horizons' not in scene:
        scene['Horizons'] = []
        for horizon_datasource in scene['Datasources']['Horizons']:
            scene['Horizons'].append({
                'Name': horizon_datasource,
            })

    # TransferFunctions
    if 'TransferFunctions' not in scene:
        scene['TransferFunctions'] = []
    tfs_config = scene['TransferFunctions']
    needed_tfs = set([
        color.extract_color_by(scene['VolumeRepresentation'], delete=False)[1]
    ])
    available_tfs = set([tf['Field'] for tf in tfs_config])
    default_tfs = needed_tfs - available_tfs
    for tf_field in default_tfs:
        if tf_field in ['Plus strain', 'Cross strain']:
            waveform_file_and_subfile = parse_as.file_and_subfile(
                scene['Datasources']['Waveform'])
            with h5py.File(waveform_file_and_subfile[0], 'r') as waveform_file:
                waveform_data = waveform_file[waveform_file_and_subfile[1]]
                mode_data = waveform_data['Y_l2_m2.dat']
                mode_max = np.max(
                    np.abs(mode_data[:, 1] + 1j * mode_data[:, 2]))
            pos_first_peak, pos_last_peak = 0.05 * mode_max, 0.2 * mode_max
            tfs_config.append({
                'Field': tf_field,
                'TransferFunction': {
                    'Peaks': {
                        'NumPeaks': 10,
                        'FirstPeak': {
                            'Position': pos_first_peak,
                            'Opacity': 0.01
                        },
                        'LastPeak': {
                            'Position': pos_last_peak,
                            'Opacity': 0.4
                        },
                        'Logarithmic': True,
                        'Colormap': 'Rainbow Uniform'
                    }
                }
            })
