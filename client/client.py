from client.auth import create_client
from librespot.core import Session
import time

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