import os
import subprocess

import rich.progress


def render_movie(output_filename, frames_dir, frame_rate):
    with rich.progress.Progress(
        rich.progress.TextColumn("[progress.description]{task.description}"),
        rich.progress.SpinnerColumn(
            spinner_name="simpleDots", finished_text="... done."
        ),
    ) as progress:
        task_id = progress.add_task("Rendering movie", total=1)
        proc = subprocess.run(
            [
                "ffmpeg",
                "-vcodec",
                "png",
                "-framerate",
                str(frame_rate),
                "-i",
                os.path.join(frames_dir, r"frame.%06d.png"),
                "-pix_fmt",
                "yuv420p",
                "-vcodec",
                "libx264",
                "-crf",
                "17",
                "-threads",
                "0",
                "-preset",
                "slow",
                "-y",
                output_filename + ".mp4",
            ],
            capture_output=True,
            check=True,
        )
        progress.update(task_id, completed=1)
