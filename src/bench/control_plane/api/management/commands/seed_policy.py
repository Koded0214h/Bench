"""Load bench.policy's bundled default rule set into the PolicyRule table."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from bench.policy.engine import _DEFAULT_POLICY_PATH, PolicySet

from bench.control_plane.api.models import PolicyRule


class Command(BaseCommand):
    help = "Seed the default policy set into the database."

    def add_arguments(self, parser):
        parser.add_argument("--replace", action="store_true", help="delete existing rules first")

    def handle(self, *args, **opts):
        if opts["replace"]:
            PolicyRule.objects.all().delete()
        rules = PolicySet.from_file(_DEFAULT_POLICY_PATH).validate()
        created = 0
        for i, rule in enumerate(rules):
            _, made = PolicyRule.objects.update_or_create(
                name=rule.name,
                defaults=dict(match=rule.match, effect=rule.effect.value,
                              reason=rule.reason, enabled=rule.enabled, priority=i),
            )
            created += int(made)
        self.stdout.write(self.style.SUCCESS(
            f"seeded {len(rules)} rules ({created} new, {len(rules) - created} updated)"))
