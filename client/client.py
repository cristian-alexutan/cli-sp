from client.auth import create_client

class Client:
    def __init__(self):
        self.__client = create_client()

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