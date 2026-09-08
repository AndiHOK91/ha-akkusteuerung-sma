"""Rolling core statistics ported from packages/sma_statistik.yaml."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(slots=True)
class RollingMean:
    """Time-windowed arithmetic mean with an optional sample cap."""

    max_age: timedelta
    sampling_size: int
    _samples: deque[tuple[datetime, float]] = field(default_factory=deque)

    def add(self, timestamp: datetime, value: float) -> float:
        """Add one sample and return the current mean."""
        self._samples.append((timestamp, float(value)))
        self._trim(timestamp)
        return self.mean

    def _trim(self, now: datetime) -> None:
        cutoff = now - self.max_age
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()
        while len(self._samples) > self.sampling_size:
            self._samples.popleft()

    @property
    def mean(self) -> float:
        """Return arithmetic mean, or 0 for an empty window."""
        if not self._samples:
            return 0.0
        return sum(value for _timestamp, value in self._samples) / len(self._samples)

    @property
    def count(self) -> int:
        """Return number of samples currently contributing to the mean."""
        return len(self._samples)
