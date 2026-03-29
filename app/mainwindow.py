from textual.app import App
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Label
from textual.binding import Binding

from client.client import Client
from app.nowplaying import NowPlayingWidget
from app.volume import VolumeWidget
from app.queue import QueueWidget

class MainWindow(App):
    CSS = """
    #bottom-bar {
        dock: bottom;
        height: 4;
        layout: horizontal;
        background: #1d2021;
    }
        
    NowPlayingWidget {
        width: 1fr;
        height: 100%;
        padding: 0 1;
        content-align: left top;
        color: #fabd2f;
    }

    VolumeWidget {
        width: auto;
        height: 100%;
        padding: 0 1;
        content-align: right middle;
        color: white;
    }
    
    Footer {
        background: #282828;
        color: white;
    }
    
    #main-content {
        height: 1fr;
        width: 100%; 
    }
    
    #queue-pane {
        height: 1fr;
        width: 100%;
        background: #282828;
    }

    #queue-title {
        padding: 0 1;
        color: #fabd2f;
        text-style: bold;
    }
    
    QueueWidget {
        background: #282828;
        padding: 0 2;
        color: #fbf1c7;
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_playback", "play/pause"),
        Binding("h", "previous", "prev"),
        Binding("l", "skip", "skip"),
        Binding("J", "volume_down", "vol-"),
        Binding("K", "volume_up", "vol+"),
        Binding("^q", "quit", "quit"),
        Binding("j", "cursor_down", "down", show=False),
        Binding("k", "cursor_up", "up", show=False),
        Binding("r", "refresh_context", "refresh", show=False),
    ]

    def __init__(self, client: Client, **kwargs):
        super().__init__(**kwargs)
        self._client = client
        self.now_playing = NowPlayingWidget()
        self.volume_widget = VolumeWidget()
        self.queue_widget = QueueWidget()
        self._last_song_uri: str | None = None

    def compose(self):
        with Vertical(id="queue-pane"):
            yield Label("queue", id="queue-title")
            yield self.queue_widget

        with Horizontal(id="bottom-bar"):
            yield self.now_playing
            yield self.volume_widget
        yield Footer()

    def on_mount(self) -> None:
        self.update_queue()
        self.update_now_playing()
        self.update_volume()
        self.set_interval(1, self.update_now_playing)
        self.set_interval(0.25, self.update_volume)

    def update_now_playing(self):
        song = self._client.get_currently_playing()
        self.now_playing.song = song

        current_uri = song.uri if song else None
        if current_uri != self._last_song_uri:
            self._last_song_uri = current_uri
            self.update_queue()

    def update_queue(self):
        songs = self._client.get_queue()
        self.queue_widget.set_queue(songs)

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