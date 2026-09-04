"""Boot and destroy one Solari sandbox to confirm the API key works."""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Boot and destroy one sandbox (Solari connectivity check)."

    def handle(self, *args, **opts):
        try:
            from bench.solari import SolariClient
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"bench.solari import failed: {exc}") from exc

        t0 = time.time()
        try:
            with SolariClient.from_env(launch_timeout_s=90) as solari:
                with solari.launch_sandbox(timeout_ms=60_000) as box:
                    r = box.exec("echo", args=["bench smoke ok"])
                    self.stdout.write(f"sandbox {box.id[:32]}…  exec exit={r.exitCode}")
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"Solari smoke failed: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"ok — booted and destroyed one sandbox in {time.time() - t0:.1f}s"))
