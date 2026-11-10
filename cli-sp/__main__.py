import os

from dotenv import load_dotenv

from client.spotify_launcher import launch_spotify
from client.client import Client
from app.mainwindow import MainWindow

def main():
    load_dotenv()

    backend = launch_spotify()
    if backend is None:
        print("Could not start a Spotify backend (Soloist or the desktop app).")

    sp = Client()
    if not sp.pass_to_clisp(require_named=backend == "soloist"):
        print("No Spotify device found; playback controls may not work.")
        if backend == "soloist":
            name = os.getenv("SPOTIFY_DEVICE_NAME", "cli-sp")
            print(f"If this is the first run, pair Soloist: open Spotify on a device on the "
                  f"same network and pick '{name}' in the device list, then restart cli-sp.")
        input("Press enter to continue anyway...")

    app = MainWindow(sp)
    app.run()

if __name__ == "__main__":
    main()
