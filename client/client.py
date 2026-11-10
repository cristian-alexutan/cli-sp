import functools
import os
import threading
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
                with self._lock:
                    return method(self, *args, **kwargs)
            except (SpotifyException, requests.RequestException) as error:
                self.report_error(describe_error(error))
                return default() if callable(default) else default
        return wrapper
    return decorator


class Client:
    def __init__(self):
        self.__client = create_client()
        self._lock = threading.RLock()
        # context uri -> display name ("Album Name", "Liked Songs", ...)
        self._context_names: dict[str, str] = {}
        self.last_error: str | None = None
        # set by the UI to display errors; called with a short message
        self.on_error: Callable[[str], None] | None = None

    def report_error(self, message: str) -> None:
        self.last_error = message
        if self.on_error is not None:
            self.on_error(message)

    MAX_PAGES = 40  # safety cap: 40 pages x 50 items = 2000 per list

    def _all_items(self, page: dict | None) -> list:
        """Collect the items of a paginated response, following `next` links."""
        items = []
        for _ in range(self.MAX_PAGES):
            if not page:
                break
            items.extend(page.get('items') or [])
            if not page.get('next'):
                break
            page = self.__client.next(page)
        return items

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
    def get_playback(self) -> tuple[SongPlayback | None, int | None] | None:
        """Current song and device volume from a single API call. Returns None
        if the request failed (so callers can keep showing the last state)."""
        state = self._playback_state()
        if not state:
            return None, None

        device = state.get('device') or {}
        return get_song_from_playback(state), device.get('volume_percent')

    @api_call()
    def set_volume(self, percent: int) -> None:
        self.__client.volume(volume_percent=max(0, min(100, percent)))

    @api_call()
    def get_context_name(self, context_uri: str | None) -> str | None:
        """Name of the album/playlist/artist/show a track plays from. Cached,
        and pre-filled from the library, so it rarely costs a request."""
        if not context_uri:
            return None
        if context_uri in self._context_names:
            return self._context_names[context_uri]

        parts = context_uri.split(':')
        kind = parts[1] if len(parts) > 2 else ''
        if parts[-1] == 'collection':
            name = 'Liked Songs'
        elif kind == 'album':
            name = (self.__client.album(context_uri) or {}).get('name')
        elif kind == 'playlist':
            name = (self.__client.playlist(context_uri, fields='name') or {}).get('name')
        elif kind == 'artist':
            name = (self.__client.artist(context_uri) or {}).get('name')
        elif kind == 'show':
            name = (self.__client.show(context_uri) or {}).get('name')
        else:
            name = None

        if name:
            self._context_names[context_uri] = name
        return name

    @api_call()
    def get_queue(self) -> list | None:
        result = self.__client.queue() or {}

        songs = []
        for item in result.get('queue') or []:
            details = get_details_from_item(item)
            if details is not None:
                songs.append(details)

        return songs

    @api_call()
    def get_library(self) -> tuple[list, list] | None:
        playlists = []
        for playlist in self._all_items(self.__client.current_user_playlists(limit=50)):
            if not playlist:
                continue
            playlists.append({'name': playlist.get('name') or '', 'uri': playlist['uri']})
            self._context_names[playlist['uri']] = playlist.get('name') or ''

        albums = []
        for saved in self._all_items(self.__client.current_user_saved_albums(limit=50)):
            album = (saved or {}).get('album')
            if not album:
                continue
            artists = ', '.join(artist.get('name') or '' for artist in album.get('artists') or [])
            albums.append({'name': album.get('name') or '', 'artists': artists, 'uri': album['uri']})
            self._context_names[album['uri']] = album.get('name') or ''

        return albums, playlists

    @api_call()
    def play_album(self, album_uri: str) -> None:
        self.__client.start_playback(context_uri=album_uri)
        self.__client.shuffle(False)

    @api_call()
    def play_playlist_shuffle(self, playlist_uri: str) -> None:
        self.__client.start_playback(context_uri=playlist_uri)
        self.__client.shuffle(True)

    # -- search -------------------------------------------------------------

    SEARCH_LIMIT = 10  # max per type the Web API accepts for this app

    @staticmethod
    def _artist_names(obj: dict) -> str:
        return ', '.join(a.get('name') or '' for a in obj.get('artists') or [])

    def _track_rows(self, items) -> list[dict]:
        rows = []
        for track in items or []:
            if not track or not track.get('uri'):
                continue
            album = track.get('album') or {}
            rows.append({'name': track.get('name') or '', 'artists': self._artist_names(track),
                         'album_uri': album.get('uri'), 'uri': track['uri']})
        return rows

    def _album_rows(self, items) -> list[dict]:
        rows = []
        for album in items or []:
            if not album or not album.get('uri'):
                continue
            name = album.get('name') or ''
            self._context_names.setdefault(album['uri'], name)
            rows.append({'name': name, 'artists': self._artist_names(album), 'uri': album['uri']})
        return rows

    @api_call()
    def search(self, query: str) -> dict | None:
        """Tracks, albums, artists and playlists matching `query`, as plain
        dicts. Returns None if the request failed."""
        result = self.__client.search(q=query, type='track,album,artist,playlist',
                                      limit=self.SEARCH_LIMIT) or {}

        def items(kind):
            return (result.get(kind) or {}).get('items') or []

        artists = [{'name': a.get('name') or '', 'uri': a['uri']}
                   for a in items('artists') if a and a.get('uri')]

        playlists = []
        for playlist in items('playlists'):
            if not playlist or not playlist.get('uri'):
                continue  # search returns null entries for some playlists
            name = playlist.get('name') or ''
            self._context_names.setdefault(playlist['uri'], name)
            owner = (playlist.get('owner') or {}).get('display_name') or ''
            playlists.append({'name': name, 'owner': owner, 'uri': playlist['uri']})

        return {
            'tracks': self._track_rows(items('tracks')),
            'albums': self._album_rows(items('albums')),
            'artists': artists,
            'playlists': playlists,
        }

    @api_call()
    def get_artist_view(self, artist_uri: str, artist_name: str) -> dict | None:
        """Popular tracks and albums for an artist. The top-tracks endpoint is
        forbidden for development-mode apps, so tracks come from a search."""
        found = self.__client.search(q=f'artist:"{artist_name}"', type='track',
                                     limit=self.SEARCH_LIMIT) or {}
        tracks = [t for t in self._track_rows((found.get('tracks') or {}).get('items'))
                  if artist_name.lower() in t['artists'].lower()]

        albums = self.__client.artist_albums(artist_uri, include_groups='album,single',
                                             limit=self.SEARCH_LIMIT) or {}
        return {'tracks': tracks, 'albums': self._album_rows(albums.get('items'))}

    @api_call()
    def play_track_in_album(self, track_uri: str, album_uri: str | None) -> None:
        """Play a track and keep going through the rest of its album."""
        if album_uri:
            self.__client.start_playback(context_uri=album_uri, offset={'uri': track_uri})
            self.__client.shuffle(False)
        else:
            self.__client.start_playback(uris=[track_uri])

    @api_call(default=False)
    def add_to_queue(self, uri: str) -> bool:
        self.__client.add_to_queue(uri)
        return True
