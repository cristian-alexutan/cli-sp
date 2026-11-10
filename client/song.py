class SongDetails:
    def __init__(self, artists: list, title: str, album: str):
        self.artists = artists
        self.title = title
        self.album = album

class SongPlayback:
    def __init__(self, details: SongDetails, progress: int, length: int, is_playing: bool, uri,
                 context_uri: str | None = None):
        self.details = details
        self.progress = progress
        self.length = length
        self.is_playing = is_playing
        self.uri = uri
        # album/playlist/artist the track is playing from, if any
        self.context_uri = context_uri

def get_details_from_item(item: dict | None) -> SongDetails | None:
    """Build SongDetails from a track or podcast episode object."""
    if not item:
        return None

    title = item.get('name') or ''

    if item.get('type') == 'episode':
        show = item.get('show') or {}
        publisher = show.get('publisher') or show.get('name') or ''
        return SongDetails([publisher] if publisher else [], title, show.get('name') or '')

    album = (item.get('album') or {}).get('name') or ''
    artists = [artist.get('name') or '' for artist in item.get('artists') or []]
    return SongDetails(artists, title, album)

def get_song_from_playback(json: dict | None) -> SongPlayback | None:
    if not json:
        return None

    progress = json.get('progress_ms') or 0
    is_playing = bool(json.get('is_playing'))
    context_uri = (json.get('context') or {}).get('uri')
    item = json.get('item')

    if item is None:
        # ads (and some unknown content) come through without an item
        if json.get('currently_playing_type') == 'ad':
            return SongPlayback(SongDetails([], 'Advertisement', ''), progress, 0, is_playing, None, context_uri)
        return None

    details = get_details_from_item(item)
    duration = item.get('duration_ms') or 0
    return SongPlayback(details, progress, duration, is_playing, item.get('uri'), context_uri)
