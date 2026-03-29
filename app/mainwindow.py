from textual.app import App
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Label, ListView, Rule
from textual.binding import Binding

from client.client import Client
from app.nowplayingwidget import NowPlayingWidget
from app.volumewidget import VolumeWidget
from app.queuewidget import QueueWidget
from app.librarywidget import LibraryWidget

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
        color: #689d6a;
    }

    VolumeWidget {
        width: auto;
        height: 100%;
        padding: 0 1;
        content-align: right middle;
        color: #fbf1c7;
    }
    
    #main-content {
        height: 1fr;
        width: 100%;
        layout: horizontal;
    }
    
    #library-pane {
        width: 35%;
        height: 100%;
        background: #282828;
    }
    
    #queue-pane {
        width: 65%;
        height: 100%;
        background: #282828;
    }   
    
    #library-title, #queue-title {
        width: 100%;
        height: 1;
        padding: 0 1;
        color: #689d6a;
        text-style: bold;
        background: #1d2021;
    }
    
    LibraryWidget {
        height: 1fr;
        padding: 0 1;
        color: #fbf1c7;
        scrollbar-size: 0 0;
    }
    
    LibraryWidget > ListItem {
        color: #fbf1c7;
        background: #282828;
    }
    
    LibraryWidget > ListItem.-highlight {
        background: transparent;
        color: #8ec07c;
    }
    
    QueueWidget {
        padding: 0 2;
        color: #fbf1c7;
        scrollbar-size: 0 0;
    }
    
    Rule {
        color: #504945;
        margin: 0;
    }
    
    Footer {
        background: #8ec07c;
    }

    FooterKey .footer-key--key {
        color: #1d2021;
    }

    FooterKey .footer-key--description {
        color: #282828;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_playback", "play/pause"),
        Binding("h", "previous", "prev"),
        Binding("l", "skip", "skip"),
        Binding("j", "cursor_down", "down"),
        Binding("k", "cursor_up", "up"),
        Binding("J", "volume_down", "vol-"),
        Binding("K", "volume_up", "vol+"),
        Binding("^q", "quit", "quit"),
    ]

    def __init__(self, client: Client, **kwargs):
        super().__init__(**kwargs)
        self._client = client
        self.now_playing = NowPlayingWidget()
        self.volume_widget = VolumeWidget()
        self.library_widget = LibraryWidget()
        self.queue_widget = QueueWidget()
        self._last_song_uri: str | None = None

    def compose(self):
        with Horizontal(id="main-content"):
            with Vertical(id="library-pane"):
                yield Label("library", id="library-title")
                yield self.library_widget

            yield Rule(orientation="vertical")

            with Vertical(id="queue-pane"):
                yield Label("queue", id="queue-title")
                yield self.queue_widget

        with Horizontal(id="bottom-bar"):
            yield self.now_playing
            yield self.volume_widget
        yield Footer()

    def on_mount(self) -> None:
        self.update_library()
        self.update_queue()
        self.update_now_playing()
        self.update_volume()
        self.set_interval(1, self.update_now_playing)
        self.set_interval(0.25, self.update_volume)
        self.set_focus(self.library_widget)

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

    def update_library(self):
        albums, playlists = self._client.get_library()
        self.library_widget.set_library(albums, playlists)

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

    def action_cursor_down(self) -> None:
        self.library_widget.action_cursor_down()

    def action_cursor_up(self) -> None:
        self.library_widget.action_cursor_up()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view is not self.library_widget:
            return

        played = self.library_widget.play_selected(self._client)
        if played:
            self.update_now_playing()
            self.update_queue()