"""The rate card: how usage becomes dollars.

The numbers shipped in ``default_rates.yaml`` are **estimates** for demo
budgeting, not billed prices. Point ``BENCH_RATE_CARD_PATH`` at a file with your
real rates, or pass a :class:`RateCard` built from your latest invoice.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .errors import MeteringConfigError

_DEFAULT_RATES_PATH = Path(__file__).with_name("default_rates.yaml")


@dataclass(frozen=True)
class ModelRate:
    input_usd_per_mtok: float
    output_usd_per_mtok: float

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens / 1_000_000 * self.input_usd_per_mtok
            + output_tokens / 1_000_000 * self.output_usd_per_mtok
        )


@dataclass(frozen=True)
class RateCard:
    #: USD per machine-second, by machine kind (sandbox / browser / desktop).
    machine_usd_per_second: Mapping[str, float] = field(default_factory=dict)
    #: Flat USD per launch, by machine kind. Optional.
    machine_launch_usd: Mapping[str, float] = field(default_factory=dict)
    #: LLM rates by model key; lookup is exact, then longest-prefix.
    llm: Mapping[str, ModelRate] = field(default_factory=dict)

    # -- machine ------------------------------------------------------

    def machine_time_cost(self, kind: str, seconds: float) -> float:
        if seconds < 0:
            raise MeteringConfigError("seconds must be >= 0")
        return max(0.0, seconds) * self.machine_usd_per_second.get(kind.lower(), 0.0)

    def launch_cost(self, kind: str) -> float:
        return self.machine_launch_usd.get(kind.lower(), 0.0)

    # -- llm --------------------------------------------------------

    def resolve_model(self, model: str) -> str | None:
        """Match a model id to a rate key: exact, then the longest key that is a
        prefix of the id (so ``claude-sonnet-5`` resolves to ``claude-sonnet``)."""

        if model in self.llm:
            return model
        candidates = [k for k in self.llm if model.startswith(k)]
        return max(candidates, key=len) if candidates else None

    def llm_cost(self, model: str, input_tokens: int, output_tokens: int) -> tuple[float, str | None]:
        """Returns ``(usd, matched_key)``. An unknown model costs 0.0 and returns
        ``None`` as the key so the caller can flag it."""

        key = self.resolve_model(model)
        if key is None:
            return 0.0, None
        return self.llm[key].cost(input_tokens, output_tokens), key

    # -- construction ---------------------------------------------

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RateCard":
        try:
            machine = {str(k).lower(): float(v) for k, v in (data.get("machine_usd_per_second") or {}).items()}
            launch = {str(k).lower(): float(v) for k, v in (data.get("machine_launch_usd") or {}).items()}
            llm_raw = data.get("llm_usd_per_mtok") or data.get("llm") or {}
            llm: dict[str, ModelRate] = {}
            for name, rate in llm_raw.items():
                if isinstance(rate, Mapping):
                    llm[str(name)] = ModelRate(
                        float(rate.get("input", rate.get("input_usd_per_mtok", 0.0))),
                        float(rate.get("output", rate.get("output_usd_per_mtok", 0.0))),
                    )
                elif isinstance(rate, (list, tuple)) and len(rate) == 2:
                    llm[str(name)] = ModelRate(float(rate[0]), float(rate[1]))
                else:
                    raise MeteringConfigError(f"llm rate for {name!r} must be a mapping or [in, out] pair")
        except (TypeError, ValueError) as exc:
            raise MeteringConfigError(f"invalid rate card: {exc}") from exc
        return cls(machine_usd_per_second=machine, machine_launch_usd=launch, llm=llm)

    @classmethod
    def from_file(cls, path: str | os.PathLike[str]) -> "RateCard":
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8")
        except OSError as exc:
            raise MeteringConfigError(f"cannot read rate card {p}: {exc}") from exc
        if p.suffix in (".yaml", ".yml"):
            import yaml

            try:
                data = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                raise MeteringConfigError(f"invalid YAML in {p}: {exc}") from exc
        else:
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise MeteringConfigError(f"invalid JSON in {p}: {exc}") from exc
        if not isinstance(data, Mapping):
            raise MeteringConfigError(f"{p}: expected a mapping at the top level")
        return cls.from_dict(data)


def default_rate_card() -> RateCard:
    return RateCard.from_file(_DEFAULT_RATES_PATH)


__all__ = ["RateCard", "ModelRate", "default_rate_card"]
