"""Create (or reuse) a user and optionally mint a SimpleJWT pair for it."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from rest_framework_simplejwt.tokens import RefreshToken


class Command(BaseCommand):
    help = "Provision a user and a JWT for API access."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="bench")
        parser.add_argument("--password", help="set/reset a usable password (enables /api/auth/token login)")
        parser.add_argument("--superuser", action="store_true")
        parser.add_argument("--print", action="store_true", help="print the tokens")

    def handle(self, *args, **opts):
        User = get_user_model()
        user, made = User.objects.get_or_create(
            username=opts["username"],
            defaults={"is_staff": opts["superuser"], "is_superuser": opts["superuser"]},
        )
        if opts["password"]:
            user.set_password(opts["password"])
            user.save()
        elif made:
            user.set_unusable_password()
            user.save()

        self.stdout.write(self.style.SUCCESS(f"user {user.username} ({'created' if made else 'exists'})"))
        if opts["print"]:
            pair = RefreshToken.for_user(user)
            self.stdout.write(f"ACCESS  {pair.access_token}")
            self.stdout.write(f"REFRESH {pair}")
