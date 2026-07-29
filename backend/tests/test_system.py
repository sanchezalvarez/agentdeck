import subprocess
import types

import pytest

from app.config import get_settings
from app.services import screenshot


class FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture
def shot_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "screenshot_dir", str(tmp_path))
    return tmp_path


def fake_mss_module(written: list):
    """A stand-in for the real mss library that writes a marker file instead of
    touching the screen."""

    class Size:
        width = 1280
        height = 720

    class Shot:
        rgb = b"fake-rgb"
        size = Size()

    class Sct:
        monitors = [{"all": True}, {"primary": True}]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def grab(self, monitor):
            return Shot()

    def to_png(rgb, size, output):
        written.append(output)
        with open(output, "wb") as f:
            f.write(b"\x89PNG\r\n")

    module = types.SimpleNamespace()
    module.__version__ = "10.2.0"
    module.mss = lambda: Sct()
    module.tools = types.SimpleNamespace(to_png=to_png)
    return module


# --- status ----------------------------------------------------------------


def test_screenshot_status_not_installed(client, monkeypatch):
    monkeypatch.setattr(screenshot, "_load_mss", lambda: None)
    body = client.get("/api/system/screenshot/status").json()

    assert body["installed"] is False
    assert body["version"] is None
    assert "not installed" in body["detail"].lower()


def test_screenshot_status_installed(client, monkeypatch):
    monkeypatch.setattr(screenshot, "_load_mss", lambda: fake_mss_module([]))
    body = client.get("/api/system/screenshot/status").json()

    assert body["installed"] is True
    assert body["version"] == "10.2.0"


# --- install ---------------------------------------------------------------


def test_screenshot_install_runs_pip(client, auth, monkeypatch):
    calls: list = []

    def runner(argv, **kwargs):
        calls.append({"argv": argv, "kwargs": kwargs})
        return FakeCompleted(0, stdout="Successfully installed mss-10.2.0")

    monkeypatch.setattr(screenshot.subprocess, "run", runner)
    # read_status runs after install — pretend it is now present.
    monkeypatch.setattr(screenshot, "_load_mss", lambda: fake_mss_module([]))

    body = client.post("/api/system/screenshot/install", headers=auth).json()

    assert body["ok"] is True
    assert body["status"]["installed"] is True
    # pip install into this very interpreter, fixed argv, shell=False.
    assert calls[0]["argv"][1:] == ["-m", "pip", "install", "mss"]
    assert calls[0]["argv"][0] == screenshot.sys.executable
    assert calls[0]["kwargs"]["shell"] is False


def test_screenshot_install_requires_write_token(client):
    assert client.post("/api/system/screenshot/install").status_code == 401


def test_screenshot_install_reports_failure(client, auth, monkeypatch):
    monkeypatch.setattr(
        screenshot.subprocess,
        "run",
        lambda *a, **k: FakeCompleted(1, stderr="ERROR: could not find a version"),
    )
    monkeypatch.setattr(screenshot, "_load_mss", lambda: None)

    body = client.post("/api/system/screenshot/install", headers=auth).json()

    assert body["ok"] is False
    assert body["exit_code"] == 1
    assert "could not find a version" in body["output"]


def test_screenshot_install_handles_timeout(client, auth, monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="pip", timeout=1)

    monkeypatch.setattr(screenshot.subprocess, "run", boom)
    response = client.post("/api/system/screenshot/install", headers=auth)

    assert response.status_code == 504
    assert "timed out" in response.json()["detail"]


# --- capture ---------------------------------------------------------------


def test_capture_without_mss_returns_422(client, auth, shot_dir, monkeypatch):
    monkeypatch.setattr(screenshot, "_load_mss", lambda: None)
    response = client.post("/api/system/screenshot/capture", headers=auth)

    assert response.status_code == 422
    assert "install" in response.json()["detail"].lower()


def test_capture_saves_png_and_returns_url(client, auth, shot_dir, monkeypatch):
    written: list = []
    monkeypatch.setattr(screenshot, "_load_mss", lambda: fake_mss_module(written))

    body = client.post("/api/system/screenshot/capture", headers=auth).json()

    assert body["ok"] is True
    assert body["filename"].startswith("screenshot-")
    assert body["filename"].endswith(".png")
    assert body["url"] == f"/api/system/screenshot/file/{body['filename']}"
    assert body["width"] == 1280 and body["height"] == 720
    # The file really landed in the configured directory.
    assert (shot_dir / body["filename"]).is_file()


def test_capture_requires_write_token(client):
    assert client.post("/api/system/screenshot/capture").status_code == 401


# --- file serving ----------------------------------------------------------


def test_screenshot_file_served(client, shot_dir):
    name = "screenshot-2026-01-01T00-00-00.png"
    (shot_dir / name).write_bytes(b"\x89PNG\r\n")

    response = client.get(f"/api/system/screenshot/file/{name}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_screenshot_file_rejects_traversal(client, shot_dir):
    # Anything not matching the capture filename pattern is a 404, never a read.
    assert client.get("/api/system/screenshot/file/..%2f..%2f.env").status_code == 404
    assert client.get("/api/system/screenshot/file/evil.png").status_code == 404


def test_screenshot_file_missing_is_404(client, shot_dir):
    assert (
        client.get("/api/system/screenshot/file/screenshot-2020-01-01T00-00-00.png").status_code
        == 404
    )
