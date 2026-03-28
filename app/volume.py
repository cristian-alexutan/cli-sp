from textual.widgets import Static
from textual.reactive import reactive
from rich.align import Align

class VolumeWidget(Static):
    volume: reactive[int] = reactive(0)

    def render(self) -> Align:
        blocks = 10
        filled = self.volume // 10
        bar = "█" * filled + "░" * (blocks - filled)
        text = f"vol |{bar}| {self.volume:>3d}%"
        return Align.right(text)