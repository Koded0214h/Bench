"""Policy engine configuration, resolved from ``POLICY_*`` environment vars."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .models import Effect

# The default effect may only be DENY (allowlist posture — recommended) or
# AUDIT (permissive: allow anything unmatched, but flag it). Never ALLOW.
_ALLOWED_DEFAULTS = {Effect.DENY, Effect.AUDIT}


class PolicyConfigError(ValueError):
    """Invalid policy configuration."""


@dataclass(frozen=True)
class PolicyConfig:
    default_effect: Effect = Effect.DENY
    #: Extra YAML files or directories of ``*.yaml``, loaded after the defaults.
    rule_paths: tuple[str, ...] = field(default_factory=tuple)
    #: Skip the rule set bundled with this package.
    disable_defaults: bool = False

    def __post_init__(self) -> None:
        if self.default_effect not in _ALLOWED_DEFAULTS:
            raise PolicyConfigError(
                f"POLICY_DEFAULT_EFFECT must be DENY or AUDIT, got {self.default_effect.value}"
            )

    @classmethod
    def from_env(cls, **overrides: object) -> "PolicyConfig":
        raw_default = os.environ.get("POLICY_DEFAULT_EFFECT", "DENY") or "DENY"
        try:
            default_effect = Effect.parse(raw_default)
        except ValueError as exc:
            raise PolicyConfigError(str(exc)) from exc

        raw_paths = os.environ.get("POLICY_RULES_PATH", "")
        rule_paths = tuple(p for p in raw_paths.split(os.pathsep) if p.strip())

        disable_defaults = _env_bool("POLICY_DISABLE_DEFAULTS", False)

        values: dict[str, object] = {
            "default_effect": default_effect,
            "rule_paths": rule_paths,
            "disable_defaults": disable_defaults,
        }
        values.update(overrides)
        return cls(**values)  # type: ignore[arg-type]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
