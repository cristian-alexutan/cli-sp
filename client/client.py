import functools
import os
import time
from typing import Callable

import requests
from spotipy.exceptions import SpotifyException

from client.auth import create_client
from client.song import SongPlayback, get_song_from_playback, get_details_from_item


def describe_error(error: Exception) -> str:
    """Turn a Spotify/network exception into a short, readable message."""
    if isinstance(error, SpotifyException):
        reason = (getattr(error, 'reason', None) or '').upper()
        status = error.http_status

        if reason == 'NO_ACTIVE_DEVICE' or status == 404:
            return "No active Spotify device"
        if reason == 'PREMIUM_REQUIRED':
            return "Spotify Premium is required for playback control"
        if status == 401:
            return "Spotify login expired; restart cli-sp to log in again"
        if status == 403:
            return f"Not allowed: {error.msg.split(':')[-1].strip() or 'restricted action'}"
        if status == 429:
            return "Rate limited by Spotify; slowing down"
        if status is not None and status >= 500:
            return "Spotify is having problems; try again shortly"
        return f"Spotify error: {error.msg}"

    if isinstance(error, requests.Timeout):
        return "Spotify request timed out"
    if isinstance(error, requests.ConnectionError):
        return "Can't reach Spotify; check your connection"
    return f"Unexpected error: {error}"


def api_call(default=None):
    """Catch Spotify/network errors in a Client method, report them through
    Client.on_error and return `default` (called first if it's callable, so
    mutable defaults aren't shared)."""
    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except (SpotifyException, requests.RequestException) as error:
                self.report_error(describe_error(error))
                return default() if callable(default) else default
        return wrapper
    return decorator


class Client:
    def __init__(self):
        self.__client = create_client()
        self.last_error: str | None = None
        # set by the UI to display errors; called with a short message
        self.on_error: Callable[[str], None] | None = None

    def report_error(self, message: str) -> None:
        self.last_error = message
        if self.on_error is not None:
            self.on_error(message)

    def _playback_state(self) -> dict | None:
        return self.__client.current_playback(additional_types='track,episode')

    @api_call(default=False)
    def pass_to_clisp(self, attempts: int = 15, require_named: bool = True) -> bool:
        """Transfer playback to the device named SPOTIFY_DEVICE_NAME (default
        "cli-sp", i.e. Soloist), waiting for it to register with
        Spotify. With require_named=False (desktop app), take the first
        available device instead."""
        preferred = os.getenv('SPOTIFY_DEVICE_NAME', 'cli-sp').strip().lower()

        for attempt in range(attempts):
            available = (self.__client.devices() or {}).get('devices', [])
            for device in available:
                if (device.get('name') or '').strip().lower() == preferred:
                    self.__client.transfer_playback(device['id'], force_play=False)
                    return True
            if available and not require_named:
                self.__client.transfer_playback(available[0]['id'], force_play=False)
                return True
            time.sleep(1)

        return False

    @api_call()
    def toggle_playback(self):
        state = self._playback_state()

        if not state:
            self.report_error("No active Spotify device")
            return

        if state.get('is_playing'):
            self.__client.pause_playback()
        else:
            self.__client.start_playback()

    @api_call()
    def previous_track(self):
        self.__client.previous_track()

    @api_call()
    def skip_track(self):
        self.__client.next_track()

    @api_call()
    def get_currently_playing(self) -> SongPlayback | None:
        return get_song_from_playback(self._playback_state())

    @api_call(default=0)
    def get_volume_percent(self) -> int:
        result = self._playback_state()
        if not result:
            return 0

        device = result.get('device') or {}
        return device.get('volume_percent') or 0

    @api_call()
    def volume_up(self):
        current = self.get_volume_percent()
        to_set = min(current + 10, 100)
        self.__client.volume(volume_percent=to_set)

    @api_call()
    def volume_down(self):
        current = self.get_volume_percent()
        to_set = max(current - 10, 0)
        self.__client.volume(volume_percent=to_set)

    @api_call(default=list)
    def get_queue(self) -> list:
        result = self.__client.queue() or {}

        songs = []
        for item in result.get('queue') or []:
            details = get_details_from_item(item)
            if details is not None:
                songs.append(details)

        return songs

    @api_call(default=lambda: ([], []))
    def get_library(self) -> tuple[list, list]:
        result = self.__client.current_user_playlists() or {}

        playlists = []
        for playlist in result.get('items') or []:
            if not playlist:
                continue
            playlists.append({'name': playlist.get('name') or '', 'uri': playlist['uri']})

        result = self.__client.current_user_saved_albums(limit=10) or {}

        albums = []
        for saved in result.get('items') or []:
            album = (saved or {}).get('album')
            if not album:
                continue
            artists = ', '.join(artist.get('name') or '' for artist in album.get('artists') or [])
            albums.append({'name': album.get('name') or '', 'artists': artists, 'uri': album['uri']})

        return albums, playlists

    @api_call()
    def play_album(self, album_uri: str) -> None:
        self.__client.start_playback(context_uri=album_uri)
        self.__client.shuffle(False)

    @api_call()
    def play_playlist_shuffle(self, playlist_uri: str) -> None:
        self.__client.start_playback(context_uri=playlist_uri)
        self.__client.shuffle(True)
