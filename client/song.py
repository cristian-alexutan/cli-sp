class SongDetails:
    def __init__(self, artists: list, title: str, album: str):
        self.artists = artists
        self.title = title
        self.album = album

class SongPlayback:
    def __init__(self, details: SongDetails, progress: int, length: int, is_playing: bool, uri):
        self.details = details
        self.progress = progress
        self.length = length
        self.is_playing = is_playing
        self.uri = uri

def get_song_from_playback(json):
    if json is None:
        return None

    album = json['item']['album']['name']
    song_name = json['item']['name']

    artists = []
    for artist in json['item']['artists']:
        artists.append(artist['name'])

    progress = json['progress_ms']
    duration = json['item']['duration_ms']
    is_playing = json['is_playing']
    uri = json['item']['uri']

    return SongPlayback(SongDetails(artists, song_name, album), progress, duration, is_playing, uri)