from __future__ import annotations

import pytest

from bench.solari import SolariConfig, SolariConfigError


def test_rejects_empty_api_key():
    with pytest.raises(SolariConfigError):
        SolariConfig(api_key="")


def test_rejects_non_http_base_url():
    with pytest.raises(SolariConfigError):
        SolariConfig(api_key="k", base_url="ftp://solari")


def test_strips_trailing_slash():
    assert SolariConfig(api_key="k", base_url="https://api.getsolari.com/").base_url == "https://api.getsolari.com"


def test_defaults():
    cfg = SolariConfig(api_key="k")
    assert cfg.base_url == "https://api.getsolari.com"
    assert cfg.region == "us-west"
    assert cfg.default_machine_timeout_ms == 15 * 60_000


def test_from_env_reads_and_overrides(monkeypatch):
    monkeypatch.setenv("SOLARI_API_KEY", "env-key")
    monkeypatch.setenv("SOLARI_LAUNCH_TIMEOUT_S", "9")
    cfg = SolariConfig.from_env(launch_timeout_s=3.0)
    assert cfg.api_key == "env-key"
    assert cfg.launch_timeout_s == 3.0  # explicit override wins


def test_from_env_missing_key_raises(monkeypatch):
    monkeypatch.delenv("SOLARI_API_KEY", raising=False)
    with pytest.raises(SolariConfigError):
        SolariConfig.from_env()
