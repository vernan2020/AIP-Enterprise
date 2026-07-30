from __future__ import annotations

from aip.platform.observability.metrics.counter import Counter
from aip.platform.observability.metrics.gauge import Gauge
from aip.platform.observability.metrics.histogram import Histogram
from aip.platform.observability.metrics.timer import Timer


class MetricsRegistry:
    def __init__(self) -> None:
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._timers: dict[str, Timer] = {}

    def counter(self, name: str) -> Counter:
        if name not in self._counters:
            self._counters[name] = Counter(name)
        return self._counters[name]

    def gauge(self, name: str) -> Gauge:
        if name not in self._gauges:
            self._gauges[name] = Gauge(name)
        return self._gauges[name]

    def histogram(self, name: str) -> Histogram:
        if name not in self._histograms:
            self._histograms[name] = Histogram(name)
        return self._histograms[name]

    def timer(self, name: str) -> Timer:
        if name not in self._timers:
            self._timers[name] = Timer(name)
        return self._timers[name]

    def snapshot(self) -> dict[str, object]:
        snapshot: dict[str, object] = {}
        for name, counter in self._counters.items():
            snapshot[name] = counter.snapshot()
        for name, gauge in self._gauges.items():
            snapshot[name] = gauge.snapshot()
        for name, histogram in self._histograms.items():
            snapshot[name] = histogram.snapshot()
        for name, timer in self._timers.items():
            snapshot[name] = timer.snapshot()
        return snapshot
