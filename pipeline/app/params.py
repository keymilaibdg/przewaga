"""Per-league model parameters chosen by the ETAP 5 walk-forward backtest.

`app/calibration.json` is written by `python -m app.backtest run` (GitHub Actions, workflow "Backtest i kalibracja")
and read by the daily pipeline. Without the file every league falls back to the ETAP 4 defaults below.

Status of a league (per market):
  validated   the blended model beat the de-vigged market out of sample -> recommendations allowed
  validating  model computed and shown, but no evidence yet that it beats the market -> no recommendations
  market_only no model for the competition -> odds only
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import LEAGUE_BY_KEY, MAX_DISAGREEMENT, MIN_EV, MIN_QUALITY, MODEL_WEIGHT

CALIBRATION_PATH = Path(__file__).resolve().parent / "calibration.json"

STATUS_LABEL = {
    "validated": "zweryfikowany w backteście",
    "validating": "w walidacji",
    "market_only": "tylko kursy rynku",
}


@dataclass(frozen=True)
class MarketParams:
    model_weight: float = MODEL_WEIGHT  # share of the model in the final probability (rest: de-vigged market)
    hw_scale: float = 1.0  # multiplies the model's uncertainty half-width (calibrated out of sample)
    status: str = "validated"
    reason: str = ""


@dataclass(frozen=True)
class LeagueParams:
    league_key: str
    status: str = "validated"  # best status among markets (see module doc)
    reason: str = ""
    min_ev: float = MIN_EV
    min_quality: int = MIN_QUALITY
    max_disagreement: float = MAX_DISAGREEMENT
    xi: float | None = None  # time decay of the model; None = model default
    fatigue: bool = False  # basketball: schedule features (rest, back-to-back, travel) in the model
    markets: dict[str, MarketParams] = field(default_factory=dict)
    calibrated_at: str | None = None

    def market(self, market: str) -> MarketParams:
        return self.markets.get(market) or MarketParams(status=self.status, reason=self.reason)

    def weight(self, market: str) -> float:
        return self.market(market).model_weight

    def can_recommend(self, market: str) -> bool:
        return self.market(market).status == "validated"

    @property
    def has_model(self) -> bool:
        return self.status != "market_only"


def default_params(league_key: str) -> LeagueParams:
    lg = LEAGUE_BY_KEY.get(league_key)
    status = "validated" if (lg is None or lg.recommend) else "market_only"
    return LeagueParams(league_key, status=status)


def _from_json(key: str, d: dict[str, Any], calibrated_at: str | None) -> LeagueParams:
    markets = {
        m: MarketParams(
            model_weight=float(v.get("model_weight", MODEL_WEIGHT)),
            hw_scale=float(v.get("hw_scale", 1.0)),
            status=v.get("status", "validating"),
            reason=v.get("reason", ""),
        )
        for m, v in (d.get("markets") or {}).items()
    }
    statuses = [m.status for m in markets.values()] or [d.get("status", "validating")]
    status = d.get("status") or ("validated" if "validated" in statuses else "validating" if "validating" in statuses else "market_only")
    return LeagueParams(
        key,
        status=status,
        reason=d.get("reason", ""),
        min_ev=float(d.get("min_ev", MIN_EV)),
        min_quality=int(d.get("min_quality", MIN_QUALITY)),
        max_disagreement=float(d.get("max_disagreement", MAX_DISAGREEMENT)),
        xi=d.get("xi"),
        fatigue=bool(d.get("fatigue", False)),
        markets=markets,
        calibrated_at=calibrated_at,
    )


def load(path: Path | str | None = None) -> dict[str, LeagueParams]:
    """All leagues. PRZEWAGA_CALIBRATION overrides the path ('' or 'none' = defaults only, used by tests)."""
    env = os.environ.get("PRZEWAGA_CALIBRATION")
    if path is None:
        path = CALIBRATION_PATH if env is None else (None if env.strip().lower() in ("", "none") else Path(env))
    out = {k: default_params(k) for k in LEAGUE_BY_KEY}
    if path is None or not Path(path).exists():
        return out
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    for key, d in (raw.get("leagues") or {}).items():
        if key in out:
            out[key] = _from_json(key, d, raw.get("generated_at"))
    return out
