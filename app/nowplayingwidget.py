from textual.reactive import reactive
from textual.widgets import Static

from client.song import SongPlayback


class NowPlayingWidget(Static):
    song: reactive[SongPlayback | None] = reactive(None)

    def render(self) -> str:
        if self.song is None:
            return "nothing is playing at the moment"

        progress_sec = self.song.progress // 1000
        duration_sec = self.song.length // 1000

        progress_str = f"{progress_sec // 60}:{progress_sec % 60:02d}"
        duration_str = f"{duration_sec // 60}:{duration_sec % 60:02d}"

        time_part = f"{progress_str} / {duration_str}"
        title_part = self.song.details.title
        artists_part = ", ".join(self.song.details.artists)
        album_part = self.song.details.album

        artist_start_col = len(time_part) + 5

        line1 = f"{time_part}     {title_part}"

        paused = "(paused)" if not self.song.is_playing else ""
        if paused:
            gap = max(1, artist_start_col - len(paused))
            line2 = f"{paused}{' ' * gap}{artists_part}"
        else:
            line2 = f"{' ' * artist_start_col}{artists_part}"

        line3 = f"{' ' * artist_start_col}{album_part}"

        return f"{line1}\n{line2}\n{line3}"