import os
import requests
import tqdm
import logging
from gwpv.scene_configuration import parse_as


def download_data(datasources):
    logger = logging.getLogger(__name__)
    for datasource_name, datasource_config in datasources.items():
        try:
            url, cached_filename = parse_as.remote_file(datasource_config)
        except ValueError:
            continue
        if os.path.exists(cached_filename):
            logger.debug("Found cached {} file '{}' for URL '{}'".format(
                datasource_name, cached_filename, url))
            continue
        logger.info("Downloading {} file at URL '{}' to cache '{}'...".format(
            datasource_name, url, cached_filename))
        os.makedirs(os.path.dirname(cached_filename), exist_ok=True)
        url_response = requests.get(url, stream=True)
        file_size = int(url_response.headers.get('content-length', 0))
        cached_filename_tmp = cached_filename + '_tmp'
        with open(cached_filename_tmp, 'wb') as cached_file, tqdm.tqdm(
                desc="Downloading " + datasource_name,
                total=file_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
        ) as progress:
            for data in url_response.iter_content(chunk_size=1024):
                progress.update(cached_file.write(data))
        os.rename(cached_filename_tmp, cached_filename)
