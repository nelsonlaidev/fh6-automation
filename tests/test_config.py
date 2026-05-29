from pathlib import Path

import pytest

import config


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """讓所有 config 測試使用獨立的暫存目錄。"""
    monkeypatch.setattr(config, "user_data_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.ini")


class TestGetDefaults:
    def test_returns_config(self):
        cfg = config.get_defaults()
        assert isinstance(cfg, config.Config)
        assert cfg.general.dry_run is False
        assert cfg.match.threshold == 0.85
        assert cfg.farm_sp.target_runs == 50


class TestLoad:
    def test_creates_default_file(self):
        cfg = config.load()
        assert (config.config_path()).exists()
        assert cfg.general.dry_run is False

    def test_reads_custom_values(self):
        ini = "[general]\ndry_run = true\n[farm_sp]\ntarget_runs = 10\n"
        config.config_path().write_text(ini, encoding="utf-8")

        cfg = config.load()
        assert cfg.general.dry_run is True
        assert cfg.farm_sp.target_runs == 10

    def test_quantity_minimum_is_one(self):
        ini = "[buy_car]\nquantity = 0\n"
        config.config_path().write_text(ini, encoding="utf-8")

        cfg = config.load()
        assert cfg.buy_car.quantity == 1


class TestSave:
    def test_roundtrip(self):
        cfg = config.get_defaults()
        cfg.general.dry_run = True
        cfg.capture.fps = 30
        config.save(cfg)

        loaded = config.load()
        assert loaded.general.dry_run is True
        assert loaded.capture.fps == 30


class TestReset:
    def test_removes_config_file(self):
        config.load()  # ensure file exists
        assert config.config_path().exists()

        config.reset()
        assert not config.config_path().exists()

    def test_reset_no_file_no_error(self):
        config.reset()  # 不應 raise
