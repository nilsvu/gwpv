import hashlib
import os
from urllib.parse import urlparse


def color(config):
    if isinstance(config, list) and len(config) == 3:
        return config
    else:
        raise ValueError(f"Not a color: {config}")


def path(config, relative_to="."):
    assert isinstance(
        config, str
    ), f"Expected file system path but got: {config}"
    if config.startswith("/"):
        return os.path.realpath(config)
    elif config.startswith("~"):
        return os.path.realpath(os.path.expanduser(config))
    else:
        return os.path.realpath(os.path.join(relative_to, config))


def file(config):
    if isinstance(config, str):
        return path(config.split(":"))
    elif "File" in config:
        return path(config["File"])
    else:
        raise ValueError(f"Can't parse as file: {config}")


def remote_file(config):
    if "File" not in config:
        raise ValueError(f"'File' expected in remote file config: {config}")
    url = config["File"]
    if urlparse(url).scheme == "":
        raise ValueError(f"Not a remote URL: {url}")
    assert (
        "Cache" in config
    ), "Provide a 'Cache' directory when specifying a remote file URL."
    # Create a somewhat unique filename for the URL
    hashed_url = int(hashlib.md5(url.encode("utf-8")).hexdigest(), 16) % 10**8
    file_basename = os.path.basename(urlparse(url).path)
    cached_filename = path(
        os.path.join(config["Cache"], str(hashed_url) + "_" + file_basename)
    )
    return url, cached_filename


def file_and_subfile(config):
    try:
        url, cached_filename = remote_file(config)
        return cached_filename, config.get("Subfile", "/")
    except ValueError:
        pass
    if isinstance(config, str):
        file_and_subfile = config.split(":")
        assert len(file_and_subfile) <= 2, (
            "Only one ':' to separate file and subfile is allowed in"
            f" '{config}'."
        )
        if len(file_and_subfile) == 1:
            file_and_subfile.append("/")
        return path(file_and_subfile[0]), file_and_subfile[1]
    elif "File" in config:
        return path(config["File"]), config.get("Subfile", "/")
    else:
        raise ValueError(f"Can't parse as file and subfile: {config}")
