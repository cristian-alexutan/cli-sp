from client.auth import create_client
import time
from client.song import SongPlayback, get_song_from_playback, SongDetails


class Client:
    def __init__(self):
        self.__client = create_client()

    def pass_to_clisp(self):
        for attempt in range(10):
            devices = self.__client.devices()
            available = devices.get('devices', [])
            if available:
                self.__client.transfer_playback(available[0]['id'], force_play=False)
                return True
            time.sleep(1)
        return False

    def toggle_playback(self):
        state = self.__client.current_playback()

        if not state:
            return

        if state['is_playing']:
            self.__client.pause_playback()
        else:
            self.__client.start_playback()

    def previous_track(self):
        self.__client.previous_track()

    def skip_track(self):
        self.__client.next_track()

    def get_currently_playing(self) -> SongPlayback | None:
        result = self.__client.current_playback()

        return get_song_from_playback(result)

    def get_volume_percent(self) -> int:
        result = self.__client.current_playback()
        if result is None:
            return 0

        return result['device']['volume_percent']

    def volume_up(self):
        current = self.get_volume_percent()
        to_set = min(current + 10, 100)
        self.__client.volume(volume_percent=to_set)

    def volume_down(self):
        current = self.get_volume_percent()
        to_set = max(current - 10, 0)
        self.__client.volume(volume_percent=to_set)

    def get_queue(self) -> list:
        result = self.__client.queue()
        queue = result['queue']

        songs = []
        for song in queue:
            album = song['album']['name']
            song_name = song['name']

            artists = []
            for artist in song['artists']:
                artists.append(artist['name'])

            songs.append(SongDetails(artists, song_name, album))

        return songs

    def get_library(self) -> tuple[list, list]:
        result = self.__client.current_user_playlists()

        playlists = []
        for playlist in result['items']:
            playlists.append({'name': playlist['name'], 'uri': playlist['uri']})

        result = self.__client.current_user_saved_albums(limit=15)

        albums = []
        for album in result['items']:
            artists = ', '.join(artist['name'] for artist in album['album']['artists'])
            albums.append({'name': album['album']['name'], 'artists': artists, 'uri': album['album']['uri']})

        return playlists, albums