import contextlib
import logging

import paraview.simple as pv

logger = logging.getLogger(__name__)


def num_frames(max_animation_length, animation_speed, frame_rate):
    max_animation_length_in_seconds = max_animation_length / animation_speed
    return int(round(frame_rate * max_animation_length_in_seconds))


def get_scene_time(time_config, scene_time_from_real):
    if isinstance(time_config, dict):
        assert time_config["TimeMode"] in ["Scene", "Real"]
        if time_config["TimeMode"] == "Scene":
            return time_config["Time"]
        elif time_config["TimeMode"] == "Real":
            return scene_time_from_real(time_config["Time"])
    return scene_time_from_real(time_config)


def follow_path(
    gui_name,
    trajectory_data,
    num_keyframes,
    scene_time_range,
    normalized_time_from_scene,
):
    # Crop trajectory data
    trajectory_start_i = 0
    trajectory_end_i = len(trajectory_data)
    for i, traj_t in enumerate(trajectory_data[:, 0]):
        if traj_t < scene_time_range[0]:
            trajectory_start_i = i
        else:
            break
    for i, traj_t in enumerate(trajectory_data[::-1, 0]):
        if traj_t > scene_time_range[1]:
            trajectory_end_i = len(trajectory_data) - i
        else:
            break
    num_traj_datapoints = trajectory_end_i - trajectory_start_i
    logger.debug(
        f"Trajectory data for '{gui_name}' cropped to indices"
        f" ({trajectory_start_i}, {trajectory_end_i}) (that's"
        f" {num_traj_datapoints} data points between times"
        f" {trajectory_data[trajectory_start_i, 0]} and"
        f" {trajectory_data[trajectory_end_i - 1, 0]})."
    )
    assert num_keyframes <= num_traj_datapoints, (
        "Time resolution in trajectory file is not sufficient for"
        f" {num_keyframes} keyframes."
    )
    keep_every_n_traj_sample = int(num_traj_datapoints / num_keyframes)
    logger.debug(
        f"Keeping every {keep_every_n_traj_sample}th/nd/st sample in the"
        " trajectory data."
    )
    trajectory_data = trajectory_data[
        trajectory_start_i:trajectory_end_i:keep_every_n_traj_sample
    ]
    trajectory = list(
        map(
            lambda i: pv.GetAnimationTrack(
                "Center", index=i, proxy=pv.FindSource(gui_name)
            ),
            range(3),
        )
    )
    for i, track in enumerate(trajectory):
        keyframes = []
        for traj_sample in trajectory_data:
            key = pv.CompositeKeyFrame()
            key.KeyTime = normalized_time_from_scene(traj_sample[0])
            key.Interpolation = "Ramp"
            key.KeyValues = [traj_sample[i + 1]]
            keyframes.append(key)
        track.KeyFrames = keyframes


def apply_visibility(
    proxy, config, normalized_time_from_scene, scene_time_from_real
):
    vis_track = pv.GetAnimationTrack("Visibility", proxy=proxy)
    vis_keyframes = []
    for vis_time, vis_value in [
        (config["Start"], False),
        (config["Start"], True),
        (config["End"], True),
        (config["End"], False),
    ]:
        key = pv.CompositeKeyFrame()
        key.KeyTime = normalized_time_from_scene(vis_time)
        key.KeyValues = [vis_value]
        vis_keyframes.append(key)
    vis_track.KeyFrames = vis_keyframes
    if "FadeIn" in config or "FadeOut" in config:
        alpha_track = pv.GetAnimationTrack("Opacity", proxy=proxy)
        alpha_keyframes = []
        if "FadeIn" in config:
            fade_duration = get_scene_time(
                config["FadeIn"], scene_time_from_real
            )
            for alpha_time, alpha_value in [
                (config["Start"], 0.0),
                (config["Start"] + fade_duration, 1.0),
            ]:
                key = pv.CompositeKeyFrame()
                key.KeyTime = normalized_time_from_scene(alpha_time)
                key.KeyValues = [alpha_value]
                alpha_keyframes.append(key)
        if "FadeOut" in config:
            fade_duration = get_scene_time(
                config["FadeOut"], scene_time_from_real
            )
            for alpha_time, alpha_value in [
                (config["End"] - fade_duration, 1.0),
                (config["End"], 0.0),
            ]:
                key = pv.CompositeKeyFrame()
                key.KeyTime = normalized_time_from_scene(alpha_time)
                key.KeyValues = [alpha_value]
                alpha_keyframes.append(key)
        alpha_track.KeyFrames = alpha_keyframes


@contextlib.contextmanager
def restore_animation_state(animation):
    if animation is None:
        try:
            yield
        finally:
            return
    animation_state = (
        animation.StartTime,
        animation.EndTime,
        animation.AnimationTime,
    )
    try:
        yield
    finally:
        animation.StartTime = animation_state[0]
        animation.EndTime = animation_state[1]
        animation.AnimationTime = animation_state[2]


def apply_time_shift(proxy, time_shift_config, animation=None):
    # We sometimes need to restore the animation time after adding the
    # `TemporalShiftScale` because for some reason it is reset
    with restore_animation_state(animation):
        time_shifted_proxy = pv.TemporalShiftScale(
            Input=proxy, **time_shift_config
        )
    return time_shifted_proxy
