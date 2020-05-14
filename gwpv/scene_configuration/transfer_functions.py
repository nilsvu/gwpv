import numpy as np


def apply_colormap(transfer_fctn, tf_config):
    colormap_config = tf_config['Colormap']
    if isinstance(colormap_config, str):
        transfer_fctn.ApplyPreset(colormap_config, False)
        return
    elif 'Name' in colormap_config:
        transfer_fctn.ApplyPreset(colormap_config['Name'], False)
    elif 'Points' in colormap_config:
        rgb_points = []
        for point in colormap_config['Points']:
            rgb_points.append(point['Position'])
            rgb_points += point['Color']
        transfer_fctn.RGBPoints = rgb_points
    elif 'Exported' in colormap_config:
        transfer_fctn.RGBPoints = colormap_config['Exported']
    if 'Invert' in colormap_config and colormap_config['Invert']:
        transfer_fctn.InvertTransferFunction()
    if 'ColorSpace' in colormap_config:
        transfer_fctn.ColorSpace = colormap_config['ColorSpace']
    if 'Logarithmic' in colormap_config:
        transfer_fctn.UseLogScale = colormap_config['Logarithmic']


def set_opacity_function_points(opacity_fctn, opacity_fctn_points):
    # TODO: Make this flattening less crude..
    flat_pnts = []
    for i in opacity_fctn_points:
        for j in i:
            for k in j:
                flat_pnts.append(k)
    opacity_fctn.Points = flat_pnts


def configure_linear_transfer_function(transfer_fctn, opacity_fctn, tf_config):
    apply_colormap(transfer_fctn, tf_config)
    start_pos, opacity_start = tf_config['Start']['Position'], tf_config[
        'Start']['Opacity']
    end_pos, opacity_end = tf_config['End']['Position'], tf_config['End'][
        'Opacity']
    transfer_fctn.RescaleTransferFunction(start_pos, end_pos)
    set_opacity_function_points(opacity_fctn,
                                [[(start_pos, opacity_start, 0.5, 0.),
                                  (end_pos, opacity_end, 0.5, 0.)]])


def configure_peaks_transfer_function(transfer_fctn, opacity_fctn, tf_config):
    apply_colormap(transfer_fctn, tf_config)
    first_peak, opacity_first_peak = tf_config['FirstPeak'][
        'Position'], tf_config['FirstPeak']['Opacity']
    last_peak, opacity_last_peak = tf_config['LastPeak'][
        'Position'], tf_config['LastPeak']['Opacity']
    transfer_fctn.RescaleTransferFunction(first_peak, last_peak)
    num_peaks = tf_config['NumPeaks']
    if 'Logarithmic' in tf_config and tf_config['Logarithmic']:
        peaks = np.logspace(np.log10(first_peak),
                            np.log10(last_peak),
                            num_peaks,
                            base=10)
    else:
        peaks = (first_peak +
                (last_peak - first_peak) * np.linspace(0, 1, num_peaks))
        tf_decay = num_peaks * [(last_peak - first_peak) / (num_peaks - 1) / 2]
    tf_decay = list(np.diff(peaks) / 2)
    tf_decay.append(tf_decay[-1])
    opacity_scale = (opacity_last_peak - opacity_first_peak) / (num_peaks - 1)
    set_opacity_function_points(
        opacity_fctn,
        [[(peak - peak_decay / 100., 0., 0.5, 0.),
          (peak, opacity_first_peak + opacity_scale * i, 0.5, 0.),
          (peak + peak_decay, 0., 0.5, 0.)] for i, (peak, peak_decay) in enumerate(zip(peaks, tf_decay))])


def configure_custom_transfer_function(transfer_fctn, opacity_fctn, tf_config):
    apply_colormap(transfer_fctn, tf_config)
    points = tf_config['Points']
    transfer_fctn.RescaleTransferFunction(points[0]['Position'],
                                          points[-1]['Position'])
    set_opacity_function_points(
        opacity_fctn,
        [[(point['Position'], point['Opacity'], 0.5, 0.)] for point in points])


def configure_transfer_function(transfer_fctn, opacity_fctn, tf_config):
    # Dispatch to particular type of transfer function
    supported_types = ['Linear', 'Peaks', 'Custom']
    assert len(tf_config) == 1, "The transfer function configuration should have one entry which is the type of the transfer function. Currently supported are: " + str(supported_types)
    tf_type = list(tf_config.keys())[0]
    assert tf_type in supported_types, "Transfer function type '{}' not supported. Currently supported are: " + str(supported_types)
    if tf_type == 'Linear':
        configure_linear_transfer_function(transfer_fctn, opacity_fctn,
                                           tf_config['Linear'])
    elif tf_type == 'Peaks':
        configure_peaks_transfer_function(transfer_fctn, opacity_fctn,
                                          tf_config['Peaks'])
    elif tf_type == 'Custom':
        configure_custom_transfer_function(transfer_fctn, opacity_fctn,
                                           tf_config['Custom'])
    # Enable opacity for surface representations
    transfer_fctn.EnableOpacityMapping = True
