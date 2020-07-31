import os
import logging
import requests
import tqdm
import hashlib
from urllib.parse import urlparse


def path(config, relative_to='.'):
    assert isinstance(config, str), "Expected file system path but got: {}".format(config)
    if config.startswith('/'):
        return os.path.realpath(config)
    elif config.startswith('~'):
        return os.path.realpath(os.path.expanduser(config))
    else:
        return os.path.realpath(os.path.join(relative_to, config))


def download_and_cache(url, cache_dir):
    logger = logging.getLogger(__name__)
    # Create a somewhat unique filename for the URL
    hashed_url = int(hashlib.md5(url.encode('utf-8')).hexdigest(), 16) % 10**8
    file_basename = os.path.basename(urlparse(url).path)
    cached_filename = path(os.path.join(cache_dir, str(hashed_url) + '_' + file_basename))
    if not os.path.exists(cached_filename):
        logger.info("Downloading file at URL '{}' to cache '{}'...".format(url, cached_filename))
        os.makedirs(os.path.dirname(cached_filename), exist_ok=True)
        url_response = requests.get(url, stream=True)
        file_size = int(url_response.headers.get('content-length', 0))
        cached_filename_tmp = cached_filename + '_tmp'
        with open(cached_filename_tmp, 'wb') as cached_file, tqdm.tqdm(
                desc="Downloading '" + file_basename + "'",
                total=file_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
        ) as progress:
            for data in url_response.iter_content(chunk_size=1024):
                progress.update(cached_file.write(data))
        os.rename(cached_filename_tmp, cached_filename)
    else:
        logger.debug("Found cached file '{}' for URL '{}'".format(cached_filename, url))
    return cached_filename


def file_and_subfile(config):
    file_and_subfile = None
    if isinstance(config, str):
        file_and_subfile = config.split(':')
        assert len(
            file_and_subfile
        ) <= 2, "Only one ':' to separate file and subfile is allowed in ''.".format(
            config)
        if len(file_and_subfile) == 1:
            file_and_subfile.append("/")
    elif 'File' in config:
        file_and_subfile = [config['File'], config.get('Subfile', '/')]
    else:
        raise ValueError("Can't parse as file and subfile: " + repr(config))
    if urlparse(file_and_subfile[0]).scheme == '':
        file_and_subfile[0] = path(file_and_subfile[0])
    else:
        assert 'Cache' in config, "Provide a 'Cache' directory when specifying a remote file URL."
        file_and_subfile[0] = download_and_cache(file_and_subfile[0], cache_dir=config['Cache'])
    return tuple(file_and_subfile)
