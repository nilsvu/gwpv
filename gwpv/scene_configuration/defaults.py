import h5py
import numpy as np
import logging
from . import parse_as
from . import color

logger = logging.getLogger(__name__)


def report_default(key, value):
    logger.info("Using default '{}': {}".format(key, value))


def apply_defaults(scene):
    # Note: Only set defaults for options the user would expect to have a
    # default. For example, the Animation.Crop is set so the full waveform data
    # is shown propagating through the domain, but the Animation.Speed has no
    # obvious default.

    if 'View' not in scene:
        scene['View'] = {}
    view_config = scene['View']
    if 'OrientationAxesVisibility' not in view_config:
        view_config['OrientationAxesVisibility'] = False

    # WaveformToVolume
    # TODO: make this more robust, work with multiple waveform volume renderings
    if 'WaveformToVolume' not in scene:
        scene['WaveformToVolume'] = {}
    waveform_to_volume_config = scene['WaveformToVolume']
    if 'VolumeRepresentation' not in scene:
        scene['VolumeRepresentation'] = {}
    vol_repr = scene['VolumeRepresentation']
    if 'Representation' not in vol_repr:
        vol_repr['Representation'] = 'Volume'
    if 'VolumeRenderingMode' not in vol_repr:
        vol_repr['VolumeRenderingMode'] = 'GPU Based'
    if 'Shade' not in vol_repr:
        vol_repr['Shade'] = True

    # Animation
    if 'Animation' not in scene:
        scene['Animation'] = {}
    animation_config = scene['Animation']
    # Crop time to full propagation through domain
    if ('FreezeTime' not in animation_config and 'Crop' not in animation_config
    and 'Size' in scene['WaveformToVolume'] and 'RadialScale' in scene['WaveformToVolume']):
        waveform_file_and_subfile = parse_as.file_and_subfile(
            scene['Datasources']['Waveform'])
        with h5py.File(waveform_file_and_subfile[0], 'r') as waveform_file:
            waveform_data = waveform_file[waveform_file_and_subfile[1]]
            mode_data = waveform_data['Y_l2_m2.dat']
            t0, t1 = mode_data[0, 0], mode_data[-1, 0]
        domain_radius = scene['WaveformToVolume']['Size'] * scene[
            'WaveformToVolume']['RadialScale']
        animation_config['Crop'] = (t0 + domain_radius, t1 + domain_radius)
        report_default('Animation.Crop', animation_config['Crop'])

    # CameraShots
    if 'CameraShots' not in scene:
        camera_distance = 2 * scene['WaveformToVolume']['Size']
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
        tfs_config.append({
            'Field': tf_field,
            'TransferFunction': {
                'Peaks': {
                    'Colormap': 'Rainbow Uniform'
                }
            }
        })
    # Compute default peaks for waveform volume rendering
    for tf_config in tfs_config:
        tf_field = tf_config['Field']
        if tf_field not in ['Plus strain', 'Cross strain']:
            continue
        if 'Peaks' not in tf_config['TransferFunction']:
            continue
        peaks_config = tf_config['TransferFunction']['Peaks']
        if 'NumPeaks' not in peaks_config:
            peaks_config['NumPeaks'] = 10
        if 'FirstPeak' not in peaks_config and 'LastPeak' not in peaks_config:
            waveform_file_and_subfile = parse_as.file_and_subfile(
                scene['Datasources']['Waveform'])
            with h5py.File(waveform_file_and_subfile[0], 'r') as waveform_file:
                waveform_data = waveform_file[waveform_file_and_subfile[1]]
                mode_data = waveform_data['Y_l2_m2.dat']
                mode_max = np.max(
                    np.abs(mode_data[:, 1] + 1j * mode_data[:, 2]))
            pos_first_peak, pos_last_peak = 0.01 * mode_max, 0.2 * mode_max
            peaks_config['FirstPeak'] = {
                'Position': pos_first_peak,
                'Opacity': 0.03
            }
            peaks_config['LastPeak'] = {
                'Position': pos_last_peak,
                'Opacity': 0.5
            }
