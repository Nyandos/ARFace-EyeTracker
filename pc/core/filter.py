import math
import time
from typing import Tuple, Optional

class LowPassFilter:
    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        self.s = None

    def reset(self):
        self.s = None

    def filter(self, value: float, alpha: Optional[float] = None) -> float:
        if alpha is not None:
            self.alpha = alpha
        if self.s is None:
            self.s = value
        else:
            self.s = self.alpha * value + (1.0 - self.alpha) * self.s
        return self.s


class OneEuroFilter:
    """
    1€ Filter with anti-jitter tuning for ultra-smooth pointer tracking.
    - min_cutoff: Cutoff at near-zero speed (smaller = ultra-smooth / zero jitter)
    - beta: Speed coefficient (moderate = smooth acceleration without sudden jump)
    - d_cutoff: Derivative cutoff
    """
    def __init__(self, min_cutoff: float = 0.4, beta: float = 0.008, d_cutoff: float = 1.0):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)

        self.x_filter = LowPassFilter()
        self.dx_filter = LowPassFilter()
        self.last_time = None

    def reset(self):
        self.x_filter.reset()
        self.dx_filter.reset()
        self.last_time = None

    def _alpha(self, cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filter(self, x: float, timestamp: Optional[float] = None) -> float:
        if timestamp is None:
            timestamp = time.perf_counter()

        if self.last_time is None:
            self.last_time = timestamp
            return self.x_filter.filter(x, alpha=1.0)

        dt = timestamp - self.last_time
        self.last_time = timestamp
        if dt <= 0.0:
            dt = 0.001

        prev_x = self.x_filter.s if self.x_filter.s is not None else x
        dx = (x - prev_x) / dt
        edx = self.dx_filter.filter(dx, alpha=self._alpha(self.d_cutoff, dt))

        # Dynamic cutoff: strictly capped to prevent teleporting spikes
        cutoff = self.min_cutoff + self.beta * min(abs(edx), 500.0)
        return self.x_filter.filter(x, alpha=self._alpha(cutoff, dt))


class GazePointFilter:
    """
    Dual-axis Gaze Filter with 1€ Filter and spatial interpolation.
    """
    def __init__(self, min_cutoff: float = 0.4, beta: float = 0.008):
        self.filter_x = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        self.filter_y = OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
        self.smoothed_x: Optional[float] = None
        self.smoothed_y: Optional[float] = None

    def update_params(self, min_cutoff: float, beta: float):
        self.filter_x.min_cutoff = min_cutoff
        self.filter_x.beta = beta
        self.filter_y.min_cutoff = min_cutoff
        self.filter_y.beta = beta

    def reset(self):
        self.filter_x.reset()
        self.filter_y.reset()
        self.smoothed_x = None
        self.smoothed_y = None

    def filter(self, x: float, y: float, timestamp: Optional[float] = None) -> Tuple[float, float]:
        fx = self.filter_x.filter(x, timestamp)
        fy = self.filter_y.filter(y, timestamp)

        if self.smoothed_x is None:
            self.smoothed_x = fx
            self.smoothed_y = fy
        else:
            # Secondary exponential smoothing for butter-smooth visual glide
            alpha = 0.65
            self.smoothed_x = alpha * fx + (1.0 - alpha) * self.smoothed_x
            self.smoothed_y = alpha * fy + (1.0 - alpha) * self.smoothed_y

        return float(self.smoothed_x), float(self.smoothed_y)
