import logging

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    Task,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.text import Text


class RenderSpeedColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        speed = task.finished_speed or task.speed
        if speed is None:
            return Text("?", style="progress.data.speed")
        return Text(f"{1/speed:.2f}s/frame", style="progress.data.speed")


render_progress = Progress(
    TextColumn("[progress.description]{task.description}"),
    TaskProgressColumn(),
    BarColumn(bar_width=None),
    MofNCompleteColumn(),
    RenderSpeedColumn(),
    TimeRemainingColumn(),
)
