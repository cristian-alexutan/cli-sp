from textual.widgets import Label
from textual.containers import ScrollableContainer
from client.song import SongDetails

class QueueWidget(ScrollableContainer):

    def set_queue(self, songs: list[SongDetails]) -> None:
        self.remove_children()

        if not songs:
            self.mount(Label("queue is empty"))
            return

        for song in songs:
            artists = ", ".join(song.artists)
            self.mount(Label(f"{song.title} - {artists}"))