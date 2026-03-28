from textual.reactive import reactive
from textual.widgets import Static

from client.client import Song

class NowPlayingWidget(Static):
    song: reactive[Song | None] = reactive(None)

    def render(self) -> str:
        if self.song is None:
            return "nothing is playing at the moment"

        progress_sec = self.song.timestamp // 1000
        duration_sec = self.song.length // 1000

        progress_str = f"{progress_sec // 60}:{progress_sec % 60:02d}"
        duration_str = f"{duration_sec // 60}:{duration_sec % 60:02d}"

        time_part = f"{progress_str} / {duration_str}"
        song_part = f"{self.song.title} - "
        artist_part = ', '.join(self.song.artists)

        line1 = f"{time_part} {song_part}{artist_part}"

        artist_start_col = len(time_part) + 1

        status = "(paused)" if not self.song.is_playing else ""

        if status:
            gap = max(1, artist_start_col - len(status))
            line2 = f"{status}{' ' * gap}{self.song.album}"
        else:
            line2 = f"{' ' * artist_start_col}{self.song.album}"

        return f"{line1}\n{line2}"