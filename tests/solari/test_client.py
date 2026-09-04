from __future__ import annotations

import pytest

from bench.solari import MachineKind, MachineLaunchError
from tests.solari.conftest import FakeDesktopClient, FakeSandboxClient


# --- sandbox --------------------------------------------------------------

def test_launch_sandbox_connects_and_maps_kwargs(client, sandbox_backend):
    with client.launch_sandbox(template="base", cpu=2, timeout_ms=600_000) as box:
        assert box.kind is MachineKind.SANDBOX
        assert box.id == "sbx_1"
        sb = sandbox_backend.created[0]
        assert sb.connected is True
        assert sb.create_kwargs["template"] == "base"
        assert sb.create_kwargs["cpu"] == 2
        assert sb.create_kwargs["timeout_ms"] == 600_000


def test_launch_sandbox_default_timeout_applied(client, sandbox_backend):
    with client.launch_sandbox():
        assert sandbox_backend.created[0].create_kwargs["timeout_ms"] == 15 * 60_000


def test_sandbox_exec_and_preview(client):
    with client.launch_sandbox() as box:
        assert box.exec("echo", args=["hi"]).stdout == "ran: echo hi"
        assert box.preview_url(8000).endswith("8000.preview.getsolari.com")
        assert box.snapshot().startswith("snap_")


def test_sandbox_write_bytes_read_bytes_roundtrip(client):
    with client.launch_sandbox() as box:
        box.write_bytes("logo.png", b"\x89PNG-raw-bytes")
        assert box.read_bytes("logo.png") == b"\x89PNG-raw-bytes"


def test_sandbox_context_exit_kills_vm(client, sandbox_backend):
    with client.launch_sandbox() as box:
        pass
    assert box.closed is True
    assert sandbox_backend.created[0].killed is True


def test_sandbox_close_is_idempotent(client, sandbox_backend):
    box = client.launch_sandbox()
    box.close()
    box.close()
    assert sandbox_backend.created[0].killed is True


def test_launch_sandbox_timeout_raises_machine_launch_error(make_client):
    slow = FakeSandboxClient(slow=1.0)
    c = make_client(sandbox=slow)
    with pytest.raises(MachineLaunchError, match="did not launch"):
        c.launch_sandbox(launch_timeout_s=0.05)


# --- desktop -------------------------------------------------------------

def test_launch_desktop_waits_for_health(make_client):
    backend = FakeDesktopClient(ready_after=2)  # first 2 health() calls -> not ready
    c = make_client(desktop=backend)
    with c.launch_desktop(resolution="1280x720") as d:
        assert d.id == "dsk_1"
        assert backend.created[0]._health_calls >= 3
        d.click(10, 20)
        d.type_text("hello")
    assert backend.created[0].closed is True
    assert backend.destroyed == ["dsk_1"]


def test_launch_desktop_never_ready_raises_and_cleans_up(make_client):
    backend = FakeDesktopClient(never_ready=True)
    c = make_client(desktop=backend)
    with pytest.raises(MachineLaunchError, match="never became ready"):
        c.launch_desktop(launch_timeout_s=0.1)
    # still torn down despite the failure
    assert backend.created[0].closed is True
    assert backend.destroyed == ["dsk_1"]


# --- browser ------------------------------------------------------------

def test_launch_browser_returns_endpoints(client, browser_backend):
    with client.launch_browser(stealth=True) as br:
        assert br.kind is MachineKind.BROWSER
        assert br.ws_endpoint.startswith("wss://")
        assert br.cdp_endpoint.endswith(br.id)
        assert browser_backend.sessions_made[0].create_kwargs["stealth"] is True
    assert browser_backend.released == [br.id]


def test_launch_browser_resolves_profile_name(client, browser_backend):
    prof = client.create_profile("salesforce")
    with client.launch_browser(profile="salesforce") as br:
        assert browser_backend.sessions_made[0].create_kwargs["profile_id"] == prof.id


def test_launch_browser_unknown_profile_raises(client):
    with pytest.raises(MachineLaunchError, match="no Solari browser profile"):
        client.launch_browser(profile="does-not-exist")


def test_browser_release_and_wait_confirms(client, browser_backend):
    br = client.launch_browser()
    br.release_and_wait()
    assert browser_backend.confirmed_release == [br.id]


def test_browser_download_replay(client):
    with client.launch_browser(recording=True) as br:
        assert br.download_replay().startswith(b"{")


# --- dispatch + shutdown ---------------------------------------------

def test_launch_dispatch_by_kind(client):
    with client.launch("sandbox") as box:
        assert box.kind is MachineKind.SANDBOX


def test_close_shuts_down_built_sdk_clients(make_client, sandbox_backend, browser_backend):
    c = make_client()
    with c.launch_sandbox():
        pass
    c.launch_browser().close()
    c.close()
    assert sandbox_backend.closed is True
    assert browser_backend.closed is True
