import subprocess
import time
import os

def is_spotify_running() -> bool:
    result = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq Spotify.exe'],
        capture_output=True,
        text=True
    )
    return 'Spotify.exe' in result.stdout

def launch_spotify():
    if is_spotify_running():
        return True

    spotify_path = os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")

    if os.path.isfile(spotify_path):
        subprocess.Popen(
            [spotify_path, "--minimized"],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
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