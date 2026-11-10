import datetime
import os
import platform
import re
import shutil
import subprocess
import time

# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------

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

def _find_binary(name: str) -> str | None:
    path = shutil.which(name)
    if path:
        return path
    local = os.path.expanduser(f"~/.local/bin/{name}")
    return local if os.access(local, os.X_OK) else None

def _systemctl_user(*args: str) -> subprocess.CompletedProcess | None:
    if shutil.which("systemctl") is None:
        return None
    return subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True,
        text=True,
    )

def _systemctl_ok(*args: str) -> bool:
    result = _systemctl_user(*args)
    return result is not None and result.returncode == 0

def _has_service(service: str) -> bool:
    return _systemctl_ok("cat", service)

def _service_active(service: str) -> bool:
    return _systemctl_ok("is-active", "--quiet", service)

def _service_exit_status(service: str) -> int | None:
    result = _systemctl_user("show", service, "-p", "ExecMainStatus", "--value")
    if result is None or result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None

def _pgrep_exact(name: str) -> bool:
    if shutil.which("pgrep") is None:
        return False
    return subprocess.run(["pgrep", "-x", name], capture_output=True).returncode == 0

def _wait_for(check, timeout_sec: float, interval_sec: float = 0.3) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(interval_sec)
    return False

# ---------------------------------------------------------------------------
# Soloist (official headless Spotify client)
# ---------------------------------------------------------------------------

SOLOIST_SERVICE = "soloist.service"
SOLOIST_ENV_FILE = os.path.expanduser("~/.config/soloist/soloist.env")
SOLOIST_EXPIRED_EXIT = 10
SOLOIST_LIFETIME_DAYS = 90
SOLOIST_DOWNLOAD_URL = "https://soloist-builds.spotifycdn.com/soloist_release_x86_64.tar.gz"

def _soloist_build_date(binary: str) -> datetime.date | None:
    try:
        out = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"\((\d{8})\)", out)
    if not match:
        return None
    try:
        return datetime.datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return None

def _warn_if_soloist_expiring(binary: str) -> None:
    built = _soloist_build_date(binary)
    if built is None:
        return
    expires = built + datetime.timedelta(days=SOLOIST_LIFETIME_DAYS)
    days_left = (expires - datetime.date.today()).days
    if days_left <= 0:
        print(f"Soloist build expired on {expires}. Download a new one from {SOLOIST_DOWNLOAD_URL}")
    elif days_left <= 14:
        print(f"Soloist build expires in {days_left} day(s) ({expires}). Consider updating.")

def _sync_soloist_env(api_key: str, device_name: str) -> bool:
    """Write the key and device name to the private env file the systemd unit
    reads. Returns True if the file changed."""
    content = f"SOLOIST_API_KEY={api_key}\nSOLOIST_DEVICE_NAME={device_name}\n"
    try:
        with open(SOLOIST_ENV_FILE) as f:
            if f.read() == content:
                return False
    except FileNotFoundError:
        pass

    os.makedirs(os.path.dirname(SOLOIST_ENV_FILE), mode=0o700, exist_ok=True)
    fd = os.open(SOLOIST_ENV_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(content)
    os.chmod(SOLOIST_ENV_FILE, 0o600)
    return True

def is_soloist_running() -> bool:
    return _service_active(SOLOIST_SERVICE) or _pgrep_exact("soloist")

def launch_soloist(device_name: str) -> bool:
    """Start Soloist in the background. Prefers the systemd user service,
    falls back to spawning the binary directly. Returns False if Soloist is
    not installed, no API key is configured, or it failed to start."""
    binary = _find_binary("soloist")
    api_key = os.getenv("SOLOIST_API_KEY", "").strip()
    if binary is None or not api_key:
        return False

    _warn_if_soloist_expiring(binary)

    if _has_service(SOLOIST_SERVICE):
        changed = _sync_soloist_env(api_key, device_name)
        if _service_active(SOLOIST_SERVICE) and not changed:
            return True

        print("Starting Soloist...")
        action = "restart" if changed else "start"
        if not _systemctl_ok(action, SOLOIST_SERVICE):
            return False

        # Give it a moment so an immediate crash (bad key, expired build) shows up.
        time.sleep(1.5)
        if _service_active(SOLOIST_SERVICE):
            return True
        if _service_exit_status(SOLOIST_SERVICE) == SOLOIST_EXPIRED_EXIT:
            print(f"Soloist build has expired. Download a new one from {SOLOIST_DOWNLOAD_URL}")
        else:
            print("Soloist failed to start; see `journalctl --user -u soloist`.")
        return False

    if is_soloist_running():
        return True

    print("Starting Soloist...")
    if not _spawn([binary, "-n", device_name, "-k", api_key, "-w", "127.0.0.1:0"]):
        return False
    return _wait_for(is_soloist_running, 5.0)

# ---------------------------------------------------------------------------
# desktop app (fallback)
# ---------------------------------------------------------------------------

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
        if _pgrep_exact("spotify"):
            return True
        # flatpak/snap wrappers: match the desktop client, not soloist
        result = subprocess.run(
            ["pgrep", "-f", "com.spotify.Client|/spotify( |$)"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    return False

def launch_desktop_spotify() -> bool:
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
    return _wait_for(is_spotify_running, 12.0)

# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def launch_spotify() -> str | None:
    """Start a playback backend. Returns which one ("soloist" or "desktop")
    or None if nothing could be started.

    Soloist is used if it is installed and SOLOIST_API_KEY is set; otherwise
    the desktop app."""
    device_name = os.getenv("SPOTIFY_DEVICE_NAME", "cli-sp").strip() or "cli-sp"

    if launch_soloist(device_name):
        return "soloist"

    if launch_desktop_spotify():
        return "desktop"

    return None
