"""
FSRS-5 Continuous Memory Engine Bridge.
Interconnects native FSRS-5 continuous retrievability formula:
R(t, S) = (1 + 19/81 * (t / S))^(-0.5)
Enforces 0.90 Target Retention and 4-lapse leech isolation.
"""
import math
from dataclasses import dataclass
from typing import Optional

@dataclass
class FSRSCardState:
    card_id: str
    stability: float  # S
    difficulty: float # D
    lapses: int
    last_review_ts: float

class FSRSEngineBridge:
    def __init__(self, target_retention: float = 0.90):
        self.target_retention = target_retention
        self.decay_factor = 19.0 / 81.0

    def compute_retrievability(self, delta_days: float, stability: float) -> float:
        if stability <= 0:
            return 0.0
        return math.pow(1.0 + self.decay_factor * (delta_days / stability), -0.5)

    def is_leech(self, lapses: int) -> bool:
        return lapses >= 4

    def next_interval_days(self, stability: float, target_r: Optional[float] = None) -> float:
        target_r = target_r or self.target_retention
        # R = (1 + (19/81) * (t / S))^-0.5
        # R^-2 = 1 + (19/81) * (t / S)
        # t = (R^-2 - 1) * (81/19) * S
        if target_r <= 0 or target_r >= 1:
            target_r = 0.90
        t = (math.pow(target_r, -2.0) - 1.0) * (81.0 / 19.0) * stability
        return max(0.1, round(t, 2))
