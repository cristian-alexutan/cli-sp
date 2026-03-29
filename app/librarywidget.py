from textual.widgets import Label, ListItem, ListView

class LibraryWidget(ListView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._entries: list[dict] = []
        self._row_to_entry_index: dict[int, int] = {}

    def set_library(self, albums: list[dict], playlists: list[dict]) -> None:
        self.clear()
        self._entries = []
        self._row_to_entry_index = {}

        row = 0

        self.append(ListItem(Label("==== albums ====")))
        row += 1

        if albums:
            for album in albums:
                text = f"{album['name']} - {album['artists']}"
                entry_index = len(self._entries)
                self._entries.append({"kind": "album", "uri": album["uri"]})
                self._row_to_entry_index[row] = entry_index
                self.append(ListItem(Label(text)))
                row += 1
        else:
            self.append(ListItem(Label("Albums (empty)")))
            row += 1

        self.append(ListItem(Label("==== playlists ====")))
        row += 1

        if playlists:
            for playlist in playlists:
                text = playlist["name"]
                entry_index = len(self._entries)
                self._entries.append({"kind": "playlist", "uri": playlist["uri"]})
                self._row_to_entry_index[row] = entry_index
                self.append(ListItem(Label(text)))
                row += 1
        else:
            self.append(ListItem(Label("No playlists")))

    def play_selected(self, client) -> bool:
        if self.index is None or self.index < 0:
            return False

        entry_index = self._row_to_entry_index.get(self.index)
        if entry_index is None:
            return False

        entry = self._entries[entry_index]
        if entry["kind"] == "album":
            client.play_album(entry["uri"])
        else:
            client.play_playlist_shuffle(entry["uri"])
        return True
