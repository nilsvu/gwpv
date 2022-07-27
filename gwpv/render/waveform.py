import logging
from tempfile import NamedTemporaryFile

import astropy.constants as const
import h5py
import matplotlib.animation as mpl_animation
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.image import imread

from gwpv.progress import render_progress
from gwpv.scene_configuration import parse_as


# https://kavigupta.org/2019/05/18/Setting-the-size-of-figures-in-matplotlib/
def get_size(fig, dpi=100):
    with NamedTemporaryFile(suffix=".png") as f:
        fig.savefig(f.name, bbox_inches="tight", dpi=dpi, pad_inches=0)
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
            abs(actual_width - target_width)
            + abs(actual_height - target_height)
        )
        if deltas[-1] < eps:
            return True
        if (
            len(deltas) > give_up
            and sorted(deltas[-give_up:]) == deltas[-give_up:]
        ):
            return False
        if set_width * dpi < min_size_px or set_height * dpi < min_size_px:
            return False


def render_waveform(scene, output_file, time_merger, mass, bounds=None):
    logger = logging.getLogger(__name__)

    waveform_file_and_subfile = parse_as.file_and_subfile(
        scene["Datasources"]["Waveform"]
    )
    logger.info(
        "Rendering waveform from file '{}:{}'".format(
            *waveform_file_and_subfile
        )
    )
    with h5py.File(waveform_file_and_subfile[0], "r") as h5_waveform_file:
        waveform_data = h5_waveform_file[waveform_file_and_subfile[1]]
        mode = "Y_l2_m2.dat"
        waveform = np.array(waveform_data[mode][:, 1:])
        time = np.array(waveform_data[mode][:, 0])
        logger.debug(
            f"Waveform has {len(waveform)} samples in time range [{time[0]},"
            f" {time[-1]}]M"
        )

    crop = np.array(
        scene["Animation"].get("Crop", [time[0], time[-1]]), dtype=np.float
    )
    logger.debug(f"Cropping animation to [{crop[0]}, {crop[1]}]M")

    if bounds is None:
        bounds = crop
    else:
        bounds = np.asarray(bounds)

    if time_merger is not None and mass is not None:
        # Transform time to seconds
        M_in_s = (const.G / const.c**3 * const.M_sun * mass).value
        time *= M_in_s
        time_merger *= M_in_s
        crop *= M_in_s
        bounds *= M_in_s

        num_extra_time = 100
        time = np.hstack(
            [time, np.linspace(time[-1], bounds[1], num_extra_time)]
        )
        waveform = np.vstack([waveform, num_extra_time * [waveform[-1]]])
    else:
        M_in_s = 1

    dpi = 100
    fig = plt.figure(dpi=dpi, tight_layout=True)
    ax = plt.gca()
    plt.plot(time, waveform[:, 0], color="white", lw=1, alpha=0.5)
    (plot_active,) = plt.plot(time, waveform[:, 0], color="white", lw=1.5)

    time_annotation = plt.annotate(
        "",
        (0, 0),
        color="white",
        ha="left",
        textcoords="offset points",
        xytext=(5, 0),
        fontsize=12,
        va="center",
        bbox=dict(boxstyle="square", fc=(0, 0, 0, 0.5), ec="none"),
    )

    plt.xlim(*bounds)
    plt.axis("off")
    set_size(fig, (1920 / dpi, 60 / dpi))

    # Write animation
    speed = scene["Animation"]["Speed"] * M_in_s
    time_in_s = crop[1] - crop[0]
    frame_rate = 30
    num_frames = int(time_in_s / speed * frame_rate)
    logger.debug(
        f"Writing animation with speed {speed} scene seconds per real second"
        f" and {time_in_s / speed} real seconds duration. That's"
        f" {num_frames} frames at {frame_rate} FPS."
    )

    progress = render_progress
    task_id = None

    def animation_init():
        nonlocal progress, task_id, num_frames, plot_active, time_annotation
        task_id = progress.add_task("Rendering", total=num_frames)
        return plot_active, time_annotation

    def animation_update(t_now):
        nonlocal progress, task_id, plot_active, time_annotation, waveform, time, time_merger
        i_now = None
        for i, t_i in enumerate(time):
            if t_i >= t_now:
                i_now = i
                break
        plot_active.set_data(time[: i_now + 1], waveform[: i_now + 1, 0])
        ax.lines = [ax.lines[0], ax.lines[1]]
        ax.axvline(t_now, color="white", alpha=0.3, lw=3)
        if t_now <= time_merger - 0.01:
            time_annotation.xy = (t_now, 0)
            time_annotation.set_text(
                f"${t_now - time_merger:.2f}" + r"\mathrm{s}$"
            )
        else:
            try:
                time_annotation.remove()
            except ValueError:
                pass
        progress.update(task_id, advance=1)
        return plot_active, time_annotation

    plt.savefig(output_file + ".png", dpi=dpi, facecolor="black")

    ani = mpl_animation.FuncAnimation(
        fig,
        animation_update,
        frames=np.linspace(crop[0], crop[1], num_frames),
        init_func=animation_init,
        blit=True,
    )

    Writer = mpl_animation.writers["ffmpeg"]
    writer = Writer(fps=frame_rate)

    with progress:
        ani.save(
            output_file + ".mp4",
            writer=writer,
            dpi=dpi,
            savefig_kwargs=dict(facecolor="black"),
        )
