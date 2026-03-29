import os
import platform
import shutil
import subprocess
import time

def is_spotify_running() -> bool:
    system = platform.system()

    if system == "Windows":
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Spotify.exe"],
            capture_output=True,
            text=True,
        )
        return "Spotify.exe" in result.stdout

    if system == "Linux":
        result = subprocess.run(
            ["pgrep", "-x", "spotify"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True

        result = subprocess.run(
            ["pgrep", "-f", "spotify"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    return False

def _spawn(command: list[str], creationflags: int = 0) -> bool:
    try:
        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if creationflags:
            kwargs["creationflags"] = creationflags
        subprocess.Popen(command, **kwargs)
        return True
    except (FileNotFoundError, OSError):
        return False

def _wait_until_running(timeout_sec: float = 12.0, interval_sec: float = 0.3) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if is_spotify_running():
            return True
        time.sleep(interval_sec)
    return False

def launch_spotify() -> bool:
    if is_spotify_running():
        return True

    system = platform.system()
    started = False

    if system == "Windows":
        spotify_path = os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")
        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        detached_process = getattr(subprocess, "DETACHED_PROCESS", 0)
        flags = create_no_window | detached_process

        if os.path.isfile(spotify_path):
            started = _spawn([spotify_path, "--minimized"], creationflags=flags)

        if not started:
            started = _spawn(["explorer.exe", "spotify:"])

    elif system == "Linux":
        launch_candidates = [
            ["spotify"],
            ["flatpak", "run", "com.spotify.Client"],
            ["snap", "run", "spotify"],
            ["xdg-open", "spotify:"],
        ]

        for cmd in launch_candidates:
            if shutil.which(cmd[0]) is None:
                continue
            if _spawn(cmd):
                started = True
                break

    if not started:
        return False

    print("Starting Spotify...")
    return _wait_until_running()
