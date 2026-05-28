from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from loguru import logger

import config


@dataclass
class MatchResult:
    name: str
    score: float
    location: tuple[int, int]


def bundled_templates_dir() -> Path:
    import sys

    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS"))
    else:
        base = Path(__file__).resolve().parent
    return base / "templates"


def load_templates(names: list[str], ratio: float = 1.0) -> dict[str, np.ndarray]:
    """載入模板並按 ratio 縮放。

    ratio = 視窗高度 / 模板參考高度（例如 1080/2160 = 0.5）。
    """
    bundled = bundled_templates_dir()
    user = config.user_templates_dir()
    out: dict[str, np.ndarray] = {}

    for name in names:
        filename = f"{name}.png"
        user_path = user / filename
        bundled_path = bundled / filename

        path = user_path if user_path.exists() else bundled_path

        if not path.exists():
            logger.warning("Missing template: {}", name)
            continue

        img = cv2.imdecode(
            np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE
        )

        if img is None:
            logger.warning("Failed to read template: {}", path)
            continue

        if ratio != 1.0 and ratio > 0:
            height, width = img.shape[:2]
            img = cv2.resize(
                img,
                (max(1, int(round(width * ratio))), max(1, int(round(height * ratio)))),
                interpolation=cv2.INTER_AREA,
            )

        out[name] = img

    return out


def to_gray(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return frame

    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def match_one(frame: np.ndarray, template: np.ndarray) -> tuple[float, tuple[int, int]]:
    frame = to_gray(frame)

    frame_height, frame_width = frame.shape[:2]
    template_height, template_width = template.shape[:2]

    if template_height > frame_height or template_width > frame_width:
        scale = min(frame_height / template_height, frame_width / template_width) * 0.95
        template = cv2.resize(
            template,
            (max(1, int(template_width * scale)), max(1, int(template_height * scale))),
        )

    res = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)

    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    return float(max_val), (int(max_loc[0]), int(max_loc[1]))


def best_match(
    frame: np.ndarray,
    templates: dict[str, np.ndarray],
    expected: str | None = None,
    early_threshold: float | None = None,
) -> MatchResult | None:
    frame = to_gray(frame)

    best: MatchResult | None = None

    if expected and expected in templates:
        score, loc = match_one(frame, templates[expected])
        best = MatchResult(name=expected, score=score, location=loc)
        if early_threshold is not None and score >= early_threshold:
            return best

    for name, tpl in templates.items():
        if name == expected:
            continue
        score, loc = match_one(frame, tpl)
        if best is None or score > best.score:
            best = MatchResult(name=name, score=score, location=loc)

    return best
