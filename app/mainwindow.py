from textual.app import App
from textual.widgets import Footer
from textual.binding import Binding

from client.client import Client

class MainWindow(App):
    BINDINGS = [
        Binding("space", "toggle_playback", "play/pause"),
        Binding("h", "previous", "prev"),
        Binding("l", "skip", "skip"),
        Binding("^q", "quit", "quit"),
    ]

    def __init__(self, client: Client, **kwargs):
        super().__init__(**kwargs)
        self._client = client

    def compose(self):
        yield Footer()

    def action_toggle_playback(self) -> None:
        self._client.toggle_playback()

    def action_previous(self) -> None:
        self._client.previous_track()

    def action_skip(self) -> None:
        self._client.skip_track()