"""V2 AC13/AC14/AC17 — install-wi plugin deployment + WIBridge HTTP protocol."""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from dvr.commands import install_wi as iw
from dvr.errors import WIError, WIUnavailable
from dvr.wi_client import DEFAULT_PORT, WIBridge


# ---------- install-wi ----------

def _make_source(tmp_path: Path) -> Path:
    src = tmp_path / "wi-plugin"
    src.mkdir()
    for name in iw.PLUGIN_FILES:
        (src / name).write_text(f"// stub {name}")
    return src


def test_install_copies_all_files(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    dst = tmp_path / "plugins" / "dvr-cli-bridge"
    out = iw.install(source_dir=src, dest_dir=dst)
    assert out["ok"] is True
    for name in iw.PLUGIN_FILES:
        assert (dst / name).exists()
    assert all("copied" in a for a in out["actions"])


def test_install_is_idempotent(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    dst = tmp_path / "plugins" / "dvr-cli-bridge"
    iw.install(source_dir=src, dest_dir=dst)
    second = iw.install(source_dir=src, dest_dir=dst)
    assert all("unchanged" in a for a in second["actions"])


def test_install_force_rewrites(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    dst = tmp_path / "plugins" / "dvr-cli-bridge"
    iw.install(source_dir=src, dest_dir=dst)
    # Mutate dst, then force should re-copy
    (dst / "manifest.xml").write_text("// tampered")
    out = iw.install(source_dir=src, dest_dir=dst, force=True)
    assert "copied: manifest.xml" in out["actions"]
    assert "stub manifest.xml" in (dst / "manifest.xml").read_text()


def test_uninstall_removes_directory(tmp_path: Path) -> None:
    src = _make_source(tmp_path)
    dst = tmp_path / "plugins" / "dvr-cli-bridge"
    iw.install(source_dir=src, dest_dir=dst)
    out = iw.uninstall(dest_dir=dst)
    assert out["removed"] is True
    assert not dst.exists()


def test_uninstall_idempotent(tmp_path: Path) -> None:
    dst = tmp_path / "ghost-dir"
    out = iw.uninstall(dest_dir=dst)
    assert out["removed"] is False


def test_plugin_dest_dir_per_platform() -> None:
    for plat in ("darwin", "windows", "linux"):
        path = iw.plugin_dest_dir(plat)
        assert iw.PLUGIN_FOLDER_NAME in str(path)


# ---------- WIBridge HTTP protocol ----------

@pytest.fixture
def free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_call_raises_wi_unavailable_when_no_plugin(free_port: int) -> None:
    bridge = WIBridge(port=free_port)
    with pytest.raises(WIUnavailable):
        bridge.call("ping", handshake_timeout=0.2)


def test_call_succeeds_with_simulated_plugin(free_port: int) -> None:
    """A background thread plays the role of the WI plugin: poll /inbox, POST /result."""
    bridge = WIBridge(port=free_port)
    base = f"http://127.0.0.1:{free_port}"

    def fake_plugin() -> None:
        # Poll until the CLI binds; once it does, claim the task and answer it.
        for _ in range(30):
            try:
                resp = urllib.request.urlopen(base + "/inbox", timeout=0.5)
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.05)
                continue
            if resp.status == 204:
                time.sleep(0.05)
                continue
            payload = json.loads(resp.read())
            result = {"id": payload["id"], "result": {"echoed": payload["params"]}}
            req = urllib.request.Request(
                base + "/result",
                data=json.dumps(result).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=1.0)
            return

    t = threading.Thread(target=fake_plugin, daemon=True)
    t.start()
    out = bridge.call("timeline.cut", {"at": "00:00:01:00"}, handshake_timeout=3.0, result_timeout=3.0)
    assert out == {"echoed": {"at": "00:00:01:00"}}
    t.join(timeout=2.0)


def test_call_raises_wi_error_when_plugin_returns_error(free_port: int) -> None:
    bridge = WIBridge(port=free_port)
    base = f"http://127.0.0.1:{free_port}"

    def fake_plugin() -> None:
        for _ in range(30):
            try:
                resp = urllib.request.urlopen(base + "/inbox", timeout=0.5)
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.05)
                continue
            if resp.status == 204:
                time.sleep(0.05)
                continue
            payload = json.loads(resp.read())
            result = {"id": payload["id"], "error": "test_failure", "hint": "check x"}
            req = urllib.request.Request(
                base + "/result",
                data=json.dumps(result).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=1.0)
            return

    threading.Thread(target=fake_plugin, daemon=True).start()
    with pytest.raises(WIError) as exc:
        bridge.call("timeline.cut", {"at": "00:00:01:00"}, handshake_timeout=3.0, result_timeout=3.0)
    assert "test_failure" in str(exc.value)


def test_bridge_default_port() -> None:
    assert DEFAULT_PORT == 50420
