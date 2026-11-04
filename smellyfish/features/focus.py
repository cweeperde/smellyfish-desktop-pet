"""A small pomodoro timer: focus phase, then a break, then ask whether to continue."""
import time

from PySide6.QtCore import QObject, QTimer, Signal


class FocusTimer(QObject):
    phase_end = Signal(str)          # "focus" or "break"
    changed = Signal()

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.phase = None             # None, "focus", "break"
        self.ends_at = 0.0
        self.timer = QTimer(self, timeout=self._tick)

    def start(self, phase="focus"):
        minutes = self.cfg["focus_min"] if phase == "focus" else self.cfg["break_min"]
        self.phase = phase
        self.ends_at = time.time() + minutes * 60
        self.timer.start(1000)
        self.changed.emit()

    def stop(self):
        self.phase = None
        self.timer.stop()
        self.changed.emit()

    def toggle(self):
        self.stop() if self.phase else self.start("focus")

    @property
    def remaining(self):
        return max(0, int(self.ends_at - time.time())) if self.phase else 0

    def label(self):
        if not self.phase:
            return ""
        m, s = divmod(self.remaining, 60)
        return f"{m}:{s:02d}"

    def _tick(self):
        if self.phase and time.time() >= self.ends_at:
            ended = self.phase
            self.phase = None
            self.timer.stop()
            self.phase_end.emit(ended)
        self.changed.emit()
