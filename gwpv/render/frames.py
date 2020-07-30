from __future__ import division

import gwpv.scene_configuration.transfer_functions as tf
import gwpv.scene_configuration.color as config_color
import h5py
import logging
import numpy as np
import os
import paraview.servermanager as pvserver
import paraview.simple as pv
import time
import tqdm
from gwpv.progress import TqdmLoggingHandler
from gwpv.scene_configuration import animate, camera_motion, parse_as

logger = logging.getLogger(__name__)

pv._DisableFirstRenderCameraReset()

# Load plugins
# - We need to load the plugins outside the `render` function to make
# them work with `multiprocessing`.
# - This has problems with `pvbatch`. We could use `PV_PLUGIN_PATH` env variable
# to load plugins, but then we have to get the client proxy somehow. Here's an
# attempt using ParaView-internal functions:
# WaveformDataReader = pv._create_func("WaveformDataReader", pvserver.sources)
# WaveformToVolume = pv._create_func("WaveformToVolume", pvserver.filters)
logger.info("Loading plugins...")
plugins_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'paraview_plugins')
pv.LoadPlugin(os.path.join(plugins_dir, 'WaveformDataReader.py'),
              remote=False,
              ns=globals())
pv.LoadPlugin(os.path.join(plugins_dir, 'WaveformToVolume.py'),
              remote=False,
              ns=globals())
pv.LoadPlugin(os.path.join(plugins_dir, 'TrajectoryDataReader.py'),
              remote=False,
              ns=globals())
pv.LoadPlugin(os.path.join(plugins_dir, 'FollowTrajectory.py'),
              remote=False,
              ns=globals())
pv.LoadPlugin(os.path.join(plugins_dir, 'TrajectoryTail.py'),
              remote=False,
              ns=globals())
logger.info("Plugins loaded.")


def render_frames(scene,
                  frames_dir=None,
                  frame_window=None,
                  render_missing_frames=False,
                  save_state_to_file=None,
                  no_render=False,
                  show_preview=False,
                  show_progress=False,
                  job_id=None):
    # Validate scene
    if scene['View']['ViewSize'][0] % 16 != 0:
        logger.warning("The view width should be a multiple of 16 to be compatible with QuickTime.")
    if scene['View']['ViewSize'][1] % 2 != 0:
        logger.warning("The view height should be even to be compatible with QuickTime.")

    render_start_time = time.time()

    # Setup layout
    layout = pv.CreateLayout('Layout')

    # Setup view
    if 'BackgroundTexture' in scene['View']:
        background_texture_config = scene['View']['BackgroundTexture']
        del scene['View']['BackgroundTexture']
    else:
        background_texture_config = None
    view = pv.CreateRenderView(**scene['View'])
    pv.AssignViewToLayout(view=view, layout=layout, hint=0)

    # Set spherical background texture
    if background_texture_config is not None:
        background_radius = background_texture_config['Radius']
        del background_texture_config['Radius']
        skybox_datasource = background_texture_config['Datasource']
        del background_texture_config['Datasource']
        background_texture = pvserver.rendering.ImageTexture(
            FileName=parse_as.path(scene['Datasources'][skybox_datasource]),
            **background_texture_config)
        background_sphere = pv.Sphere(Radius=background_radius,
                                      ThetaResolution=100,
                                      PhiResolution=100)
        background_texture_map = pv.TextureMaptoSphere(Input=background_sphere)
        pv.Show(background_texture_map,
                view,
                Texture=background_texture,
                BackfaceRepresentation='Cull Frontface',
                Ambient=1.0)

    # Load the waveform data file
    waveform_h5file, waveform_subfile = parse_as.file_and_subfile(
        scene['Datasources']['Waveform'])
    waveform_data = WaveformDataReader(FileName=waveform_h5file,
                                       Subfile=waveform_subfile)
    pv.UpdatePipeline()

    # Generate volume data from the waveform. Also sets the available time range.
    # TODO: Pull KeepEveryNthTimestep out of datasource
    waveform_to_volume_configs = scene['WaveformToVolume']
    if isinstance(waveform_to_volume_configs, dict):
        waveform_to_volume_configs = [{
            'Object': waveform_to_volume_configs,
        }]
        if 'VolumeRepresentation' in scene:
            waveform_to_volume_configs[0]['VolumeRepresentation'] = scene['VolumeRepresentation']
    waveform_to_volume_objects = []
    for waveform_to_volume_config in waveform_to_volume_configs:
        volume_data = WaveformToVolume(
            WaveformData=waveform_data,
            SwshCacheDirectory=parse_as.path(scene['Datasources']['SwshCache']),
            **waveform_to_volume_config['Object'])
        if 'Modes' in waveform_to_volume_config['Object']:
            volume_data.Modes = waveform_to_volume_config['Object']['Modes']
        if 'Polarizations' in waveform_to_volume_config['Object']:
            volume_data.Polarizations = waveform_to_volume_config['Object']['Polarizations']
        waveform_to_volume_objects.append(volume_data)

    # Compute timing and frames information
    time_range_in_M = volume_data.TimestepValues[
        0], volume_data.TimestepValues[-1]
    logger.debug(
        "Full available data time range: {} (in M)".format(time_range_in_M))
    if 'FreezeTime' in scene['Animation']:
        frozen_time = scene['Animation']['FreezeTime']
        logger.info("Freezing time at {}.".format(frozen_time))
        view.ViewTime = frozen_time
        animation = None
    else:
        if 'Crop' in scene['Animation']:
            time_range_in_M = scene['Animation']['Crop']
            logger.debug("Cropping time range to {} (in M).".format(time_range_in_M))
        animation_speed = scene['Animation']['Speed']
        frame_rate = scene['Animation']['FrameRate']
        num_frames = animate.num_frames(
            max_animation_length=time_range_in_M[1] - time_range_in_M[0],
            animation_speed=animation_speed,
            frame_rate=frame_rate)
        animation_length_in_seconds = num_frames / frame_rate
        animation_length_in_M = animation_length_in_seconds * animation_speed
        time_per_frame_in_M = animation_length_in_M / num_frames
        logger.info(
            "Rendering {:.2f}s movie with {} frames ({} FPS or {:.2e} M/s or {:.2e} M/frame)...".
            format(
                animation_length_in_seconds,
                num_frames,
                frame_rate,
                animation_speed,
                time_per_frame_in_M
            ))
        if frame_window is not None:
            animation_window_num_frames = frame_window[1] - frame_window[0]
            animation_window_time_range = (
                time_range_in_M[0] + frame_window[0] * time_per_frame_in_M,
                time_range_in_M[0] + (frame_window[1] - 1) * time_per_frame_in_M)
            logger.info(
                "Restricting rendering to {} frames (numbers {} to {}).".format(
                    animation_window_num_frames, frame_window[0],
                    frame_window[1] - 1))
        else:
            animation_window_num_frames = num_frames
            animation_window_time_range = time_range_in_M
            frame_window = (0, num_frames)

        # Setup animation so that sources can retrieve the `UPDATE_TIME_STEP`
        animation = pv.GetAnimationScene()
        # animation.UpdateAnimationUsingDataTimeSteps()
        # Since the data can be evaluated at arbitrary times we define the time steps
        # here by setting the number of frames within the full range
        animation.PlayMode = 'Sequence'
        animation.StartTime = animation_window_time_range[0]
        animation.EndTime = animation_window_time_range[1]
        animation.NumberOfFrames = animation_window_num_frames
        logger.debug("Animating from scene time {} to {} in {} frames.".format(
            animation.StartTime, animation.EndTime, animation.NumberOfFrames))

        def scene_time_from_real(real_time):
            return real_time / animation_length_in_seconds * animation_length_in_M

        # For some reason the keyframe time for animations is expected to be within
        # (0, 1) so we need to transform back and forth from this "normalized" time
        def scene_time_from_normalized(normalized_time):
            return animation.StartTime + normalized_time * (
                animation.EndTime - animation.StartTime)

        def normalized_time_from_scene(scene_time):
            return (scene_time - animation.StartTime) / (animation.EndTime -
                                                         animation.StartTime)

        # Setup progress measuring already here so volume data computing for
        # initial frame is measured
        if show_progress and not no_render:
            logging.getLogger().handlers = [TqdmLoggingHandler()]
            animation_window_frame_range = tqdm.trange(
                animation_window_num_frames,
                desc="Rendering",
                unit="frame",
                miniters=1,
                position=job_id)
        else:
            animation_window_frame_range = range(animation_window_num_frames)

        # Set the initial time step
        animation.GoToFirst()

    # Display the volume data. This will trigger computing the volume data at the
    # current time step.
    for volume_data, waveform_to_volume_config in zip(waveform_to_volume_objects, waveform_to_volume_configs):
        vol_repr = waveform_to_volume_config['VolumeRepresentation'] if 'VolumeRepresentation' in waveform_to_volume_config else {}
        volume_color_by = config_color.extract_color_by(vol_repr)
        if 'Representation' not in vol_repr:
            vol_repr['Representation'] = 'Volume'
        if 'VolumeRenderingMode' not in vol_repr:
            vol_repr['VolumeRenderingMode'] = 'GPU Based'
        if 'Shade' not in vol_repr:
            vol_repr['Shade'] = True
        if (vol_repr['VolumeRenderingMode'] == 'GPU Based'
                and len(volume_color_by) > 2):
            logger.warning(
                "The 'GPU Based' volume renderer doesn't support multiple components.")
        if 'ScalarOpacityUnitDistance' not in vol_repr:
            vol_repr['ScalarOpacityUnitDistance'] = 4.
        volume = pv.Show(volume_data, view, **vol_repr)
        pv.ColorBy(volume, value=volume_color_by)

    if 'Slices' in scene:
        for slice_config in scene['Slices']:
            slice_obj_config = slice_config.get('Object', {})
            slice = pv.Slice(Input=volume_data)
            slice.SliceType = 'Plane'
            slice.SliceOffsetValues = [0.]
            slice.SliceType.Origin = slice_obj_config.get(
                'Origin', [0., 0., -0.3])
            slice.SliceType.Normal = slice_obj_config.get(
                'Normal', [0., 0., 1.])
            slice_rep = pv.Show(slice, view,
                                **slice_config.get('Representation', {}))
            pv.ColorBy(slice_rep, value=volume_color_by)

    # Display the time
    if 'TimeAnnotation' in scene:
        time_annotation = pv.AnnotateTimeFilter(volume_data,
                                                **scene['TimeAnnotation'])
        pv.Show(
            time_annotation, view, **scene['TimeAnnotationRepresentation'])

    # Add spheres
    if 'Spheres' in scene:
        for sphere_config in scene['Spheres']:
            sphere = pv.Sphere(**sphere_config['Object'])
            pv.Show(sphere, view, **sphere_config['Representation'])

    # Add trajectories and objects that follow them
    if 'Trajectories' in scene:
        for trajectory_config in scene['Trajectories']:
            trajectory_name = trajectory_config['Name']
            radial_scale = trajectory_config['RadialScale'] if 'RadialScale' in trajectory_config else 1.
            # Load the trajectory data
            traj_data_reader = TrajectoryDataReader(
                RadialScale=radial_scale,
                **scene['Datasources']['Trajectories'][trajectory_name])
            # Make sure the data is loaded so we can retrieve timesteps.
            # TODO: This should be fixed in `TrajectoryDataReader` by
            # communicating time range info down the pipeline, but we had issues
            # with that (see also `WaveformDataReader`).
            traj_data_reader.UpdatePipeline()
            if 'Objects' in trajectory_config:
                with animate.restore_animation_state(animation):
                    follow_traj = FollowTrajectory(TrajectoryData=traj_data_reader)
                for traj_obj_config in trajectory_config['Objects']:
                    for traj_obj_key in traj_obj_config:
                        if traj_obj_key in [
                                'Representation', 'Visibility', 'TimeShift',
                                'Glyph'
                        ]:
                            continue
                        traj_obj_type = getattr(pv, traj_obj_key)
                        traj_obj_glyph = traj_obj_type(
                            **traj_obj_config[traj_obj_key])
                    follow_traj.UpdatePipeline()
                    traj_obj = pv.Glyph(Input=follow_traj,
                                        GlyphType=traj_obj_glyph)
                    # Can't set this in the constructor for some reason
                    traj_obj.ScaleFactor = 1.
                    for glyph_property in (traj_obj_config['Glyph'] if
                                           'Glyph' in traj_obj_config else []):
                        setattr(traj_obj, glyph_property,
                                traj_obj_config['Glyph'][glyph_property])
                    traj_obj.UpdatePipeline()
                    if 'TimeShift' in traj_obj_config:
                        traj_obj = animate.apply_time_shift(
                            traj_obj, traj_obj_config['TimeShift'])
                    pv.Show(traj_obj, view, **traj_obj_config['Representation'])
                    if 'Visibility' in traj_obj_config:
                        animate.apply_visibility(traj_obj,
                                                 traj_obj_config['Visibility'],
                                                 normalized_time_from_scene,
                                                 scene_time_from_real)
            if 'Tail' in trajectory_config:
                with animate.restore_animation_state(animation):
                    traj_tail = TrajectoryTail(TrajectoryData=traj_data_reader)
                if 'TimeShift' in trajectory_config:
                    traj_tail = animate.apply_time_shift(
                        traj_tail, trajectory_config['TimeShift'])
                tail_config = trajectory_config['Tail']
                traj_color_by = config_color.extract_color_by(tail_config)
                if 'Visibility' in tail_config:
                    tail_visibility_config = tail_config['Visibility']
                    del tail_config['Visibility']
                else:
                    tail_visibility_config = None
                tail_rep = pv.Show(traj_tail, view, **tail_config)
                pv.ColorBy(tail_rep, value=traj_color_by)
                if tail_visibility_config is not None:
                    animate.apply_visibility(
                        traj_tail,
                        tail_visibility_config,
                        normalized_time_from_scene=normalized_time_from_scene,
                        scene_time_from_real=scene_time_from_real)
            if 'Move' in trajectory_config:
                move_config = trajectory_config['Move']
                logger.debug(
                    "Animating '{}' along trajectory.".format(move_config['guiName']))
                with h5py.File(trajectory_file, 'r') as traj_data_file:
                    trajectory_data = np.array(traj_data_file[trajectory_subfile])
                if radial_scale != 1.:
                    trajectory_data[:, 1:] *= radial_scale
                logger.debug("Trajectory data shape: {}".format(
                    trajectory_data.shape))
                animate.follow_path(
                    gui_name=move_config['guiName'],
                    trajectory_data=trajectory_data,
                    num_keyframes=move_config['NumKeyframes'],
                    scene_time_range=time_range_in_M,
                    normalized_time_from_scene=normalized_time_from_scene)

    # Add non-spherical horizon shapes (instead of spherical objects following
    # trajectories)
    if 'Horizons' in scene:
        for horizon_config in scene['Horizons']:
            with animate.restore_animation_state(animation):
                horizon = pv.PVDReader(FileName=scene['Datasources']
                                       ['Horizons'][horizon_config['Name']])
            if 'TimeShift' in horizon_config:
                horizon = animate.apply_time_shift(horizon,
                                                   horizon_config['TimeShift'],
                                                   animation)
            # Try to make horizon surfaces smooth. At low angular resoluton
            # they still show artifacts, so perhaps more can be done.
            horizon = pv.ExtractSurface(Input=horizon)
            horizon = pv.GenerateSurfaceNormals(Input=horizon)
            horizon_rep_config = horizon_config.get('Representation', {})
            if 'Representation' not in horizon_rep_config:
                horizon_rep_config['Representation'] = 'Surface'
            if 'AmbientColor' not in horizon_rep_config:
                horizon_rep_config['AmbientColor'] = [0., 0., 0.]
            if 'DiffuseColor' not in horizon_rep_config:
                horizon_rep_config['DiffuseColor'] = [0., 0., 0.]
            if 'Specular' not in horizon_rep_config:
                horizon_rep_config['Specular'] = 0.2
            if 'SpecularPower' not in horizon_rep_config:
                horizon_rep_config['SpecularPower'] = 10
            if 'SpecularColor' not in horizon_rep_config:
                horizon_rep_config['SpecularColor'] = [1., 1., 1.]
            if 'ColorBy' in horizon_rep_config:
                horizon_color_by = config_color.extract_color_by(
                    horizon_rep_config)
            else:
                horizon_color_by = None
            horizon_rep = pv.Show(horizon, view, **horizon_rep_config)
            if horizon_color_by is not None:
                pv.ColorBy(horizon_rep, value=horizon_color_by)
            # Animate visibility
            if 'Visibility' in horizon_config:
                animate.apply_visibility(
                    horizon,
                    horizon_config['Visibility'],
                    normalized_time_from_scene=normalized_time_from_scene,
                    scene_time_from_real=scene_time_from_real)

    # Configure transfer functions
    if 'TransferFunctions' in scene:
        for tf_config in scene['TransferFunctions']:
            colored_field = tf_config['Field']
            transfer_fctn = pv.GetColorTransferFunction(colored_field)
            opacity_fctn = pv.GetOpacityTransferFunction(colored_field)
            tf.configure_transfer_function(transfer_fctn, opacity_fctn,
                                           tf_config['TransferFunction'])

    # Save state file before configuring camera keyframes.
    # TODO: Make camera keyframes work with statefile
    if save_state_to_file is not None:
        pv.SaveState(save_state_to_file + '.pvsm')

    # Camera shots
    # TODO: Make this work with freezing time while the camera is swinging
    if animation is None:
        for i, shot in enumerate(scene['CameraShots']):
            if i == len(scene['CameraShots']) - 1 or (shot['Time'] if 'Time' in shot else 0.) >= view.ViewTime:
                camera_motion.apply(shot)
                break
    else:
        camera_motion.apply_swings(
            scene['CameraShots'],
            scene_time_range=time_range_in_M,
            scene_time_from_real=scene_time_from_real,
            normalized_time_from_scene=normalized_time_from_scene)

    # Report time
    if animation is not None:
        report_time_cue = pv.PythonAnimationCue()
        report_time_cue.Script = """
def start_cue(self): pass

def tick(self):
    import paraview.simple as pv
    logger = logging.getLogger('Animation')
    scene_time = pv.GetActiveView().ViewTime
    logger.info("Scene time: {}".format(scene_time))

def end_cue(self): pass
"""
        animation.Cues.append(report_time_cue)

    if show_preview and animation is not None:
        animation.PlayMode = 'Real Time'
        animation.Duration = 10
        animation.Play()
        animation.PlayMode = 'Sequence'

    if no_render:
        logger.info("No rendering requested. Total time: {:.2f}s".format(
            time.time() - render_start_time))
        return

    if frames_dir is None:
        raise RuntimeError("Trying to render but `frames_dir` is not set.")
    if os.path.exists(frames_dir):
        logger.warning("Output directory '{}' exists, files may be overwritten.".format(frames_dir))
    else:
        os.makedirs(frames_dir)

    if animation is None:
        pv.Render()
        pv.SaveScreenshot(os.path.join(frames_dir, 'frame.png'))
    else:
        # Iterate over frames manually to support filling in missing frames.
        # If `pv.SaveAnimation` would support that, here's how it could be
        # invoked:
        # pv.SaveAnimation(
        #     os.path.join(frames_dir, 'frame.png'),
        #     view,
        #     animation,
        #     FrameWindow=frame_window,
        #     SuffixFormat='.%06d')
        # Note that `FrameWindow` appears to be buggy, so we set up the
        # `animation` according to the `frame_window` above so the frame files
        # are numberd correctly.
        for animation_window_frame_i in animation_window_frame_range:
            frame_i = frame_window[0] + animation_window_frame_i
            frame_file = os.path.join(frames_dir,
                                      'frame.{:06d}.png'.format(frame_i))
            if render_missing_frames and os.path.exists(frame_file):
                continue
            logger.debug("Rendering frame {}...".format(frame_i))
            animation.AnimationTime = (
                animation.StartTime +
                time_per_frame_in_M * animation_window_frame_i)
            pv.Render()
            pv.SaveScreenshot(frame_file)
            logger.info("Rendered frame {}.".format(frame_i))

    logger.info(
        "Rendering done. Total time: {:.2f}s".format(time.time() -
                                                     render_start_time))
