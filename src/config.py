import configparser
from dataclasses import dataclass
from pathlib import Path
import ctypes
from ctypes import wintypes

APP_NAME = "fh6-automation"


def get_documents_dir() -> Path:
    try:
        CSIDL_PERSONAL = 5  # My Documents
        SHGFP_TYPE_CURRENT = 0

        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        # 第二參數須為 c_int,直接傳 Python int 即可。
        res = ctypes.windll.shell32.SHGetFolderPathW(
            None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf
        )
        if res == 0 and buf.value:
            return Path(buf.value)
    except Exception:
        pass
    return Path.home() / "Documents"


def user_data_dir() -> Path:
    documents_dir = get_documents_dir() / APP_NAME
    documents_dir.mkdir(parents=True, exist_ok=True)
    return documents_dir


def config_path() -> Path:
    return user_data_dir() / "config.ini"


def user_templates_dir() -> Path:
    templates_dir = user_data_dir() / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    return templates_dir


def logs_dir() -> Path:
    logs_dir = user_data_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


@dataclass
class GeneralCfg:
    dry_run: bool = False
    always_on_top: bool = True
    auto_update: bool = True


@dataclass
class CaptureCfg:
    backend: str = "auto"  # auto | bettercam | mss
    fps: int = 10


@dataclass
class MatchCfg:
    threshold: float = 0.85
    stale_timeout_ms: int = 1500
    stuck_timeout_ms: int = 4000
    scale: float = 0.5


@dataclass
class InputCfg:
    press_hold_ms: int = 90
    between_press_ms: int = 200
    jitter_ms: int = 60


@dataclass
class FarmSPCfg:
    target_runs: int = 50


@dataclass
class BuyCarCfg:
    quantity: int = 33


@dataclass
class UpgradeCarCfg:
    quantity: int = 33


@dataclass
class DeleteCfg:
    quantity: int = 33


@dataclass
class Config:
    general: GeneralCfg
    capture: CaptureCfg
    match: MatchCfg
    input: InputCfg
    farm_sp: FarmSPCfg
    buy_car: BuyCarCfg
    upgrade_car: UpgradeCarCfg
    delete: DeleteCfg


def get_defaults() -> Config:
    return Config(
        general=GeneralCfg(),
        capture=CaptureCfg(),
        match=MatchCfg(),
        input=InputCfg(),
        farm_sp=FarmSPCfg(),
        buy_car=BuyCarCfg(),
        upgrade_car=UpgradeCarCfg(),
        delete=DeleteCfg(),
    )


DEFAULT_INI_TEMPLATE = """\
; fh6-automation 設定檔
; 編輯後請重啟程式，或直接從 GUI 修改。

[general]
; dry_run = true 時只跑導航流程，不實際執行消耗操作。
dry_run = {defaults.general.dry_run}
always_on_top = {defaults.general.always_on_top}
auto_update = {defaults.general.auto_update}

[capture]
; auto -> 優先使用 bettercam (較快),失敗會退回 mss
backend = {defaults.capture.backend}
fps = {defaults.capture.fps}

[match]
threshold = {defaults.match.threshold}
stale_timeout_ms = {defaults.match.stale_timeout_ms}
stuck_timeout_ms = {defaults.match.stuck_timeout_ms}
; 比對前縮放畫面與模板。1.0 = 原尺寸，0.5 約快 4 倍。
scale = {defaults.match.scale}

[input]
press_hold_ms = {defaults.input.press_hold_ms}
between_press_ms = {defaults.input.between_press_ms}
jitter_ms = {defaults.input.jitter_ms}

[farm_sp]
; 要刷幾次，必須 >= 1。
target_runs = {defaults.farm_sp.target_runs}

[buy_car]
; 要買幾輛，必須 >= 1。
quantity = {defaults.buy_car.quantity}

[upgrade_car]
; 要升級幾輛，必須 >= 1。
quantity = {defaults.upgrade_car.quantity}

[delete]
; 要從車庫刪除幾輛，必須 >= 1。
quantity = {defaults.delete.quantity}
"""


def get_default_ini() -> str:
    defaults = get_defaults()
    return DEFAULT_INI_TEMPLATE.format(defaults=defaults)


def ensure_default(path: Path) -> None:
    if not path.exists():
        path.write_text(get_default_ini(), encoding="utf-8")


def load() -> Config:
    path = config_path()
    ensure_default(path)

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    defaults = get_defaults()

    return Config(
        general=GeneralCfg(
            dry_run=parser.getboolean(
                "general", "dry_run", fallback=defaults.general.dry_run
            ),
            always_on_top=parser.getboolean(
                "general", "always_on_top", fallback=defaults.general.always_on_top
            ),
            auto_update=parser.getboolean(
                "general", "auto_update", fallback=defaults.general.auto_update
            ),
        ),
        capture=CaptureCfg(
            backend=parser.get("capture", "backend", fallback=defaults.capture.backend),
            fps=parser.getint("capture", "fps", fallback=defaults.capture.fps),
        ),
        match=MatchCfg(
            threshold=parser.getfloat(
                "match", "threshold", fallback=defaults.match.threshold
            ),
            stale_timeout_ms=parser.getint(
                "match", "stale_timeout_ms", fallback=defaults.match.stale_timeout_ms
            ),
            stuck_timeout_ms=parser.getint(
                "match", "stuck_timeout_ms", fallback=defaults.match.stuck_timeout_ms
            ),
            scale=parser.getfloat("match", "scale", fallback=defaults.match.scale),
        ),
        input=InputCfg(
            press_hold_ms=parser.getint(
                "input", "press_hold_ms", fallback=defaults.input.press_hold_ms
            ),
            between_press_ms=parser.getint(
                "input", "between_press_ms", fallback=defaults.input.between_press_ms
            ),
            jitter_ms=parser.getint(
                "input", "jitter_ms", fallback=defaults.input.jitter_ms
            ),
        ),
        farm_sp=FarmSPCfg(
            target_runs=max(
                1,
                parser.getint(
                    "farm_sp", "target_runs", fallback=defaults.farm_sp.target_runs
                ),
            ),
        ),
        buy_car=BuyCarCfg(
            quantity=max(
                1,
                parser.getint(
                    "buy_car", "quantity", fallback=defaults.buy_car.quantity
                ),
            ),
        ),
        upgrade_car=UpgradeCarCfg(
            quantity=max(
                1,
                parser.getint(
                    "upgrade_car", "quantity", fallback=defaults.upgrade_car.quantity
                ),
            ),
        ),
        delete=DeleteCfg(
            quantity=max(
                1,
                parser.getint("delete", "quantity", fallback=defaults.delete.quantity),
            ),
        ),
    )


def save(conf: Config) -> None:
    parser = configparser.ConfigParser()
    parser["general"] = {
        "dry_run": str(conf.general.dry_run),
        "always_on_top": str(conf.general.always_on_top),
        "auto_update": str(conf.general.auto_update),
    }
    parser["capture"] = {
        "backend": conf.capture.backend,
        "fps": str(conf.capture.fps),
    }
    parser["match"] = {
        "threshold": str(conf.match.threshold),
        "stale_timeout_ms": str(conf.match.stale_timeout_ms),
        "stuck_timeout_ms": str(conf.match.stuck_timeout_ms),
        "scale": str(conf.match.scale),
    }
    parser["input"] = {
        "press_hold_ms": str(conf.input.press_hold_ms),
        "between_press_ms": str(conf.input.between_press_ms),
        "jitter_ms": str(conf.input.jitter_ms),
    }
    parser["farm_sp"] = {
        "target_runs": str(conf.farm_sp.target_runs),
    }
    parser["buy_car"] = {
        "quantity": str(conf.buy_car.quantity),
    }
    parser["upgrade_car"] = {
        "quantity": str(conf.upgrade_car.quantity),
    }
    parser["delete"] = {
        "quantity": str(conf.delete.quantity),
    }
    with open(config_path(), "w", encoding="utf-8") as f:
        parser.write(f)


def reset() -> None:
    p = config_path()
    if p.exists():
        p.unlink()
