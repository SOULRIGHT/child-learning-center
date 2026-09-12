"""Absolute request deadline. Growth AI Deadline와 분리한다."""
from __future__ import annotations

import time

from features.assistant.failures import AssistantDeadlineError

MIN_CALL_S = 0.5


class RequestDeadline:
    def __init__(self, seconds, *, clock=None, start=None):
        self.clock = clock or time.monotonic
        self.seconds = float(seconds)
        self.start = self.clock() if start is None else float(start)

    def remaining(self):
        return self.seconds - (self.clock() - self.start)

    def expired(self, min_needed=MIN_CALL_S):
        return self.remaining() < min_needed

    def raise_if_expired(self, min_needed=MIN_CALL_S):
        if self.expired(min_needed=min_needed):
            raise AssistantDeadlineError()

    def provider_timeout(self, cap_s):
        remaining = self.remaining()
        if remaining <= 0:
            raise AssistantDeadlineError()
        return max(0.1, min(float(cap_s), remaining))

    def capped(self, seconds):
        """Same start as this deadline. Does not open a new 10s window per call."""
        return RequestDeadline(
            min(float(seconds), self.seconds),
            clock=self.clock,
            start=self.start,
        )
