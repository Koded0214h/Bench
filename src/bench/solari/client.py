"""``SolariClient`` — the one object Bench worker code imports.

A synchronous facade over the async ``solari-sandbox`` / ``solari-desktop`` /
``solari-browser`` SDKs. It runs them on a private background loop, maps Bench's
three capabilities onto the right SDK call, and hands back a handle that destroys
its machine on ``with`` exit.

    from bench.solari import SolariClient

    with SolariClient.from_env() as solari:
        with solari.launch_sandbox(timeout_ms=600_000) as box:
            print(box.exec("echo", args=["hello"]).stdout)
"""

from __future__ import annotations

import time
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, Callable

from ._loop import LoopThread
from .backends import SolariBackends
from .config import SolariConfig
from .errors import MachineLaunchError
from .handles import BrowserHandle, DesktopHandle, MachineKind, SandboxHandle


class SolariClient:
    def __init__(
        self,
        config: SolariConfig,
        *,
        backends: SolariBackends | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._backends = backends or SolariBackends()
        self._sleep = sleep
        self._loop = LoopThread()
        self._sandbox_client: Any = None
        self._desktop_client: Any = None
        self._browser_client: Any = None
        self._closed = False

    @classmethod
    def from_env(cls, **overrides: Any) -> "SolariClient":
        return cls(SolariConfig.from_env(**overrides))

    @property
    def config(self) -> SolariConfig:
        return self._config

    # -- lazily-built SDK clients ------------------------------------------

    def _sandbox(self) -> Any:
        if self._sandbox_client is None:
            self._sandbox_client = self._backends.sandbox(self._config)
        return self._sandbox_client

    def _desktop(self) -> Any:
        if self._desktop_client is None:
            self._desktop_client = self._backends.desktop(self._config)
        return self._desktop_client

    def _browser(self) -> Any:
        if self._browser_client is None:
            self._browser_client = self._backends.browser(self._config)
        return self._browser_client

    @property
    def _call_timeout_s(self) -> float:
        return self._config.call_timeout_ms / 1000.0

    def _launch_timeout(self, override: float | None) -> float:
        return override if override is not None else self._config.launch_timeout_s

    # -- sandbox --------------------------------------------------------

    def launch_sandbox(
        self,
        *,
        template: str | None = None,
        timeout_ms: int | None = None,
        cpu: int | None = None,
        mem_mb: int | None = None,
        envs: dict[str, str] | None = None,
        metadata: dict[str, str] | None = None,
        from_snapshot: str | None = None,
        launch_timeout_s: float | None = None,
    ) -> SandboxHandle:
        """Create a Linux sandbox and connect its control channel."""

        timeout_ms = timeout_ms or self._config.default_machine_timeout_ms

        async def _make() -> Any:
            client = self._sandbox()
            sandbox = await client.create(
                template=template,
                timeout_ms=timeout_ms,
                cpu=cpu,
                mem_mb=mem_mb,
                envs=envs,
                metadata=metadata,
                from_snapshot=from_snapshot,
            )
            await sandbox.connect()
            return sandbox

        sandbox = self._run_launch(_make(), self._launch_timeout(launch_timeout_s), MachineKind.SANDBOX)

        return SandboxHandle(
            self._loop,
            sandbox,
            teardown=lambda: sandbox.kill(),
            call_timeout_s=self._call_timeout_s,
        )

    # -- desktop -------------------------------------------------------

    def launch_desktop(
        self,
        *,
        template: str = "default",
        resolution: str | None = None,
        timeout_ms: int | None = None,
        cpu: int | None = None,
        mem_mb: int | None = None,
        record: bool | None = None,
        metadata: dict[str, str] | None = None,
        launch_timeout_s: float | None = None,
    ) -> DesktopHandle:
        """Create a GUI desktop, connect it, and wait for X11 to report ready."""

        timeout_ms = timeout_ms or self._config.default_machine_timeout_ms
        client = self._desktop()

        async def _make() -> Any:
            desktop = await client.create(
                template=template,
                resolution=resolution,
                timeout_ms=timeout_ms,
                cpu=cpu,
                mem_mb=mem_mb,
                record=record,
                metadata=metadata,
            )
            await desktop.connect()
            return desktop

        deadline = self._launch_timeout(launch_timeout_s)
        desktop = self._run_launch(_make(), deadline, MachineKind.DESKTOP)

        async def _teardown() -> None:
            try:
                await desktop.close()
            finally:
                await client.destroy(desktop.sessionId)

        handle = DesktopHandle(
            self._loop, desktop, teardown=_teardown, call_timeout_s=self._call_timeout_s
        )
        try:
            handle.wait_ready(
                timeout_s=deadline,
                poll_interval_s=self._config.launch_poll_interval_s,
                sleep=self._sleep,
            )
        except Exception as exc:  # noqa: BLE001 - convert + clean up
            handle.close()
            raise MachineLaunchError(
                f"desktop {handle.id} never became ready: {exc}",
                machine_id=handle.id,
                kind="desktop",
            ) from exc
        return handle

    # -- browser -------------------------------------------------------

    def launch_browser(
        self,
        *,
        profile: str | None = None,
        profile_id: str | None = None,
        recording: bool = False,
        stealth: bool = False,
        captcha: bool = False,
        proxy: Any = None,
        launch_timeout_s: float | None = None,
    ) -> BrowserHandle:
        """Create a cloud browser session. Pass ``profile`` (name) or
        ``profile_id`` to start already logged in. The caller drives the browser
        over ``handle.ws_endpoint`` / ``handle.cdp_endpoint``."""

        solari = self._browser()

        async def _make() -> Any:
            resolved = profile_id
            if resolved is None and profile is not None:
                for p in await solari.profiles.list():
                    if p.name == profile:
                        resolved = p.id
                        break
                if resolved is None:
                    raise MachineLaunchError(f"no Solari browser profile named {profile!r}")
            return await solari.sessions.create(
                profile_id=resolved,
                recording=recording,
                stealth=stealth,
                captcha=captcha,
                proxy=proxy,
            )

        session = self._run_launch(_make(), self._launch_timeout(launch_timeout_s), MachineKind.BROWSER)

        return BrowserHandle(
            self._loop,
            session,
            solari.sessions,
            teardown=lambda: solari.sessions.release(session.id),
            call_timeout_s=self._call_timeout_s,
        )

    def launch(self, kind: MachineKind | str, **kwargs: Any) -> Any:
        """Dispatch to ``launch_sandbox`` / ``launch_browser`` / ``launch_desktop``."""

        mapping = {
            MachineKind.SANDBOX: self.launch_sandbox,
            MachineKind.BROWSER: self.launch_browser,
            MachineKind.DESKTOP: self.launch_desktop,
        }
        return mapping[MachineKind(kind)](**kwargs)

    # -- browser profiles (login reuse) -------------------------------

    def list_profiles(self) -> list[Any]:
        return self._loop.run(self._browser().profiles.list(), timeout=self._call_timeout_s)

    def create_profile(self, name: str) -> Any:
        return self._loop.run(self._browser().profiles.create(name), timeout=self._call_timeout_s)

    def delete_profile(self, profile_id: str) -> None:
        self._loop.run(self._browser().profiles.delete(profile_id), timeout=self._call_timeout_s)

    # -- internals ---------------------------------------------------

    def _run_launch(self, coro: Any, timeout_s: float, kind: MachineKind) -> Any:
        try:
            return self._loop.run(coro, timeout=timeout_s)
        except FutureTimeoutError as exc:
            raise MachineLaunchError(
                f"{kind.value} did not launch within {timeout_s}s", kind=kind.value
            ) from exc

    # -- lifecycle -------------------------------------------------

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        async def _shutdown() -> None:
            for client, method in (
                (self._sandbox_client, "aclose"),
                (self._desktop_client, "aclose"),
                (self._browser_client, "close"),
            ):
                if client is None:
                    continue
                try:
                    await getattr(client, method)()
                except Exception:  # noqa: BLE001 - shutdown is best-effort
                    pass

        try:
            self._loop.run(_shutdown(), timeout=15.0)
        except Exception:  # noqa: BLE001
            pass
        self._loop.close()

    def __enter__(self) -> "SolariClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
