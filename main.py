from client.spotify_launcher import launch_spotify
from client.client import Client
from app.mainwindow import MainWindow

def main():
    launch_spotify()

    sp = Client()
    sp.pass_to_clisp()

    app = MainWindow(sp)
    app.run()

if __name__ == "__main__":
    main()