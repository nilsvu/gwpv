#!/usr/bin/env python

from __future__ import division

import logging

logger = logging.getLogger(__name__)


def render_with_paraview(force_offscreen_rendering, **kwargs):
    # Make sure the script was launched with ParaView
    try:
        logger.debug("Checking if we're running with 'pvpython'...")
        import paraview
    except ImportError:
        import sys
        import subprocess
        logger.debug("Not running with 'pvpython', dispatching...")
        sys.exit(
            subprocess.call(['pvpython'] +
                            (['--force-offscreen-rendering']
                             if force_offscreen_rendering else []) + sys.argv))
    logger.debug(
        "Running with 'pvpython'. Dispatching to rendering function...")

    # Dispatch to rendering function
    from gwpv.render.frames import render_frames
    render_frames(**kwargs)


def _render_frame_window(job_id_and_frame_window, **kwargs):
    render_with_paraview(job_id=job_id_and_frame_window[0],
                         frame_window=job_id_and_frame_window[1],
                         **kwargs)


def render_parallel(num_jobs, frame_window, scene, **kwargs):
    import functools
    import h5py
    import multiprocessing
    from gwpv.scene_configuration import parse_as
    from tqdm import tqdm

    # Infer frame window if needed
    if frame_window is None:
        if 'Crop' in scene['Animation']:
            max_animation_length = (scene['Animation']['Crop'][1] -
                                    scene['Animation']['Crop'][0])
        else:
            waveform_file_and_subfile = parse_as.file_and_subfile(
                scene['Datasources']['Waveform'])
            with h5py.File(waveform_file_and_subfile[0], 'r') as waveform_file:
                waveform_times = waveform_file[
                    waveform_file_and_subfile[1]]['Y_l2_m2.dat'][:, 0]
                max_animation_length = waveform_times[-1] - waveform_times[0]
                logger.debug(
                    "Inferred max. animation length {}M from waveform data.".
                    format(max_animation_length))
        frame_window = (0,
                        animate.num_frames(
                            max_animation_length=max_animation_length,
                            animation_speed=scene['Animation']['Speed'],
                            frame_rate=scene['Animation']['FrameRate']))
        logger.debug("Inferred total frame window: {}".format(frame_window))

    num_frames = frame_window[1] - frame_window[0]
    frames_per_job = int(num_frames / num_jobs)
    extra_frames = num_frames % num_jobs
    logger.debug(
        "Using {} jobs with {} frames per job ({} jobs render an additional frame)."
        .format(num_jobs, frames_per_job, extra_frames))

    frame_windows = []
    distributed_frames = frame_window[0]
    for i in range(num_jobs):
        frames_this_job = frames_per_job + (1 if i < extra_frames else 0)
        frame_windows.append(
            (distributed_frames, distributed_frames + frames_this_job))
        distributed_frames += frames_this_job
    logger.debug("Frame windows: {}".format(frame_windows))

    pool = multiprocessing.Pool(num_jobs,
                                initializer=tqdm.set_lock,
                                initargs=(tqdm.get_lock(), ))
    render_frame_window = functools.partial(_render_frame_window,
                                            scene=scene,
                                            **kwargs)
    pool.map(render_frame_window, enumerate(frame_windows))


def render_scene_entrypoint(scene_files, keypath_overrides, scene_paths,
                            num_jobs, render_movie_to_file, **kwargs):
    import os
    import subprocess
    from gwpv.scene_configuration.load import load_scene

    # Validate options
    assert (
        kwargs['frames_dir'] is not None or kwargs['no_render']
        or render_movie_to_file is not None
    ), "Provide the `--frames-dir` option, the '--render-movie-to-file' option, or disable rendering with `--no-render`."
    if kwargs['frames_dir'] is None and render_movie_to_file is not None:
        kwargs['frames_dir'] = render_movie_to_file + '_frames'

    # Load scene configuration file
    scene = load_scene(scene_files, keypath_overrides, paths=scene_paths)

    if num_jobs == 1:
        render_with_paraview(scene=scene, **kwargs)
    else:
        render_parallel(num_jobs=num_jobs, scene=scene, **kwargs)

    if (render_movie_to_file is not None
            and 'FreezeTime' not in scene['Animation']):
        from gwpv.render.movie import render_movie
        render_movie(output_filename=render_movie_to_file,
                     frame_rate=scene['Animation']['FrameRate'],
                     frames_dir=kwargs['frames_dir'])


def render_scenes_entrypoint(scenes_file, output_dir, output_prefix,
                             output_suffix, scene_overrides, **kwargs):
    import os
    import yaml
    from tqdm import tqdm

    scenes = yaml.safe_load(open(scenes_file, 'r'))['Scenes']
    for scene in tqdm(scenes, desc='Scenes', unit='scene'):
        render_scene_entrypoint(
            scene_files=[scenes_file + ':' + scene['Name']] + scene_overrides,
            force_offscreen_rendering=True,
            render_movie_to_file=os.path.join(
                output_dir, output_prefix + scene['Name'] + output_suffix),
            frames_dir=None,
            no_render=False,
            show_progress=True,
            **kwargs)


if __name__ == "__main__":
    # FIXME:
    # - Generated state file doesn't `UpdatePipeline()` in between adding the
    # reader and the filter, so the timesteps are not loaded from the file yet.
    # This generates an error in the GUI and timesteps are unavailable.
    # I had no success propagating the time range from the reader to the filter
    # in `RequestInformation` so far, neither using information keys nor
    # `vtkFieldData`.
    import argparse
    parser = argparse.ArgumentParser(
        'gwrender', description="Visualize gravitational waves with ParaView")
    subparsers = parser.add_subparsers()

    # `scene` CLI
    parser_scene = subparsers.add_parser(
        'scene', help="Render frames for a single scene.")
    parser_scene.set_defaults(subcommand=render_scene_entrypoint)
    parser_scene.add_argument(
        'scene_files',
        help=
        "Path to one or more YAML scene configuration files. Entries in later files override those in earlier files.",
        nargs='+')
    parser_scene.add_argument('--frames-dir', '-o',
                               help="Output directory for frames",
                               required=False)
    parser_scene.add_argument(
        '--frame-window',
        help=
        "Subset of frames to render. Includes lower bound and excludes upper bound.",
        type=int,
        nargs=2)
    parser_scene.add_argument(
        '--render-missing-frames',
        help="Only render missing frames without replacing existing files.",
        action='store_true')
    parser_scene.add_argument(
        '--render-movie-to-file',
        help=
        "Name of a file (excluding extension) to render a movie from all frames to."
    )
    parser_scene.add_argument(
        '--save-state-to-file',
        help=
        "Name of a file (excluding the 'pvsm' extension) to save the ParaView state to. The file can be loaded with ParaView to inspect the scene interactively."
    )
    parser_scene.add_argument(
        '--no-render',
        action='store_true',
        help="Skip rendering any frames, e.g. to produce only a state file.")
    parser_scene_preview_group = parser_scene.add_mutually_exclusive_group()
    parser_scene_preview_group.add_argument(
        '--show-preview',
        action='store_true',
        help="Show a window with a preview of the full movie.")
    parser_scene_preview_group.add_argument('--force-offscreen-rendering',
                                             '-x',
                                             action='store_true')
    parser_scene.add_argument('--hide-progress',
                               dest='show_progress',
                               action='store_false',
                               help="Hide the progress bar")

    # `scenes` CLI
    parser_scenes = subparsers.add_parser(
        'scenes', help="Render a set of scenes consecutively.")
    parser_scenes.set_defaults(subcommand=render_scenes_entrypoint)
    parser_scenes.add_argument(
        'scenes_file',
        help="Path to a YAML file listing the scenes to render.")
    parser_scenes.add_argument('scene_overrides',
                               help="Overrides to apply to all scenes",
                               nargs='*',
                               default=[])
    parser_scenes.add_argument('--output-dir', '-o')
    parser_scenes.add_argument('--output-prefix', default="")
    parser_scenes.add_argument('--output-suffix', default="")

    # Common CLI
    for subparser in [parser_scene, parser_scenes]:
        subparser.add_argument(
            '--scene-path',
            '-p',
            help="Append search paths for scene configuration files",
            action='append',
            dest='scene_paths',
            default=[])
        subparser.add_argument(
            '--override',
            help="A key-value pair that replaces an entry in the scene file, e.g. '--override Animation.FrameRate=30'. The value is parsed as YAML.",
            action='append',
            type=lambda kv: kv.split('='),
            dest='keypath_overrides',
            default=[])
        subparser.add_argument('--num-jobs',
                               '-n',
                               help="Render frames in parallel",
                               type=int,
                               default=1)
        subparser.add_argument('--verbose',
                               '-v',
                               action='count',
                               default=0,
                               help="Logging verbosity (-v, -vv, ...)")

    # Parse the command line arguments
    args = parser.parse_args()

    # Setup logging
    log_level = logging.WARNING - args.verbose * 10
    del args.verbose
    logging.basicConfig(level=log_level)

    # Forward to the subcommand's function
    subcommand = args.subcommand
    del args.subcommand
    subcommand(**vars(args))
