import time
import logging
import numpy as np
import hashlib
import os
from gwpv.scene_configuration import parse_as


def cached_swsh_grid(size,
                     num_points,
                     spin_weight,
                     ell_max,
                     clip_y_normal,
                     clip_z_normal,
                     cache_dir=None):
    logger = logging.getLogger(__name__)
    X = np.linspace(-size, size, num_points)
    Y = np.linspace(-size, 0, num_points // 2) if clip_y_normal else X
    Z = np.linspace(-size, 0, num_points // 2) if clip_z_normal else X
    x, y, z = map(lambda arr: arr.flatten(order='F'), np.meshgrid(X, Y, Z, indexing='ij'))
    r = np.sqrt(x**2 + y**2 + z**2)
    swsh_grid = None
    if cache_dir:
        swsh_grid_id = (round(float(size),
                              3), int(num_points), int(spin_weight),
                        int(ell_max), bool(clip_y_normal), bool(clip_z_normal))
        # Create a somewhat unique filename
        swsh_grid_hash = int(hashlib.md5(repr(swsh_grid_id).encode('utf-8')).hexdigest(), 16) % 10**8
        swsh_grid_cache_file = os.path.join(
            cache_dir,
            ('swsh_grid_D{}_N{}_'.format(int(size), int(num_points)) +
             str(swsh_grid_hash) + '.npy'))
        if os.path.exists(swsh_grid_cache_file):
            logger.debug("Loading SWSH grid from file '{}'...".format(
                swsh_grid_cache_file))
            swsh_grid = np.load(swsh_grid_cache_file)
        else:
            logger.debug(
                "No SWSH grid file '{}' found.".format(swsh_grid_cache_file))
    if swsh_grid is None:
        logger.info("No cached SWSH grid found, computing now...")
        logger.info("Loading 'spherical' module...")
        import spherical
        import quaternionic
        logger.info("'spherical' module loaded.")
        start_time = time.time()
        th = np.arccos(z / r)
        phi = np.arctan2(y, x)
        angles = quaternionic.array.from_spherical_coordinates(th, phi)
        swsh_grid = spherical.Wigner(ell_max).sYlm(s=spin_weight, R=angles)
        logger.info("SWSH grid computed in {:.3f}s.".format(time.time() -
                                                            start_time))
        if cache_dir:
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            if not os.path.exists(swsh_grid_cache_file):
                np.save(swsh_grid_cache_file, swsh_grid)
                logger.debug("SWSH grid cache saved to file '{}'.".format(
                    swsh_grid_cache_file))
    return swsh_grid, r


def precompute_cached_swsh_grid(scene):
    if 'WaveformToVolume' not in scene:
        return
    config = scene['WaveformToVolume']
    # WARNING: These defaults must match the ones of the `WaveformToVolume`
    # plugin for the cache to be useful
    cached_swsh_grid(size=config.get('Size', 100),
                     num_points=config.get('SpatialResolution', 100),
                     spin_weight=-2,
                     ell_max=config.get('EllMax', 2),
                     clip_y_normal=config.get('ClipYNormal', False),
                     clip_z_normal=config.get('ClipZNormal', False),
                     cache_dir=parse_as.path(
                         scene['Datasources']['SwshCache']))
