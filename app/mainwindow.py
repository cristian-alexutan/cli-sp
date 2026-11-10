import time

from textual import work
from textual.app import App
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Label, ListView, Rule
from textual.binding import Binding

from client.client import Client
from client.song import SongPlayback
from app.nowplayingwidget import NowPlayingWidget
from app.volumewidget import VolumeWidget
from app.queuewidget import QueueWidget
from app.librarywidget import LibraryWidget
from app.searchscreen import SearchScreen

class MainWindow(App):
    CSS_PATH = "mainwindow.tcss"

    BINDINGS = [
        Binding("space", "toggle_playback", "play/pause"),
        Binding("h", "previous", "prev"),
        Binding("l", "skip", "skip"),
        # priority: Textual binds tab to focus-next by default
        Binding("tab", "switch_library_tab", "albums/playlists", priority=True),
        Binding("slash", "open_search", "search"),
        Binding("j", "cursor_down", "down"),
        Binding("k", "cursor_up", "up"),
        Binding("J", "volume_down", "vol-"),
        Binding("K", "volume_up", "vol+"),
        Binding("ctrl+q", "quit", "quit"),
    ]

    ERROR_REPEAT_SEC = 15.0
    # ignore polled volume this long after a local change, so a poll that was
    # already in flight doesn't make the bar jump back
    VOLUME_HOLD_SEC = 1.5

    def __init__(self, client: Client, **kwargs):
        super().__init__(**kwargs)
        self._client = client
        self.now_playing = NowPlayingWidget()
        self.volume_widget = VolumeWidget()
        self.library_widget = LibraryWidget()
        self.queue_widget = QueueWidget()
        self._last_song_uri: str | None = None
        self._last_context_uri: str | None = None
        self._last_error: str | None = None
        self._last_error_time = 0.0
        self._polling = False
        self._volume: int | None = None
        self._volume_hold_until = 0.0
        self._pending_volume: int | None = None
        self._volume_sending = False
        self._client.on_error = self._on_client_error

    def compose(self):
        with Horizontal(id="main-content"):
            with Vertical(id="library-pane"):
                yield Label("library", id="library-title")
                yield self.library_widget

            yield Rule(orientation="vertical")

            with Vertical(id="queue-pane"):
                # markup off: album/playlist names can contain [brackets]
                yield Label("queue", id="queue-title", markup=False)
                yield self.queue_widget

        with Horizontal(id="bottom-bar"):
            yield self.now_playing
            yield self.volume_widget
        yield Footer()

    def on_mount(self) -> None:
        self.load_library()
        self.refresh_queue()
        self.poll_playback()
        self.set_interval(1, self.poll_playback)
        self.library_widget.focus_list()

    # -- errors ------------------------------------------------------------

    def _on_client_error(self, message: str) -> None:
        # client calls run in worker threads; hop to the UI thread
        try:
            self.call_from_thread(self.show_error, message)
        except RuntimeError:
            self.show_error(message)

    def show_error(self, message: str) -> None:
        # polling hits the same error every second; don't spam the same toast
        now = time.monotonic()
        if message == self._last_error and now - self._last_error_time < self.ERROR_REPEAT_SEC:
            return
        self._last_error = message
        self._last_error_time = now
        self.notify(message, severity="error", timeout=5)

    # -- background data loading ------------------------------------------

    def poll_playback(self) -> None:
        if self._polling:
            return  # previous request still in flight
        self._polling = True
        self._fetch_playback()

    @work(thread=True, group="poll")
    def _fetch_playback(self) -> None:
        result = None
        try:
            result = self._client.get_playback()
        finally:
            self.call_from_thread(self._poll_done, result)

    def _poll_done(self, result: tuple[SongPlayback | None, int | None] | None) -> None:
        self._polling = False
        if result is None:
            return  # request failed; keep showing the last known state

        song, volume = result
        self.now_playing.song = song

        if volume is not None and time.monotonic() >= self._volume_hold_until:
            self._volume = volume
            self.volume_widget.volume = volume

        current_uri = song.uri if song else None
        if current_uri != self._last_song_uri:
            self._last_song_uri = current_uri
            self.refresh_queue()

        context_uri = song.context_uri if song else None
        if context_uri != self._last_context_uri:
            self._last_context_uri = context_uri
            self._update_queue_title(context_uri)

    @work(thread=True, exclusive=True, group="context")
    def _update_queue_title(self, context_uri: str | None) -> None:
        name = self._client.get_context_name(context_uri) if context_uri else None
        self.call_from_thread(self._set_queue_title, context_uri, name)

    def _set_queue_title(self, context_uri: str | None, name: str | None) -> None:
        if context_uri != self._last_context_uri:
            return  # playback moved on while we were looking the name up
        self.query_one("#queue-title", Label).update(f"queue - {name}" if name else "queue")

    @work(thread=True, exclusive=True, group="queue")
    def refresh_queue(self) -> None:
        songs = self._client.get_queue()
        if songs is not None:
            self.call_from_thread(self.queue_widget.set_queue, songs)

    @work(thread=True, exclusive=True, group="library")
    def load_library(self) -> None:
        library = self._client.get_library()
        if library is not None:
            self.call_from_thread(self.library_widget.set_library, *library)

    # -- playback control ---------------------------------------------------

    @work(thread=True, group="control")
    def run_command(self, command, *args, refresh_queue: bool = False) -> None:
        """Run a playback command in the background, then refresh the UI."""
        command(*args)
        self.call_from_thread(self.poll_playback)
        if refresh_queue:
            self.call_from_thread(self.refresh_queue)

    def action_toggle_playback(self) -> None:
        self.run_command(self._client.toggle_playback)

    def action_previous(self) -> None:
        self.run_command(self._client.previous_track)

    def action_skip(self) -> None:
        self.run_command(self._client.skip_track)

    def _change_volume(self, delta: int) -> None:
        if self._volume is None:
            return
        self._volume = max(0, min(100, self._volume + delta))
        self._volume_hold_until = time.monotonic() + self.VOLUME_HOLD_SEC
        self.volume_widget.volume = self._volume  # update instantly

        # one request at a time; rapid presses collapse into the latest value
        self._pending_volume = self._volume
        if not self._volume_sending:
            self._volume_sending = True
            self._send_volume(self._pending_volume)

    @work(thread=True, group="volume")
    def _send_volume(self, percent: int) -> None:
        self._client.set_volume(percent)
        self.call_from_thread(self._volume_sent, percent)

    def _volume_sent(self, percent: int) -> None:
        if self._pending_volume != percent:
            self._send_volume(self._pending_volume)  # changed while sending
        else:
            self._volume_sending = False

    def action_volume_up(self) -> None:
        self._change_volume(10)

    def action_volume_down(self) -> None:
        self._change_volume(-10)

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        # main-screen-only keys stay out of the way while the search popup is open
        # (tab is a priority binding, so it would otherwise fire inside the popup)
        if action in ("switch_library_tab", "open_search"):
            return self.screen is self.screen_stack[0]
        return True

    def action_open_search(self) -> None:
        self.push_screen(
            SearchScreen(self._client, self.library_widget, self.run_command),
            callback=lambda _: self.library_widget.focus_list(),
        )

    def action_switch_library_tab(self) -> None:
        self.library_widget.switch_tab()

    def action_cursor_down(self) -> None:
        self.library_widget.cursor_down()

    def action_cursor_up(self) -> None:
        self.library_widget.cursor_up()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not self.library_widget.owns(event.list_view):
            return

        entry = self.library_widget.selected_entry()
        if entry is None:
            return

        if entry["kind"] == "albums":
            self.run_command(self._client.play_album, entry["uri"], refresh_queue=True)
        else:
            self.run_command(self._client.play_playlist_shuffle, entry["uri"], refresh_queue=True)
