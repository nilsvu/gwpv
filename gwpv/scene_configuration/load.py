import logging
import os
import sys

import yaml

from .defaults import apply_defaults

if sys.version_info >= (3, 10):
    from importlib.resources import as_file, files
else:
    from importlib_resources import as_file, files

logger = logging.getLogger(__name__)


def apply_partial_overrides(config, partial_config):
    if isinstance(partial_config, list):
        for element_config in partial_config:
            if "Element" in element_config:
                replace_element = element_config["Element"]
                del element_config["Element"]
                logger.debug(
                    "Applying nested partial override for list element"
                    f" {replace_element}..."
                )
                apply_partial_overrides(config[replace_element], element_config)
            elif "Append" in element_config:
                config.append(element_config["Append"])
            else:
                assert False, f"Invalid list override: {element_config}"
        return
    assert isinstance(partial_config, dict), (
        f"Invalid 'partial_config' type {type(partial_config)}. Must be either"
        " dict or list."
    )
    # `partial_config` is a dict. Its keys either forward further into
    # nested dicts or match one of the keywords below.
    for key in partial_config:
        if key == "Replace":
            for replace_key in partial_config[key]:
                replace_value = partial_config[key][replace_key]
                logger.debug(f"Replacing '{replace_key}' with: {replace_value}")
                config[replace_key] = replace_value
        elif key == "Delete":
            if isinstance(partial_config[key], str):
                if partial_config[key] in config:
                    del config[partial_config[key]]
            else:
                for delete_key in partial_config[key]:
                    if delete_key in config:
                        del config[delete_key]
        elif key == "ReplaceElement":
            replace_element = partial_config[key]["Element"]
            replace_value = partial_config[key]["With"]
            logger.debug(
                f"Replacing list element {replace_element} with:"
                f" {replace_value}"
            )
            config[replace_element] = replace_value
        elif key == "AppendElements":
            append_values = partial_config[key]
            logger.debug(f"Append list elements: {append_values}")
            config += append_values
        else:
            logger.debug(f"Applying nested partial override for key '{key}'...")
            if key not in config:
                config[key] = {}
            apply_partial_overrides(config[key], partial_config[key])


def apply_keypath_overrides(scene, keypath_overrides):
    for override in keypath_overrides:
        config = scene
        keys = override[0].split(".")
        for key in keys[:-1]:
            config = config[key]
        config[keys[-1]] = yaml.safe_load(override[1])


def find_scene_file_without_extension(scene_file):
    logger.debug(f"Looking for scene file: '{scene_file}[.y[a]ml]'")
    if os.path.exists(scene_file):
        return os.path.realpath(scene_file)
    if os.path.exists(scene_file + ".yaml"):
        return os.path.realpath(scene_file + ".yaml")
    if os.path.exists(scene_file + ".yml"):
        return os.path.realpath(scene_file + ".yml")
    raise LookupError(f"No scene file found for '{scene_file}'.")


def find_scene_file(scene_file, paths=[]):
    try:
        found_scene_file = find_scene_file_without_extension(scene_file)
        found_path = os.path.dirname(found_scene_file)
        if found_path not in paths:
            paths.append(found_path)
        return found_scene_file
    except LookupError:
        for path in paths:
            try:
                return find_scene_file(os.path.join(path, scene_file), [])
            except LookupError:
                continue
        raise LookupError(
            f"No scene file '{scene_file}' found in paths: {paths}"
        )


def load_composition(scene_files, paths=[]):
    composition = []
    for scene_file in scene_files:
        if ":" in scene_file:
            scene_file, scene_name_in_file = scene_file.split(":")
            logger.debug(
                f"Looking for scene '{scene_name_in_file}' in file"
                f" '{scene_file}'."
            )
            found_scene_file = find_scene_file(scene_file, paths)
            scenes_from_file = yaml.safe_load(open(found_scene_file, "r"))[
                "Scenes"
            ]
            found_scenes_in_file = list(
                filter(
                    lambda s: s["Name"] == scene_name_in_file, scenes_from_file
                )
            )
            assert len(found_scenes_in_file) == 1, (
                f"Expected exactly one scene named '{scene_name_in_file}' in"
                f" file '{found_scene_file}' but found {found_scenes_in_file}."
            )
            scene_composition = found_scenes_in_file[0]["Composition"]
            logger.debug(
                f"Found composition for scene '{scene_name_in_file}':"
                f" {scene_composition}"
            )
            composition += load_composition(scene_composition, paths)
        else:
            composition.append(scene_file)
            logger.debug(f"Extracting includes for scene '{scene_file}'.")
            found_scene_file = find_scene_file(scene_file, paths)
            logger.debug(f"Found scene file: '{found_scene_file}'")
            scene_from_file = yaml.safe_load(open(found_scene_file, "r"))
            if "Include" in scene_from_file:
                logger.debug(
                    f"Includes for scene '{scene_file}':"
                    f" {scene_from_file['Include']}"
                )
                composition += scene_from_file["Include"]
    return composition


def load_scene(scene_files, keypath_overrides=None, paths=[]):
    default_scene_path_resource = as_file(files("gwpv") / "scene_overrides")
    default_scene_path = default_scene_path_resource.__enter__()
    if default_scene_path not in paths:
        paths.append(default_scene_path)
    composition = load_composition(scene_files, paths)
    logger.debug(f"Loading scene composition: {composition}")
    scene = None
    for scene_file in composition:
        logger.debug(f"Loading scene file: '{scene_file}'")
        found_scene_file = find_scene_file(scene_file, paths)
        logger.debug(f"Found scene file: '{found_scene_file}'")
        scene_from_file = yaml.safe_load(open(found_scene_file, "r"))
        if scene is None:
            if "Base" in scene_from_file:
                base = scene_from_file["Base"]
                del scene_from_file["Base"]
                logger.debug(f"Loading base: {base}")
                scene = load_scene(
                    base, paths=paths + [os.path.dirname(found_scene_file)]
                )
                logger.debug(
                    f"Applying partial override to base {base}:"
                    f" {scene_from_file}"
                )
                apply_partial_overrides(scene, scene_from_file)
                logger.debug(f"Overridden base {base}: {scene}")
            else:
                scene = scene_from_file
        else:
            if "Base" in scene_from_file:
                logger.debug(
                    f"Ignoring base {scene_from_file['Base']} in nested"
                    f" override '{scene_file}'."
                )
                del scene_from_file["Base"]
            logger.debug(f"Applying partial override: {scene_from_file}")
            apply_partial_overrides(scene, scene_from_file)
            logger.debug(f"Overriden scene: {scene}")
    if keypath_overrides is not None:
        logger.debug(f"Applying keypath overrides: {keypath_overrides}")
        apply_keypath_overrides(scene, keypath_overrides)
        logger.debug(f"Overriden scene: {scene}")
    apply_defaults(scene)
    default_scene_path_resource.__exit__(None, None, None)
    return scene
