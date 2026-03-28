from textual.app import App
from textual.containers import Horizontal
from textual.widgets import Footer
from textual.binding import Binding

from client.client import Client, Song
from app.nowplaying import NowPlayingWidget
from app.volume import VolumeWidget

class MainWindow(App):
    CSS = """
    #bottom-bar {
        dock: bottom;
        height: 4;
        layout: horizontal;
        background: #3c3836;
        color: #fbf1c7
    }
        
    NowPlayingWidget {
        width: 1fr;
        height: 100%;
        padding: 0 1;
        content-align: left top;
    }

    VolumeWidget {
        width: auto;
        height: 100%;
        padding: 0 1;
        content-align: right middle;
    }
    
    Footer {
        background: #282828;
        color: white;
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
        self.volume_widget = VolumeWidget()

    def compose(self):
        with Horizontal(id="bottom-bar"):
            yield self.now_playing
            yield self.volume_widget
        yield Footer()

    def on_mount(self) -> None:
        self.update_now_playing()
        self.update_volume()
        self.set_interval(1, self.update_now_playing)
        self.set_interval(0.25, self.update_volume)

    def update_now_playing(self):
        self.now_playing.song = self._client.get_currently_playing()

    def update_volume(self):
        self.volume_widget.volume = self._client.get_volume_percent()

    def action_toggle_playback(self) -> None:
        self._client.toggle_playback()
        self.update_now_playing()

    def action_previous(self) -> None:
        self._client.previous_track()
        self.update_now_playing()

    def action_skip(self) -> None:
        self._client.skip_track()
        self.update_now_playing()

    def action_volume_up(self) -> None:
        self._client.volume_up()
        self.update_volume()

    def action_volume_down(self) -> None:
        self._client.volume_down()
        self.update_volume()