from textual.containers import Vertical
from textual.widgets import Label, ListItem, ListView, TabbedContent, TabPane


class LibraryItem(ListItem):
    """A playable album or playlist row."""

    def __init__(self, text: str, kind: str, uri: str):
        super().__init__(Label(text, markup=False))
        self.kind = kind
        self.uri = uri


class LibraryWidget(Vertical):
    """Albums and playlists in separate tabs, each with its own list."""

    TABS = ("albums", "playlists")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._lists = {kind: ListView(id=f"{kind}-list") for kind in self.TABS}
        self._tabs = TabbedContent(id="library-tabs")
        self.albums: list[dict] = []
        self.playlists: list[dict] = []

    def compose(self):
        with self._tabs:
            for kind in self.TABS:
                with TabPane(kind, id=f"{kind}-tab"):
                    yield self._lists[kind]

    @property
    def active(self) -> str:
        return self._tabs.active

    def get_tab(self, pane_id: str):
        return self._tabs.get_tab(pane_id)

    # -- data -------------------------------------------------------------

    def set_library(self, albums: list[dict], playlists: list[dict]) -> None:
        self.albums, self.playlists = albums, playlists
        self._fill("albums", [(f"{a['name']} - {a['artists']}", a["uri"]) for a in albums])
        self._fill("playlists", [(p["name"], p["uri"]) for p in playlists])

    def _fill(self, kind: str, rows: list[tuple[str, str]]) -> None:
        list_view = self._lists[kind]
        list_view.clear()
        if rows:
            list_view.extend(LibraryItem(text, kind, uri) for text, uri in rows)
            list_view.index = 0
        else:
            list_view.append(ListItem(Label(f"no {kind}")))
        self.get_tab(f"{kind}-tab").label = f"{kind} {len(rows)}"

    def saved_matches(self, query: str) -> tuple[list[dict], list[dict]]:
        """Saved albums and playlists whose name (or album artist) contains
        `query`, case-insensitively. No API call."""
        q = query.strip().lower()
        if not q:
            return [], []
        albums = [a for a in self.albums if q in a["name"].lower() or q in a["artists"].lower()]
        playlists = [p for p in self.playlists if q in p["name"].lower()]
        return albums, playlists

    # -- navigation -------------------------------------------------------

    @property
    def active_list(self) -> ListView:
        kind = (self.active or "albums-tab").removesuffix("-tab")
        return self._lists[kind]

    def owns(self, list_view: ListView) -> bool:
        return list_view in self._lists.values()

    def switch_tab(self) -> None:
        """Cycle to the next tab and focus its list."""
        current = (self.active or "albums-tab").removesuffix("-tab")
        following = self.TABS[(self.TABS.index(current) + 1) % len(self.TABS)]
        self._tabs.active = f"{following}-tab"
        self.focus_list()

    def focus_list(self) -> None:
        self.active_list.focus()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        # clicking a tab should also move focus to its list so j/k keep working
        self.call_after_refresh(self.focus_list)

    def cursor_down(self) -> None:
        self.active_list.action_cursor_down()

    def cursor_up(self) -> None:
        self.active_list.action_cursor_up()

    def selected_entry(self) -> dict | None:
        """The highlighted album/playlist as {"kind", "uri"}, or None for
        placeholder rows."""
        item = self.active_list.highlighted_child
        if isinstance(item, LibraryItem):
            return {"kind": item.kind, "uri": item.uri}
        return None
