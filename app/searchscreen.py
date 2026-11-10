import asyncio
from typing import Callable

from textual import work
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Footer, Input, Label, ListItem, ListView, TabbedContent, TabPane

from client.client import Client
from app.librarywidget import LibraryWidget

TABS = ("all", "tracks", "albums", "artists", "playlists")
# how many Spotify results of each type the "all" tab shows
ALL_TAB_COUNTS = {"tracks": 3, "albums": 3, "artists": 2, "playlists": 3}
DEBOUNCE_SEC = 0.3
SAVED_MARK = "♥ "
NO_RESULTS = {"tracks": [], "albums": [], "artists": [], "playlists": []}


class ResultItem(ListItem):
    """A playable search result."""

    def __init__(self, text: str, kind: str, uri: str, album_uri: str | None = None, name: str = ""):
        super().__init__(Label(text, markup=False))
        self.text = text
        self.kind = kind            # "track" | "album" | "artist" | "playlist"
        self.uri = uri
        self.album_uri = album_uri  # tracks: the album to keep playing afterwards
        self.item_name = name


class ResultList(ListView):
    BINDINGS = [
        Binding("j", "cursor_down", "down", show=False),
        Binding("k", "cursor_up", "up", show=False),
        Binding("a", "screen.add_to_queue", "add to queue"),
    ]

    def action_cursor_up(self) -> None:
        # moving up past the first result goes back to the search box
        if not self.index:
            self.screen.focus_input()
        else:
            super().action_cursor_up()


def _track_text(t: dict) -> str:
    return f"{t['name']} - {t['artists']}"

def _album_text(a: dict, saved: bool = False) -> str:
    return f"{SAVED_MARK if saved else ''}{a['name']} - {a['artists']}"

def _playlist_text(p: dict, saved: bool = False) -> str:
    owner = f" (by {p['owner']})" if p.get("owner") else ""
    return f"{SAVED_MARK if saved else ''}{p['name']}{owner}"


class SearchScreen(ModalScreen[None]):
    """Popup search: type to search, tab between result types, enter plays."""

    BINDINGS = [
        Binding("escape", "back", "back / close"),
        Binding("tab", "next_tab", "next tab"),
        Binding("down,ctrl+j", "focus_results", "results", show=False),
    ]

    def __init__(self, client: Client, library: LibraryWidget, run_command: Callable, **kwargs):
        super().__init__(**kwargs)
        self._client = client
        self._library = library
        self._run_command = run_command
        self._lists = {tab: ResultList(id=f"search-{tab}-list") for tab in TABS}
        self._tabs = TabbedContent(id="search-tabs")
        self._debounce: Timer | None = None
        self._saved: tuple[list, list] = ([], [])
        self._remote: dict | None = None
        self._artist: dict | None = None  # {"name", "uri"} while in the artist view
        # result lists are redrawn with awaited clear()/extend(); one redraw at a time
        self._render_lock = asyncio.Lock()

    def compose(self):
        with Vertical(id="search-box"):
            yield Input(placeholder="search Spotify: songs, albums, artists, playlists", id="search-input")
            yield Label("", id="search-header", markup=False)  # artist view title
            with self._tabs:
                for tab in TABS:
                    with TabPane(tab, id=f"search-{tab}-tab"):
                        yield self._lists[tab]
            yield Footer()

    async def on_mount(self) -> None:
        self._set_header("")
        self.focus_input()
        await self._show_hint("type to search")

    # -- focus / navigation -----------------------------------------------

    @property
    def _input(self) -> Input:
        return self.query_one("#search-input", Input)

    def _active_tab(self) -> str:
        return (self._tabs.active or "search-all-tab").removeprefix("search-").removesuffix("-tab")

    def _active_list(self) -> ResultList:
        return self._lists[self._active_tab()]

    def _set_header(self, text: str) -> None:
        header = self.query_one("#search-header", Label)
        header.update(text)
        header.display = bool(text)

    def focus_input(self) -> None:
        self._input.focus()

    def action_focus_results(self) -> None:
        results = self._active_list()
        if any(isinstance(child, ResultItem) for child in results.children):
            results.focus()
            if results.index is None:
                results.index = 0

    def action_next_tab(self) -> None:
        tabs = self._visible_tabs()
        current = self._active_tab()
        following = tabs[(tabs.index(current) + 1) % len(tabs)] if current in tabs else tabs[0]
        self._tabs.active = f"search-{following}-tab"
        if not self._input.has_focus:
            self.call_after_refresh(self.action_focus_results)

    def _visible_tabs(self) -> list[str]:
        return ["tracks", "albums"] if self._artist else list(TABS)

    async def action_back(self) -> None:
        if self._artist is not None:
            await self._leave_artist()
            self.action_focus_results()
        else:
            self.dismiss()

    async def _leave_artist(self) -> None:
        self._artist = None
        for tab in ("all", "artists", "playlists"):
            self._tabs.show_tab(f"search-{tab}-tab")
        self._tabs.active = "search-artists-tab"
        self._set_header("")
        await self._render_results()

    # -- searching --------------------------------------------------------

    async def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.strip()

        if self._debounce is not None:
            self._debounce.stop()
        self._remote = None

        if self._artist is not None:
            await self._leave_artist()

        if not query:
            self._saved = ([], [])
            await self._show_hint("type to search")
            return

        # saved library matches are instant; Spotify results follow after a pause
        self._saved = self._library.saved_matches(query)
        self._debounce = self.set_timer(DEBOUNCE_SEC, lambda: self._search(query))
        await self._render_results(loading=True)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_focus_results()

    @work(thread=True, exclusive=True, group="search")
    def _search(self, query: str) -> None:
        results = self._client.search(query)
        self.app.call_from_thread(self._search_done, query, results)

    async def _search_done(self, query: str, results: dict | None) -> None:
        if query != self._input.value.strip() or self._artist is not None:
            return  # out of date: the user kept typing or opened an artist
        self._remote = results or NO_RESULTS
        await self._render_results()

    # -- rendering --------------------------------------------------------
    # clear() removes rows asynchronously: highlighting before it finishes
    # would mark an outgoing row, so every redraw awaits it (under the lock).

    async def _show_hint(self, text: str) -> None:
        async with self._render_lock:
            for tab, results in self._lists.items():
                await results.clear()
                await results.append(ListItem(Label(text)))
                self._tabs.get_tab(f"search-{tab}-tab").label = tab

    async def _fill(self, tab: str, rows: list[ResultItem], loading: bool) -> None:
        """Replace a tab's rows and highlight the first. Hold the render lock."""
        results = self._lists[tab]
        await results.clear()
        if rows:
            await results.extend(rows)
            results.index = 0
        else:
            await results.append(ListItem(Label("searching..." if loading else "no results")))
        self._tabs.get_tab(f"search-{tab}-tab").label = f"{tab} {len(rows)}" if rows or not loading else tab

    async def _render_results(self, loading: bool = False) -> None:
        async with self._render_lock:
            await self._render_results_locked(loading)

    async def _render_results_locked(self, loading: bool) -> None:
        saved_albums, saved_playlists = self._saved
        remote = self._remote or NO_RESULTS
        saved_uris = {a["uri"] for a in saved_albums} | {p["uri"] for p in saved_playlists}

        def tracks(rows):
            return [ResultItem(_track_text(t), "track", t["uri"], t["album_uri"]) for t in rows]

        def albums(rows, saved=False):
            return [ResultItem(_album_text(a, saved), "album", a["uri"]) for a in rows]

        def artists(rows):
            return [ResultItem(a["name"], "artist", a["uri"], name=a["name"]) for a in rows]

        def playlists(rows, saved=False):
            return [ResultItem(_playlist_text(p, saved), "playlist", p["uri"]) for p in rows]

        remote_albums = [a for a in remote["albums"] if a["uri"] not in saved_uris]
        remote_playlists = [p for p in remote["playlists"] if p["uri"] not in saved_uris]
        n = ALL_TAB_COUNTS

        await self._fill("all",
                         albums(saved_albums, True) + playlists(saved_playlists, True)
                         + tracks(remote["tracks"][:n["tracks"]])
                         + albums(remote_albums[:n["albums"]])
                         + artists(remote["artists"][:n["artists"]])
                         + playlists(remote_playlists[:n["playlists"]]),
                         loading)
        await self._fill("tracks", tracks(remote["tracks"]), loading)
        await self._fill("albums", albums(saved_albums, True) + albums(remote_albums), loading)
        await self._fill("artists", artists(remote["artists"]), loading)
        await self._fill("playlists", playlists(saved_playlists, True) + playlists(remote_playlists), loading)

    # -- artist view ------------------------------------------------------

    async def _open_artist(self, item: ResultItem) -> None:
        self._artist = {"name": item.item_name, "uri": item.uri}
        self._set_header(f"artist: {item.item_name}  (esc to go back)")
        for tab in ("all", "artists", "playlists"):
            self._tabs.hide_tab(f"search-{tab}-tab")
        self._tabs.active = "search-tracks-tab"
        self._load_artist(item.uri, item.item_name)
        async with self._render_lock:
            await self._fill("tracks", [], loading=True)
            await self._fill("albums", [], loading=True)

    @work(thread=True, exclusive=True, group="search")
    def _load_artist(self, uri: str, name: str) -> None:
        view = self._client.get_artist_view(uri, name)
        self.app.call_from_thread(self._artist_done, uri, view)

    async def _artist_done(self, uri: str, view: dict | None) -> None:
        if self._artist is None or self._artist["uri"] != uri:
            return
        view = view or {"tracks": [], "albums": []}
        async with self._render_lock:
            if self._artist is None or self._artist["uri"] != uri:
                return  # user left the artist view while we waited for the lock
            await self._fill("tracks", [ResultItem(_track_text(t), "track", t["uri"], t["album_uri"])
                                        for t in view["tracks"]], False)
            await self._fill("albums", [ResultItem(_album_text(a), "album", a["uri"])
                                        for a in view["albums"]], False)
        self.action_focus_results()

    # -- actions ----------------------------------------------------------

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if not isinstance(item, ResultItem):
            return

        if item.kind == "artist":
            await self._open_artist(item)
            return

        if item.kind == "track":
            self._run_command(self._client.play_track_in_album, item.uri, item.album_uri, refresh_queue=True)
        elif item.kind == "album":
            self._run_command(self._client.play_album, item.uri, refresh_queue=True)
        else:
            self._run_command(self._client.play_playlist_shuffle, item.uri, refresh_queue=True)
        self.dismiss()

    def action_add_to_queue(self) -> None:
        item = self._active_list().highlighted_child
        if not isinstance(item, ResultItem) or item.kind != "track":
            self.notify("Only tracks can be added to the queue", severity="warning", timeout=3)
            return
        self._queue(item.uri, item.text)

    @work(thread=True, group="queue-add")
    def _queue(self, uri: str, text: str) -> None:
        # own worker (not run_command) so the toast only appears once Spotify confirms
        if self._client.add_to_queue(uri):
            self.app.call_from_thread(self.notify, f"Added to queue: {text}", timeout=3)
            self.app.call_from_thread(self.app.refresh_queue)
