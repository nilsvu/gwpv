import yaml
import logging
import os
from .defaults import apply_defaults
import sys
if sys.version_info >= (3, 10):
    from importlib.resources import files, as_file
else:
    from importlib_resources import files, as_file

logger = logging.getLogger(__name__)


def apply_partial_overrides(config, partial_config):
    if isinstance(partial_config, list):
        for element_config in partial_config:
            if 'Element' in element_config:
                replace_element = element_config['Element']
                del element_config['Element']
                logger.debug(
                    "Applying nested partial override for list element {}...".
                    format(replace_element))
                apply_partial_overrides(config[replace_element], element_config)
            elif 'Append' in element_config:
                config.append(element_config['Append'])
            else:
                assert False, "Invalid list override: {}".format(element_config)
        return
    assert isinstance(partial_config, dict), "Invalid 'partial_config' type {}. Must be either dict or list.".format(type(partial_config))
    # `partial_config` is a dict. Its keys either forward further into
    # nested dicts or match one of the keywords below.
    for key in partial_config:
        if key == 'Replace':
            for replace_key in partial_config[key]:
                replace_value = partial_config[key][replace_key]
                logger.debug("Replacing '{}' with: {}".format(
                    replace_key, replace_value))
                config[replace_key] = replace_value
        elif key == 'Delete':
            if isinstance(partial_config[key], str):
                if partial_config[key] in config:
                    del config[partial_config[key]]
            else:
                for delete_key in partial_config[key]:
                    if delete_key in config:
                        del config[delete_key]
        elif key == 'ReplaceElement':
            replace_element = partial_config[key]['Element']
            replace_value = partial_config[key]['With']
            logger.debug("Replacing list element {} with: {}".format(
                    replace_element, replace_value))
            config[replace_element] = replace_value
        elif key == 'AppendElements':
            append_values = partial_config[key]
            logger.debug("Append list elements: {}".format(append_values))
            config += append_values
        else:
            logger.debug(
                "Applying nested partial override for key '{}'...".format(key))
            if key not in config:
                config[key] = {}
            apply_partial_overrides(config[key], partial_config[key])


def apply_keypath_overrides(scene, keypath_overrides):
    for override in keypath_overrides:
        config = scene
        keys = override[0].split('.')
        for key in keys[:-1]:
            config = config[key]
        config[keys[-1]] = yaml.safe_load(override[1])


def find_scene_file_without_extension(scene_file):
    logger.debug("Looking for scene file: '{}[.y[a]ml]'".format(scene_file))
    if os.path.exists(scene_file):
        return os.path.realpath(scene_file)
    if os.path.exists(scene_file + '.yaml'):
        return os.path.realpath(scene_file + '.yaml')
    if os.path.exists(scene_file + '.yml'):
        return os.path.realpath(scene_file + '.yml')
    raise LookupError("No scene file found for '{}'.".format(scene_file))


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
        raise LookupError("No scene file '{}' found in paths: {}".format(
            scene_file, paths))


def load_composition(scene_files, paths=[]):
    composition = []
    for scene_file in scene_files:
        if ':' in scene_file:
            scene_file, scene_name_in_file = scene_file.split(':')
            logger.debug("Looking for scene '{}' in file '{}'.".format(scene_name_in_file, scene_file))
            found_scene_file = find_scene_file(scene_file, paths)
            scenes_from_file = yaml.safe_load(open(found_scene_file, 'r'))['Scenes']
            found_scenes_in_file = list(filter(lambda s: s['Name'] == scene_name_in_file, scenes_from_file))
            assert len(found_scenes_in_file) == 1, "Expected exactly one scene named '{}' in file '{}' but found {}.".format(scene_name_in_file, found_scene_file, len(found_scenes_in_file))
            scene_composition = found_scenes_in_file[0]['Composition']
            logger.debug("Found composition for scene '{}': {}".format(scene_name_in_file, scene_composition))
            composition += load_composition(scene_composition, paths)
        else:
            composition.append(scene_file)
            logger.debug("Extracting includes for scene '{}'.".format(scene_file))
            found_scene_file = find_scene_file(scene_file, paths)
            logger.debug("Found scene file: '{}'".format(found_scene_file))
            scene_from_file = yaml.safe_load(open(found_scene_file, 'r'))
            if 'Include' in scene_from_file:
                logger.debug("Includes for scene '{}': {}".format(
                    scene_file, scene_from_file['Include']))
                composition += scene_from_file['Include']
    return composition


def load_scene(scene_files, keypath_overrides=None, paths=[]):
    default_scene_path_resource = as_file(files('gwpv') / 'scene_overrides')
    default_scene_path = default_scene_path_resource.__enter__()
    if default_scene_path not in paths:
        paths.append(default_scene_path)
    composition = load_composition(scene_files, paths)
    logger.debug("Loading scene composition: {}".format(composition))
    scene = None
    for scene_file in composition:
        logger.debug("Loading scene file: '{}'".format(scene_file))
        found_scene_file = find_scene_file(scene_file, paths)
        logger.debug("Found scene file: '{}'".format(found_scene_file))
        scene_from_file = yaml.safe_load(open(found_scene_file, 'r'))
        if scene is None:
            if 'Base' in scene_from_file:
                base = scene_from_file['Base']
                del scene_from_file['Base']
                logger.debug("Loading base: {}".format(base))
                scene = load_scene(base,
                                   paths=paths + [os.path.dirname(found_scene_file)])
                logger.debug("Applying partial override to base {}: {}".format(
                    base, scene_from_file))
                apply_partial_overrides(scene, scene_from_file)
                logger.debug("Overriden base {}: {}".format(base, scene))
            else:
                scene = scene_from_file
        else:
            if 'Base' in scene_from_file:
                logger.debug("Ignoring base {} in nested override '{}'.".format(
                    scene_from_file['Base'], scene_file))
                del scene_from_file['Base']
            logger.debug("Applying partial override: {}".format(scene_from_file))
            apply_partial_overrides(scene, scene_from_file)
            logger.debug("Overriden scene: {}".format(scene))
    if keypath_overrides is not None:
        logger.debug("Applying keypath overrides: {}".format(keypath_overrides))
        apply_keypath_overrides(scene, keypath_overrides)
        logger.debug("Overriden scene: {}".format(scene))
    apply_defaults(scene)
    default_scene_path_resource.__exit__(None, None, None)
    return scene
