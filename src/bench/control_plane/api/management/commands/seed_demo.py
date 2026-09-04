"""Create a demo user so you can log into the frontend immediately."""

from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a demo user (BENCH_DEMO_USER / BENCH_DEMO_PASSWORD, default demo / bench-demo-pass)."

    def handle(self, *args, **opts):
        User = get_user_model()
        username = os.environ.get("BENCH_DEMO_USER", "demo")
        password = os.environ.get("BENCH_DEMO_PASSWORD", "bench-demo-pass")
        user, made = User.objects.get_or_create(username=username)
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f"demo user {'created' if made else 'password reset'}: {username} / {password}"))
