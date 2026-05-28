import random
import time
from contextlib import contextmanager

import pydirectinput as pdi

pdi.PAUSE = 0
pdi.FAILSAFE = False


def sleep_ms(ms: int, jitter_ms: int = 0) -> None:
    extra = random.uniform(0, jitter_ms) if jitter_ms > 0 else 0
    time.sleep((ms + extra) / 1000.0)


def tap(key: str, hold_ms: int = 90, gap_ms: int = 220, jitter_ms: int = 60) -> None:
    pdi.keyDown(key)
    sleep_ms(hold_ms, jitter_ms)
    pdi.keyUp(key)
    sleep_ms(gap_ms, jitter_ms)


def hold(key: str) -> None:
    pdi.keyDown(key)


def release(key: str) -> None:
    pdi.keyUp(key)


@contextmanager
def held(key: str):
    pdi.keyDown(key)
    try:
        yield
    finally:
        pdi.keyUp(key)
