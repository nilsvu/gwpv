import functools
import logging
import multiprocessing
from logging.handlers import QueueHandler

import h5py

from gwpv.progress import render_progress
from gwpv.render.frames import render_frames
from gwpv.scene_configuration import animate, parse_as

logger = logging.getLogger(__name__)


def _init_subprocess(logging_config, logging_queue):
    """Initializes each subprocess

    Logging records are put into the queue so the main thread can handle them.
    """
    logging.basicConfig(
        **logging_config, handlers=[QueueHandler(logging_queue)]
    )


def _render_frames_parallel(task_id, progress_queue, **kwargs):
    """Loops over render_frames and puts progress updates in the queue"""
    for progress_update in render_frames(**kwargs):
        progress_update["task_id"] = task_id
        progress_queue.put(progress_update)


def _subprocess_put_error(err, error_queue, progress_queue):
    """Exception handler for subprocesses

    Exceptions are put into the `error_queue` so the main thread can handle
    them. At the same time, `None` is put into the `progress_queue` to advance
    the loop monitoring it.
    """
    # Exceptions from multiprocessing carry the original `__cause__` but no
    # `__traceback__` (as of Py 3.9)
    error_queue.put((err, err.__cause__))
    progress_queue.put(None)


def render_parallel(
    num_jobs,
    scene,
    subprocess_logging_config,
    frame_window=None,
    **kwargs,
):
    """Dispatches to multiple processes to render frames in parallel

    Displays progress bars and configures logging from subprocesses.

    Arguments are forwarded to `render_frames`.
    """
    # Infer frame window if needed
    if "FreezeTime" in scene["Animation"]:
        frame_window = (0, 1)
    elif frame_window is None:
        if "Crop" in scene["Animation"]:
            max_animation_length = (
                scene["Animation"]["Crop"][1] - scene["Animation"]["Crop"][0]
            )
        else:
            waveform_file_and_subfile = parse_as.file_and_subfile(
                scene["Datasources"]["Waveform"]
            )
            with h5py.File(waveform_file_and_subfile[0], "r") as waveform_file:
                waveform_times = waveform_file[waveform_file_and_subfile[1]][
                    "Y_l2_m2.dat"
                ][:, 0]
                max_animation_length = waveform_times[-1] - waveform_times[0]
                logger.debug(
                    f"Inferred max. animation length {max_animation_length}M"
                    " from waveform data."
                )
        frame_window = (
            0,
            animate.num_frames(
                max_animation_length=max_animation_length,
                animation_speed=scene["Animation"]["Speed"],
                frame_rate=scene["Animation"]["FrameRate"],
            ),
        )
        logger.debug(f"Inferred total frame window: {frame_window}")

    num_frames = frame_window[1] - frame_window[0]
    frames_per_job = int(num_frames / num_jobs)
    extra_frames = num_frames % num_jobs
    logger.debug(
        f"Using {num_jobs} jobs with {frames_per_job} frames per job"
        f" ({extra_frames} jobs render an additional frame)."
    )

    frame_windows = []
    distributed_frames = frame_window[0]
    for i in range(num_jobs):
        frames_this_job = frames_per_job + (1 if i < extra_frames else 0)
        frame_windows.append(
            (distributed_frames, distributed_frames + frames_this_job)
        )
        distributed_frames += frames_this_job
    logger.debug(f"Frame windows: {frame_windows}")

    with render_progress as progress:
        with multiprocessing.Manager() as manager:
            logging_queue = manager.Queue()
            progress_queue = manager.Queue()
            error_queue = manager.Queue()

            with multiprocessing.Pool(
                processes=num_jobs,
                initializer=_init_subprocess,
                initargs=(subprocess_logging_config, logging_queue),
            ) as pool:
                for frame_window in frame_windows:
                    num_frames_this_window = frame_window[1] - frame_window[0]
                    if num_frames_this_window == 0:
                        continue
                    task_id = progress.add_task(
                        f"Rendering frames {frame_window[0] + 1} -"
                        f" {frame_window[1]}",
                        total=num_frames_this_window,
                        start=False,
                    )
                    pool.apply_async(
                        _render_frames_parallel,
                        kwds=dict(
                            task_id=task_id,
                            progress_queue=progress_queue,
                            scene=scene,
                            frame_window=frame_window,
                            **kwargs,
                        ),
                        error_callback=functools.partial(
                            _subprocess_put_error,
                            error_queue=error_queue,
                            progress_queue=progress_queue,
                        ),
                    )
                pool.close()

                # Update the display when subprocesses report progress
                while error_queue.empty() and not progress.finished:
                    progress_update = progress_queue.get()
                    if progress_update is None:
                        continue
                    elif "start" in progress_update:
                        progress.start_task(progress_update["task_id"])
                    else:
                        progress.update(**progress_update)
                    while not logging_queue.empty():
                        logger.handle(logging_queue.get())

                # Log the remaining records
                while not logging_queue.empty():
                    logger.handle(logging_queue.get())

                # Raise errors from subprocesses
                if not error_queue.empty():
                    error, cause = error_queue.get()
                    raise error from cause

                # Wait for all processes to complete
                pool.join()
