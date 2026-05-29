import threading
import time
from unittest.mock import patch

from runner import Status, StepRunner, StopReason
import config


class TestStatus:
    def test_defaults(self):
        s = Status()
        assert s.running is False
        assert s.state == "-"
        assert s.score == 0.0
        assert s.progress == 0
        assert s.target == 1


class TestStepRunner:
    def make_runner(self):
        conf = config.get_defaults()
        runner = StepRunner(conf)
        runner.name = "test"
        runner.template_names = ["dummy"]
        return runner

    def test_initial_status(self):
        runner = self.make_runner()
        s = runner.get_status()
        assert s.running is False
        assert s.last_reason == ""

    def test_update_fields(self):
        runner = self.make_runner()
        runner.update(state="loading", score=0.95)
        s = runner.get_status()
        assert s.state == "loading"
        assert s.score == 0.95

    def test_finish_sets_reason(self):
        runner = self.make_runner()
        runner.start_time = time.monotonic() - 1.0
        runner.finish(StopReason.DONE, "完成")
        s = runner.get_status()
        assert s.running is False
        assert s.last_reason == "target_reached"
        assert s.message == "完成"
        assert s.elapsed_s >= 1.0

    def test_finish_user_stopped(self):
        runner = self.make_runner()
        runner.start_time = time.monotonic()
        runner.finish_user_stopped()
        s = runner.get_status()
        assert s.last_reason == StopReason.USER.value

    def test_mark_declined_when_not_running(self):
        runner = self.make_runner()
        runner.mark_declined("已取消")
        s = runner.get_status()
        assert s.last_reason == StopReason.USER_DECLINED.value
        assert s.message == "已取消"

    def test_stop_sets_event(self):
        runner = self.make_runner()
        assert not runner.stop_evt.is_set()
        runner.stop()
        assert runner.stop_evt.is_set()

    def test_get_state_label(self):
        runner = self.make_runner()
        runner.state_labels = {"driving": "行駛中"}
        assert runner.get_state_label("driving") == "行駛中"
        assert runner.get_state_label("unknown") == "unknown"
        assert runner.get_state_label("-") == "—"
