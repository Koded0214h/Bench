"""Capture a browser login once, by hand, and save it as a Solari profile.

    python manage.py capture_session --tool salesforce

Opens a cloud browser, hands you a DevTools URL to drive it, waits while you log
in, then saves the session's cookies + localStorage as a profile named after the
tool. Workers reuse it with ``launch_browser(profile="<tool>")`` — your password
is never held by an agent.
"""

from __future__ import annotations

import sys

from django.core.management.base import BaseCommand, CommandError

_LOGIN_URLS = {
    "salesforce": "https://login.salesforce.com/",
    "hubspot": "https://app.hubspot.com/login",
    "notion": "https://www.notion.so/login",
    "linear": "https://linear.app/login",
    "gmail": "https://accounts.google.com/",
    "github": "https://github.com/login",
}


class Command(BaseCommand):
    help = "Open a live browser, log in by hand, and save the session as a profile."

    def add_arguments(self, parser):
        parser.add_argument("--tool", required=True, help="profile name, e.g. salesforce")
        parser.add_argument("--url", help="login URL (defaults to a known one for the tool)")
        parser.add_argument("--keep", action="store_true", help="do not release the session after saving")

    def handle(self, *args, **opts):
        tool = opts["tool"].strip().lower()
        url = opts["url"] or _LOGIN_URLS.get(tool)
        if not url:
            raise CommandError(f"no known login URL for {tool!r}; pass --url")

        try:
            from patchright.sync_api import sync_playwright
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"patchright is required: {exc}") from exc

        from bench.cli import load_dotenv

        load_dotenv()

        from bench.solari import SolariClient

        client = SolariClient.from_env()
        try:
            profiles = {p.name: p for p in client.list_profiles()}
            profile = profiles.get(tool) or client.create_profile(tool)
            self.stdout.write(f"profile: {profile.name} ({profile.id})")

            handle = client.launch_browser(profile_id=profile.id, stealth=True, launch_timeout_s=120)
            self.stdout.write(self.style.WARNING("\n  A cloud browser is open. Drive it from Chrome DevTools:\n"))
            self.stdout.write(f"    1. open  chrome://inspect/#devices  in your local Chrome")
            self.stdout.write(f"    2. Configure… → add this endpoint:")
            self.stdout.write(f"       {handle.cdp_endpoint}")
            self.stdout.write(f"    3. click 'inspect' under the remote target, then load: {url}")
            self.stdout.write(f"    4. log in fully (including any 2FA)\n")

            with sync_playwright() as pw:
                browser = pw.chromium.connect(handle.ws_endpoint)
                ctx = browser.contexts[0] if browser.contexts else browser.new_context()
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto(url, wait_until="load")
                self.stdout.write(f"  opened {url} in the session — log in there, then…")
                try:
                    input("  press Enter here once you are logged in: ")
                except EOFError:
                    raise CommandError("no stdin; run this in a terminal")
                state = ctx.storage_state()
                browser.close()

            result = client._loop.run(  # persist the captured state onto the profile
                client._browser().profiles.save(profile.id, state), timeout=30.0
            )
            self.stdout.write(self.style.SUCCESS(
                f"\nsaved profile '{tool}' v{getattr(result, 'version', '?')} "
                f"({getattr(result, 'size_bytes', '?')} bytes). "
                f"Workers: launch_browser(profile='{tool}')."))

            if not opts["keep"]:
                handle.close()
        finally:
            client.close()
