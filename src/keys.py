import random
import time
from contextlib import contextmanager

import pydirectinput as pdi
from loguru import logger

pdi.PAUSE = 0
pdi.FAILSAFE = False


def sleep_ms(ms: int, jitter_ms: int = 0) -> None:
    extra = random.uniform(0, jitter_ms) if jitter_ms > 0 else 0
    time.sleep((ms + extra) / 1000.0)


def tap(key: str, hold_ms: int = 90, gap_ms: int = 220, jitter_ms: int = 60) -> None:
    try:
        pdi.keyDown(key)
        logger.debug("keys: keyDown('{}') 成功", key)
    except Exception as e:
        logger.error("keys: keyDown('{}') 失敗：{}", key, e)
        return
    sleep_ms(hold_ms, jitter_ms)
    try:
        pdi.keyUp(key)
        logger.debug("keys: keyUp('{}') 成功（tap，hold={}ms）", key, hold_ms)
    except Exception as e:
        logger.error("keys: keyUp('{}') 失敗：{}", key, e)


def hold(key: str) -> None:
    try:
        pdi.keyDown(key)
        logger.debug("keys: hold('{}') 成功", key)
    except Exception as e:
        logger.error("keys: hold('{}') 失敗：{}", key, e)


def release(key: str) -> None:
    try:
        pdi.keyUp(key)
        logger.debug("keys: release('{}') 成功", key)
    except Exception as e:
        logger.error("keys: release('{}') 失敗：{}", key, e)


@contextmanager
def held(key: str):
    try:
        pdi.keyDown(key)
        logger.debug("keys: held('{}') 開始", key)
    except Exception as e:
        logger.error("keys: held('{}') keyDown 失敗：{}", key, e)
    try:
        yield
    finally:
        try:
            pdi.keyUp(key)
            logger.debug("keys: held('{}') 結束", key)
        except Exception as e:
            logger.error("keys: held('{}') keyUp 失敗：{}", key, e)
