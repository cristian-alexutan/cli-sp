import subprocess
import time
import os

def launch_spotify():
    spotify_path = os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")

    if os.path.isfile(spotify_path):
        subprocess.Popen(
            [spotify_path, "--minimized"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        subprocess.Popen(
            ['explorer.exe', 'spotify:'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    print("Starting Spotify...")
    time.sleep(4)
    return True