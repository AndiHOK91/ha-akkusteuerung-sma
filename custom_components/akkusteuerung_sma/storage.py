"""Persistent storage for balancing/deep-charge state."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .balancing import BalancingPersistentState
from .const import DOMAIN

STORAGE_VERSION = 1


class BalancingStorage:
    """Persist the state that upstream kept in counter/input_datetime helpers."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store[dict[str, Any]](
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.balancing.{entry_id}",
        )

    async def async_load(self) -> BalancingPersistentState:
        """Load persisted state, falling back to upstream-safe zeros."""
        data = await self._store.async_load() or {}
        last_completion = _parse_datetime(data.get("last_completion"))
        last_daily_increment = _parse_date(data.get("last_daily_increment"))
        raw_tick = data.get("last_minute_tick")
        tick = None
        if isinstance(raw_tick, list) and len(raw_tick) == 5:
            try:
                tick = tuple(int(value) for value in raw_tick)
            except (TypeError, ValueError):
                tick = None

        return BalancingPersistentState(
            days_since_full=max(0, int(data.get("days_since_full", 0))),
            done_minutes=max(0, int(data.get("done_minutes", 0))),
            last_completion=last_completion,
            completion_valid=bool(data.get("completion_valid", False)),
            last_daily_increment=last_daily_increment,
            last_minute_tick=tick,
        )

    async def async_save(self, state: BalancingPersistentState) -> None:
        """Persist the complete balancing state."""
        await self._store.async_save(
            {
                "days_since_full": state.days_since_full,
                "done_minutes": state.done_minutes,
                "last_completion": (
                    state.last_completion.isoformat() if state.last_completion else None
                ),
                "completion_valid": state.completion_valid,
                "last_daily_increment": (
                    state.last_daily_increment.isoformat()
                    if state.last_daily_increment
                    else None
                ),
                "last_minute_tick": (
                    list(state.last_minute_tick) if state.last_minute_tick else None
                ),
            }
        )


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
