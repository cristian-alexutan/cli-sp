from client.auth import create_client
from librespot.core import Session
import time

class Song:
    def __init__(self, artists: list, title: str, album: str, progress: int, length: int, is_playing: bool):
        self.artists = artists
        self.title = title
        self.album = album
        self.timestamp = progress
        self.length = length
        self.is_playing = is_playing

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

    def get_currently_playing(self) -> Song | None:
        result = self.__client.current_playback()

        album = result['item']['album']['name']
        song_name = result['item']['name']

        artists = []
        for artist in result['item']['artists']:
            artists.append(artist['name'])

        progress = result['progress_ms']
        duration = result['item']['duration_ms']
        is_playing = result['is_playing']

        return Song(artists, song_name, album, progress, duration, is_playing)

    def volume_up(self):
        current = self.__client.current_playback()['device']['volume_percent'] // 10 * 10
        to_set = min(current + 10, 100)
        self.__client.volume(volume_percent=to_set)

    def volume_down(self):
        current = self.__client.current_playback()['device']['volume_percent'] // 10 * 10
        to_set = max(current - 10, 0)
        self.__client.volume(volume_percent=to_set)