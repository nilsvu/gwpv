import numpy as np
import matplotlib.pyplot as plt
import h5py
import matplotlib.animation as mpl_animation
import astropy.constants as const
import logging
from tqdm import tqdm
from matplotlib.image import imread
from tempfile import NamedTemporaryFile
from gwpv.scene_configuration import parse_as


# https://kavigupta.org/2019/05/18/Setting-the-size-of-figures-in-matplotlib/
def get_size(fig, dpi=100):
    with NamedTemporaryFile(suffix='.png') as f:
        fig.savefig(f.name, bbox_inches='tight', dpi=dpi, pad_inches=0)
        height, width, _channels = imread(f.name).shape
        return width / dpi, height / dpi


def set_size(fig, size, dpi=100, eps=1e-2, give_up=2, min_size_px=10):
    target_width, target_height = size
    set_width, set_height = target_width, target_height
    deltas = []
    while True:
        fig.set_size_inches([set_width, set_height])
        actual_width, actual_height = get_size(fig, dpi=dpi)
        set_width *= target_width / actual_width
        set_height *= target_height / actual_height
        deltas.append(
            abs(actual_width - target_width) +
            abs(actual_height - target_height))
        if deltas[-1] < eps:
            return True
        if len(deltas) > give_up and sorted(
                deltas[-give_up:]) == deltas[-give_up:]:
            return False
        if set_width * dpi < min_size_px or set_height * dpi < min_size_px:
            return False


def render_waveform(scene,
                    output_file,
                    time_merger,
                    mass,
                    extra_plot_range=0.095):
    logger = logging.getLogger(__name__)

    waveform_file_and_subfile = parse_as.file_and_subfile(
        scene['Datasources']['Waveform'])
    logger.info("Rendering waveform from file '{}:{}'".format(
        *waveform_file_and_subfile))
    with h5py.File(waveform_file_and_subfile[0], 'r') as h5_waveform_file:
        waveform_data = h5_waveform_file[waveform_file_and_subfile[1]]
        mode = 'Y_l2_m2.dat'
        waveform = np.array(waveform_data[mode][:, 1:])
        time = np.array(waveform_data[mode][:, 0])
        logger.debug("Waveform has {} samples in time range [{}, {}]M".format(
            len(waveform), time[0], time[-1]))

    i_start = None
    for i, t_i in enumerate(time):
        if t_i >= 1000:
            i_start = i
            break
    time = time[i_start:]
    waveform = waveform[i_start:]

    crop = np.array(scene['Animation'].get('Crop', [time[0], time[-1]]),
                    dtype=np.float)
    logger.debug("Cropping animation to [{}, {}]M".format(crop[0], crop[1]))

    # Transform time to seconds
    M_in_s = (const.G / const.c**3 * const.M_sun * mass).value
    time *= M_in_s
    time_merger *= M_in_s
    crop *= M_in_s

    time_plot_range = (time[0], time_merger + extra_plot_range *
                       (time_merger - time[0]))

    num_extra_time = 100
    time = np.hstack(
        [time, np.linspace(time[-1], time_plot_range[1], num_extra_time)])
    waveform = np.vstack([waveform, num_extra_time * [waveform[-1]]])

    dpi = 100
    fig = plt.figure(dpi=dpi, tight_layout=True)
    ax = plt.gca()
    plt.plot(time, waveform[:, 0], color='white', lw=1, alpha=0.5)
    plot_active, = plt.plot(time, waveform[:, 0], color='white', lw=1.5)

    time_annotation = plt.annotate("", (0, 0),
                                   color='white',
                                   ha='left',
                                   textcoords='offset points',
                                   xytext=(5, 0),
                                   fontsize=12,
                                   va='center',
                                   bbox=dict(boxstyle='square',
                                             fc=(0, 0, 0, 0.5),
                                             ec='none'))

    plt.xlim(*time_plot_range)
    plt.axis('off')
    set_size(fig, (1920 / dpi, 60 / dpi))

    # Write animation
    speed = scene['Animation']['Speed'] * M_in_s
    time_in_s = crop[1] - crop[0]
    frame_rate = 30
    num_frames = int(time_in_s / speed * frame_rate)
    logger.debug(
        "Writing animation with speed {} scene seconds per real second and {} real seconds duration. That's {} frames at {} FPS."
        .format(speed, time_in_s / speed, num_frames, frame_rate))

    progress_bar = None

    def animation_init():
        nonlocal progress_bar, plot_active, time_annotation
        progress_bar = tqdm(total=num_frames, unit='frames')
        return plot_active, time_annotation

    def animation_update(t_now):
        nonlocal progress_bar, plot_active, time_annotation, waveform, time, time_merger
        i_now = None
        for i, t_i in enumerate(time):
            if t_i >= t_now:
                i_now = i
                break
        plot_active.set_data(time[:i_now + 1], waveform[:i_now + 1, 0])
        ax.lines = [ax.lines[0], ax.lines[1]]
        ax.axvline(t_now, color='white', alpha=0.3, lw=3)
        if t_now <= time_merger - 0.01:
            time_annotation.xy = (t_now, 0)
            time_annotation.set_text("${:.2f}".format(t_now - time_merger) +
                                     r"\mathrm{s}$")
        else:
            try:
                time_annotation.remove()
            except ValueError:
                pass
        progress_bar.update(1)
        return plot_active, time_annotation

    ani = mpl_animation.FuncAnimation(fig,
                                      animation_update,
                                      frames=np.linspace(
                                          crop[0], crop[1], num_frames),
                                      init_func=animation_init,
                                      blit=True)

    Writer = mpl_animation.writers['ffmpeg']
    writer = Writer(fps=frame_rate)
    ani.save(output_file + '.mp4',
             writer=writer,
             dpi=dpi,
             savefig_kwargs=dict(facecolor='black'))

    if progress_bar is not None:
        progress_bar.close()

    # plt.savefig('waveform.png',
    #             dpi=dpi,
    #             facecolor='black')
