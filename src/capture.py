from typing import Protocol

import numpy as np
from loguru import logger

from window import Rect


class Grabber(Protocol):
    def grab(self, rect: Rect) -> np.ndarray | None: ...
    def close(self) -> None: ...


class BetterCamGrabber:
    def __init__(self) -> None:
        import bettercam

        self.cam = bettercam.create(output_color="BGR")
        self.last_frame: np.ndarray = np.empty((0, 0, 3), dtype=np.uint8)

    def grab(self, rect: Rect) -> np.ndarray | None:
        region = (rect.left, rect.top, rect.right, rect.bottom)
        frame = self.cam.grab(region=region)

        if frame is not None:
            self.last_frame = frame
            return frame

        if self.last_frame.size == 0:
            return None

        return self.last_frame

    def close(self) -> None:
        pass


class MssGrabber:
    def __init__(self) -> None:
        import mss

        self.sct = mss.mss()

    def grab(self, rect: Rect) -> np.ndarray:
        region = {
            "left": rect.left,
            "top": rect.top,
            "width": rect.width,
            "height": rect.height,
        }
        shot = self.sct.grab(region)
        arr = np.asarray(shot, dtype=np.uint8)

        return arr[:, :, :3]

    def close(self) -> None:
        try:
            self.sct.close()
        except Exception:
            pass


def make_grabber(backend: str = "auto") -> Grabber:
    backend = backend.lower()

    if backend in ("auto", "bettercam"):
        try:
            return BetterCamGrabber()
        except Exception as e:
            logger.warning("bettercam unavailable ({}); falling back to mss", e)

            if backend == "bettercam":
                raise

    return MssGrabber()
