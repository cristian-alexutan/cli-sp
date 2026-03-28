from textual.app import App
from textual.widgets import Footer, Static
from textual.binding import Binding
from textual.reactive import reactive

from client.client import Client, Song

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


class MainWindow(App):
    CSS = """
    NowPlayingWidget {
        dock: bottom;
        height: 4; 
    }
    """

    BINDINGS = [
        Binding("space", "toggle_playback", "play/pause"),
        Binding("h", "previous", "prev"),
        Binding("l", "skip", "skip"),
        Binding("j", "volume_down", "vol-"),
        Binding("k", "volume_up", "vol+"),
        Binding("^q", "quit", "quit"),
    ]

    def __init__(self, client: Client, **kwargs):
        super().__init__(**kwargs)
        self._client = client
        self.now_playing = NowPlayingWidget()

    def compose(self):
        yield self.now_playing
        yield Footer()

    def on_mount(self) -> None:
        self.update_now_playing()
        self.set_interval(1, self.update_now_playing)

    def update_now_playing(self):
        self.now_playing.song = self._client.get_currently_playing()

    def action_toggle_playback(self) -> None:
        self._client.toggle_playback()

    def action_previous(self) -> None:
        self._client.previous_track()

    def action_skip(self) -> None:
        self._client.skip_track()

    def action_volume_up(self) -> None:
        self._client.volume_up()

    def action_volume_down(self) -> None:
        self._client.volume_down()