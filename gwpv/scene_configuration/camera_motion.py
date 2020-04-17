import paraview.simple as pv
import logging
from .animate import get_scene_time

logger = logging.getLogger(__name__)


def get_last_camera_swing_path_point(shot_config, key):
    return shot_config[key][-1] if isinstance(shot_config[key][0],
                                              list) else shot_config[key]


def get_flat_camera_swing_path_points(shot_config, key, num_path_points):
    if isinstance(shot_config[key][0], list):
        assert len(shot_config[key]) == num_path_points
        return sum(shot_config[key], [])
    else:
        return num_path_points * shot_config[key]


def apply(camera_config, camera=None):
    if camera is None:
        camera = pv.GetActiveCamera()
    camera.SetFocalPoint(
        *get_last_camera_swing_path_point(camera_config, 'FocalPoint'))
    camera.SetPosition(
        *get_last_camera_swing_path_point(camera_config, 'Position'))
    camera.SetViewUp(*camera_config['ViewUp'])
    camera.SetViewAngle(camera_config['ViewAngle'])


def make_camera_swing_keyframes(shot_config,
                                start_time,
                                end_time,
                                prev_shot_config=None):
    num_path_points = 1
    for key in ['Position', 'FocalPoint']:
        if isinstance(shot_config[key][0], list):
            if num_path_points == 1:
                num_path_points = len(shot_config[key])
            else:
                assert len(shot_config[key]) == num_path_points, "Camera shots must have either one, or the same number of points in 'Position' and 'FocalPoint'"
    position_path_points = get_flat_camera_swing_path_points(shot_config, 'Position', num_path_points)
    focal_path_points = get_flat_camera_swing_path_points(shot_config, 'FocalPoint', num_path_points)
    if prev_shot_config is not None:
        position_path_points = get_last_camera_swing_path_point(prev_shot_config, 'Position') + position_path_points
        focal_path_points = get_last_camera_swing_path_point(prev_shot_config, 'FocalPoint') + focal_path_points
        assert prev_shot_config['ViewAngle'] == shot_config['ViewAngle'], "The 'Path-based' camera interpolation mode doesn't support interpolating the ViewAngle"

    path_keyframe = pv.CameraKeyFrame()
    path_keyframe.KeyTime = start_time
    path_keyframe.Position = position_path_points[:3]
    path_keyframe.PositionPathPoints = position_path_points
    path_keyframe.FocalPoint = focal_path_points[:3]
    path_keyframe.FocalPathPoints = focal_path_points
    path_keyframe.ViewUp = shot_config['ViewUp']
    path_keyframe.ViewAngle = shot_config['ViewAngle']
    path_keyframe.ClosedPositionPath = 0
    path_keyframe.ClosedFocalPath = 0

    if prev_shot_config is None and num_path_points == 1:
        return [path_keyframe]

    end_keyframe = pv.CameraKeyFrame()
    end_keyframe.KeyTime = end_time
    end_keyframe.Position = position_path_points[-3:]
    end_keyframe.PositionPathPoints = end_keyframe.Position
    end_keyframe.FocalPoint = focal_path_points[-3:]
    end_keyframe.FocalPathPoints = end_keyframe.FocalPoint
    end_keyframe.ViewUp = shot_config['ViewUp']
    end_keyframe.ViewAngle = shot_config['ViewAngle']
    return [path_keyframe, end_keyframe]


def apply_swings(camera_swings_config,
                 scene_time_range,
                 scene_time_from_real,
                 normalized_time_from_scene,
                 camera_animation_track=None):
    # Discard unused shots
    i_shots_start = 0
    i_shots_end = len(camera_swings_config)
    for i, shot in enumerate(camera_swings_config):
        if i > 0:
            assert 'Time' in shot and 'SwingDuration' in shot, "Set the 'Time' when camera shot {} should be shown in scene time and the 'SwingDuration' to the shot in real-time seconds.".format(i)
            if shot['Time'] <= scene_time_range[0]:
                logger.debug("Discarding unused camera shot {} that finishes before animation starts.".format(i - 1))
                i_shots_start = i
            if shot['Time'] - get_scene_time(shot['SwingDuration'], scene_time_from_real) >= scene_time_range[1]:
                logger.debug("Discarding unused camera shots {} and later that are shown after animation ends.".format(i))
                i_shots_end = i
                break
    camera_swings_config = camera_swings_config[i_shots_start:i_shots_end]
    # Try setting a static camera
    if len(camera_swings_config) == 1:
        logger.debug("Only a single camera shot is shown, making it static.")
        apply(camera_config=camera_swings_config[0])
        return
    # Setup key frames
    if camera_animation_track is None:
        camera_animation_track = pv.GetCameraTrack()
    # ParaView's implementation of the interpolation in 'Interpolate Camera'
    # mode leads to oscillations. The 'Path-based' mode's interpolation appears
    # to be more robust.
    camera_animation_track.Mode = 'Path-based'
    camera_key_frames = []
    prev_shot_start_time = 0.
    for i, shot in enumerate(camera_swings_config):
        shot_start_time = shot['Time'] if 'Time' in shot else scene_time_range[0]
        shot_start_time_normalized = normalized_time_from_scene(
            shot_start_time)
        swing_start_time = max(
            prev_shot_start_time, shot_start_time -
            (get_scene_time(shot['SwingDuration'], scene_time_from_real)
             if 'SwingDuration' in shot else 0.))
        swing_start_time_normalized = normalized_time_from_scene(
            swing_start_time)
        if i > 0:
            logger.debug("Camera shot {} starts swinging at {}.".format(
                i, swing_start_time_normalized))
            prev_shot = camera_swings_config[i - 1]
        else:
            prev_shot = None
        logger.debug("Camera shot {} is shown at {}.".format(
            i, shot_start_time_normalized))
        camera_key_frames += make_camera_swing_keyframes(
            shot, swing_start_time_normalized, shot_start_time_normalized,
            prev_shot)
        prev_shot_start_time = shot_start_time
    camera_animation_track.KeyFrames = camera_key_frames
