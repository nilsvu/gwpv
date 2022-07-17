#!/usr/bin/env python

# This script needs to control its startup sequence to interface with ParaView's
# `pvpython`.
#
# 1. The user launches `gwrender` in a Python environment of their choice.
#    They have `gwpv` and its dependencies installed in this environment.
#    The `pvpython` executable is available in the `PATH`.
# 2. CLI arguments are parsed.
#    a. The `scene` entrypoint is dispatched to `pvpython` in a subprocess,
#       passing along the path to the active Python environment.
#    b. The `scenes` entrypoint launches subprocesses with the `pvpython`
#       executable that each call the `scene` entrypoint.
# 3. Now running in `pvpython`, the Python environment is activated using its
#    `activate_this.py` script.
# 4. The `gwpv.render.frames` module is imported in the global namespace so
#    ParaView plugins are loaded and work with `multiprocessing`.
#
# FIXME:
# - Installing in editable mode with `pip install -e` is broken
# - Generated state file doesn't `UpdatePipeline()` in between adding the
# reader and the filter, so the timesteps are not loaded from the file yet.
# This generates an error in the GUI and timesteps are unavailable.
# I had no success propagating the time range from the reader to the filter
# in `RequestInformation` so far, neither using information keys nor
# `vtkFieldData`.

from __future__ import division

import json
import logging
import os
import sys

# Work around https://gitlab.kitware.com/paraview/paraview/-/issues/21457
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__
sys.stdin = sys.__stdin__

# Activate the virtual environment if requested before trying to import
# anything outside the standard library
if __name__ == "__main__" and "--activate-venv" in sys.argv:
    activate_venv = sys.argv[sys.argv.index("--activate-venv") + 1]
    activate_venv_script = os.path.join(
        activate_venv, "bin", "activate_this.py"
    )
    assert os.path.exists(
        activate_venv_script
    ), f"No 'bin/activate_this.py' script found in '{activate_venv}'."
    with open(activate_venv_script, "r") as f:
        exec(f.read(), {"__file__": activate_venv_script})


def render_scene_entrypoint(
    scene_files,
    keypath_overrides,
    scene_paths,
    num_jobs,
    render_movie_to_file,
    force_offscreen_rendering,
    subprocess_logging_config=None,
    **kwargs,
):
    from gwpv.download_data import download_data
    from gwpv.scene_configuration.load import load_scene
    from gwpv.swsh_cache import precompute_cached_swsh_grid

    # Validate options
    assert (
        kwargs["frames_dir"] is not None
        or kwargs["no_render"]
        or render_movie_to_file is not None
    ), (
        "Provide the `--frames-dir` option, the '--render-movie-to-file'"
        " option, or disable rendering with `--no-render`."
    )
    if kwargs["frames_dir"] is None and render_movie_to_file is not None:
        kwargs["frames_dir"] = render_movie_to_file + "_frames"

    # Load scene configuration file
    scene = load_scene(scene_files, keypath_overrides, paths=scene_paths)

    # Download data files
    download_data(scene["Datasources"])

    # Cache SWSH grid
    precompute_cached_swsh_grid(scene)

    if num_jobs == 1:
        from gwpv.progress import render_progress
        from gwpv.render.frames import render_frames

        with render_progress as progress:
            task_id = progress.add_task("Rendering", start=False)
            for progress_update in render_frames(
                scene=scene,
                **kwargs,
            ):
                if "start" in progress_update:
                    progress.start_task(task_id)
                else:
                    progress.update(task_id, **progress_update)
    else:
        from gwpv.render.parallel import render_parallel

        render_parallel(
            num_jobs=num_jobs,
            scene=scene,
            subprocess_logging_config=subprocess_logging_config,
            **kwargs,
        )

    if (
        render_movie_to_file is not None
        and "FreezeTime" not in scene["Animation"]
    ):
        from gwpv.render.movie import render_movie

        render_movie(
            output_filename=render_movie_to_file,
            frame_rate=scene["Animation"]["FrameRate"],
            frames_dir=kwargs["frames_dir"],
        )


def dispatch_to_pvpython(force_offscreen_rendering, cli_args):
    import subprocess

    logger = logging.getLogger(__name__)
    # Check if we're running in a virtual environment and pass that
    # information on
    activate_venv_script = os.path.join(sys.prefix, "bin", "activate_this.py")
    pvpython_command = (
        ["pvpython"]
        + (["--force-offscreen-rendering"] if force_offscreen_rendering else [])
        + cli_args
        + (
            ["--activate-venv", sys.prefix]
            if os.path.exists(activate_venv_script)
            else []
        )
    )
    logger.debug(f"Dispatching to 'pvpython' as: {pvpython_command}")
    return subprocess.call(pvpython_command)


def render_scenes_entrypoint(
    scenes_file,
    output_dir,
    output_prefix,
    output_suffix,
    scene_overrides,
    scene_paths,
    keypath_overrides,
    render_missing_frames,
    num_jobs,
    force_offscreen_rendering,
    verbose,
    logging_config,
):
    import itertools

    import rich
    import yaml

    common_args = (
        list(
            itertools.chain(
                *[
                    ("--override", "=".join(override))
                    for override in keypath_overrides
                ]
            )
        )
        + (["--render-missing-frames"] if render_missing_frames else [])
        + list(
            itertools.chain(*[("-p", scene_path) for scene_path in scene_paths])
        )
        + ["-n", str(num_jobs)]
        + ["-v"] * verbose
        + (
            ["--logging-config", "'" + json.dumps(logging_config) + "'"]
            if logging_config is not None
            else []
        )
    )

    with open(scenes_file, "r") as open_scenes_file:
        scenes = yaml.safe_load(open_scenes_file)["Scenes"]
        for i, scene in enumerate(scenes):
            rich.print(
                f"Rendering scene {i + 1}/{len(scenes)}:"
                f" [bold]{scene['Name']}[/bold]"
            )
            scene_files = [scenes_file + ":" + scene["Name"]] + scene_overrides
            movie_file = os.path.join(
                output_dir, output_prefix + scene["Name"] + output_suffix
            )
            # Run as a subprocess instead of calling `render_scene_entrypoint`
            # directly to make sure ParaView releases memory after each run
            dispatch_to_pvpython(
                force_offscreen_rendering,
                [__file__, "scene"]
                + scene_files
                + ["--render-movie-to-file", movie_file]
                + common_args,
            )


def render_waveform_entrypoint(
    scene_files, keypath_overrides, scene_paths, **kwargs
):
    from gwpv.download_data import download_data
    from gwpv.render.waveform import render_waveform
    from gwpv.scene_configuration.load import load_scene

    scene = load_scene(scene_files, keypath_overrides, paths=scene_paths)
    download_data(scene["Datasources"])
    render_waveform(scene, **kwargs)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        "gwrender", description="Visualize gravitational waves with ParaView"
    )
    subparsers = parser.add_subparsers(dest="entrypoint")
    subparsers.required = True

    # `scene` CLI
    parser_scene = subparsers.add_parser(
        "scene", help="Render frames for a single scene."
    )
    parser_scene.set_defaults(subcommand=render_scene_entrypoint)
    parser_scene.add_argument(
        "scene_files",
        help=(
            "Path to one or more YAML scene configuration files. Entries in"
            " later files override those in earlier files."
        ),
        nargs="+",
    )
    parser_scene.add_argument(
        "--frames-dir", "-o", help="Output directory for frames", required=False
    )
    parser_scene.add_argument(
        "--frame-window",
        help=(
            "Subset of frames to render. Includes lower bound and excludes"
            " upper bound."
        ),
        type=int,
        nargs=2,
    )
    parser_scene.add_argument(
        "--render-movie-to-file",
        help=(
            "Name of a file (excluding extension) to render a movie from all"
            " frames to."
        ),
    )
    parser_scene.add_argument(
        "--save-state-to-file",
        help=(
            "Name of a file (excluding the 'pvsm' extension) to save the"
            " ParaView state to. The file can be loaded with ParaView to"
            " inspect the scene interactively."
        ),
    )
    parser_scene.add_argument(
        "--no-render",
        action="store_true",
        help="Skip rendering any frames, e.g. to produce only a state file.",
    )
    parser_scene_preview_group = parser_scene.add_mutually_exclusive_group()
    parser_scene_preview_group.add_argument(
        "--show-preview",
        action="store_true",
        help="Show a window with a preview of the full movie.",
    )

    # `scenes` CLI
    parser_scenes = subparsers.add_parser(
        "scenes", help="Render a set of scenes consecutively."
    )
    parser_scenes.set_defaults(subcommand=render_scenes_entrypoint)
    parser_scenes.add_argument(
        "scenes_file", help="Path to a YAML file listing the scenes to render."
    )
    parser_scenes.add_argument(
        "scene_overrides",
        help="Overrides to apply to all scenes",
        nargs="*",
        default=[],
    )
    parser_scenes.add_argument("--output-dir", "-o")
    parser_scenes.add_argument("--output-prefix", default="")
    parser_scenes.add_argument("--output-suffix", default="")

    # Common CLI for `scene` and `scenes`
    for subparser in [parser_scene, parser_scenes]:
        subparser.add_argument(
            "--render-missing-frames",
            help="Only render missing frames without replacing existing files.",
            action="store_true",
        )
        subparser.add_argument(
            "--num-jobs",
            "-n",
            help="Render frames in parallel",
            type=int,
            default=1,
        )
        subparser.add_argument(
            "--force-offscreen-rendering", "-x", action="store_true"
        )
        subparser.add_argument("--activate-venv")

    # `waveform` CLI
    parser_waveform = subparsers.add_parser(
        "waveform", help="Render waveform for a scene."
    )
    parser_waveform.set_defaults(subcommand=render_waveform_entrypoint)
    parser_waveform.add_argument(
        "scene_files",
        help=(
            "Path to one or more YAML scene configuration files. Entries in"
            " later files override those in earlier files."
        ),
        nargs="+",
    )
    parser_waveform.add_argument("--output-file", "-o", required=True)
    parser_waveform.add_argument("--time-merger", type=float, required=True)
    parser_waveform.add_argument("--mass", type=float, required=True)
    parser_waveform.add_argument("--bounds", type=float, nargs=2)

    # Common CLI for all entrypoints
    for subparser in [parser_scene, parser_scenes, parser_waveform]:
        subparser.add_argument(
            "--scene-path",
            "-p",
            help="Append search paths for scene configuration files",
            action="append",
            dest="scene_paths",
            default=[],
        )
        subparser.add_argument(
            "--override",
            help=(
                "A key-value pair that replaces an entry in the scene file,"
                " e.g. '--override Animation.FrameRate=30'. The value is parsed"
                " as YAML."
            ),
            action="append",
            type=lambda kv: kv.split("="),
            dest="keypath_overrides",
            default=[],
        )
        subparser.add_argument(
            "--verbose",
            "-v",
            action="count",
            default=0,
            help="Logging verbosity (-v, -vv, ...)",
        )
        subparser.add_argument("--logging-config", type=json.loads)

    args = parser.parse_args()

    # Venv activation is handled at the start of the script
    if args.entrypoint in ["scene", "scenes"]:
        del args.activate_venv

    # Setup logging
    from rich.logging import RichHandler

    FORMAT = "%(message)s"
    logging_config = dict(
        level=logging.WARNING - args.verbose * 10,
        format=FORMAT,
        datefmt="[%X]",
    )
    logging.basicConfig(
        **logging_config,
        handlers=[RichHandler()],
    )
    if args.logging_config is not None:
        if "version" not in args.logging_config:
            args.logging_config["version"] = 1
        logging.config.dictConfig(args.logging_config)
    if args.entrypoint != "scenes":
        del args.verbose
        del args.logging_config
    if args.entrypoint == "scene":
        args.subprocess_logging_config = logging_config
    logger = logging.getLogger(__name__)

    # Setup tracebacks
    import rich.traceback

    rich.traceback.install(show_locals=True)

    # Re-launch the script with `pvpython` if necessary
    if args.entrypoint == "scene":
        try:
            logger.debug("Checking if we're running with 'pvpython'...")
            import paraview.simple
        except ImportError:
            logger.debug("Not running with 'pvpython', dispatching...")
            sys.exit(
                dispatch_to_pvpython(
                    args.force_offscreen_rendering, [__file__] + sys.argv[1:]
                )
            )
        logger.debug("Running with 'pvpython'.")

    # Forward to the user-selected entrypoint
    subcommand = args.subcommand
    del args.subcommand
    del args.entrypoint
    subcommand(**vars(args))


if __name__ == "__main__":
    main()
