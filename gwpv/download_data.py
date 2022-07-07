import logging
import os

import requests
import rich.progress

from gwpv.scene_configuration import parse_as

logger = logging.getLogger(__name__)
progress = rich.progress.Progress(
    "  ",
    rich.progress.BarColumn(),
    rich.progress.DownloadColumn(),
    rich.progress.TransferSpeedColumn(),
    rich.progress.TimeRemainingColumn(),
)


def _download_file(url, filename, task_id):
    url_response = requests.get(url, stream=True)
    file_size = int(url_response.headers.get("content-length", 0))
    filename_tmp = filename + "_tmp"
    progress.update(task_id, total=file_size)
    with open(filename_tmp, "wb") as cached_file, progress:
        progress.start_task(task_id)
        for data in url_response.iter_content(chunk_size=1024):
            progress.update(task_id, advance=cached_file.write(data))
    os.rename(filename_tmp, filename)


def download_data(datasources):
    with progress:
        for datasource_name, datasource_config in datasources.items():
            try:
                url, cached_filename = parse_as.remote_file(datasource_config)
            except ValueError:
                continue
            if os.path.exists(cached_filename):
                logger.debug(
                    f"Found cached {datasource_name} file '{cached_filename}'"
                    f" for URL '{url}'"
                )
                continue
            logger.info(
                f"Downloading {datasource_name} file at URL '{url}' to cache"
                f" '{cached_filename}'..."
            )
            os.makedirs(os.path.dirname(cached_filename), exist_ok=True)
            progress.console.print(
                f"Downloading [bold]{datasource_name}[/bold]"
            )
            task_id = progress.add_task(
                "download",
                start=False,
                datasource_name=datasource_name,
            )
            _download_file(url=url, filename=cached_filename, task_id=task_id)
