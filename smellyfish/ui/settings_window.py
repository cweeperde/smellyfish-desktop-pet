"""Settings window and the shared option schema (also used by the tray menu)."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QGridLayout, QGroupBox, QHBoxLayout,
                               QKeySequenceEdit, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSlider, QSpinBox,
                               QVBoxLayout, QWidget)

from smellyfish import __version__
from smellyfish.system import hotkeys
from smellyfish.ui import theme

SIZES = [("Tiny", 2), ("Small", 3), ("Medium", 4), ("Large", 5), ("Huge", 6), ("Giant", 8), ("Colossal", 10)]
OPACITIES = [(f"{int(o * 100)} %", o) for o in (1.0, 0.85, 0.7, 0.5, 0.3)]
SLEEPS = [("1 minute", 1), ("3 minutes", 3), ("10 minutes", 10), ("30 minutes", 30), ("Never", 0)]
VOLUMES = [("Quiet", 25), ("Normal", 60), ("Loud", 100)]
FOCUS = [("15 min", 15), ("25 min", 25), ("45 min", 45), ("60 min", 60)]
BREAKS = [("3 min", 3), ("5 min", 5), ("10 min", 10), ("15 min", 15)]
SKIN_CHOICES = [("Lavender", "lavender"), ("Pink", "pink"), ("Blue", "blue"), ("Mint", "mint"),
                ("Peach", "peach"), ("Custom", "custom")]

def monitor_choices():
    from PySide6.QtGui import QGuiApplication
    out = [("Main screen", "primary")]
    for i, sc in enumerate(QGuiApplication.screens(), 1):
        g = sc.geometry()
        out.append((f"Screen {i} ({g.width()}x{g.height()})", f"{g.x()},{g.y()}"))
    return out + [("All screens", "all")]


SCHEMA = [
    ("Appearance", [
        ("scale", "Size", SIZES),
        ("opacity", "Opacity", OPACITIES),
        ("show_house", "Show the house (lamp, bed, plant)", None),
        ("skin", "Color", SKIN_CHOICES),
        ("seasonal", "Seasonal outfits", None),
        ("weather", "Weather outfits (umbrella, sunglasses, scarf)", None),
        ("temp_unit", "Temperature", [("°C", "C"), ("°F", "F")]),
    ]),
    ("Movement", [
        ("gravity", "Gravity", None),
        ("sit_on_windows", "Sit on windows", None),
        ("sit_on_icons", "Sit on desktop icons (only ones with free space above)", None),
        ("window_hop", "Jump between windows", None),
        ("wander", "Hop around by itself", None),
        ("trips_home", "Go home now and then", None),
        ("auto_water", "Water the plant now and then", None),
        ("eyes_follow", "Eyes follow the cursor", None),
        ("monitor", "Stay on", monitor_choices),
    ]),
    ("Claude Code & Codex", [
        ("ask_in_bubble", "Answer questions in bubble", None),
        ("perm_in_bubble", "Answer permissions in bubble", None),
        ("done_bubble", "Show summary when done", None),
        ("hooks", "Claude Code hooks (all projects)", None),
        ("codex_hooks", "Codex hooks (~/.codex/hooks.json)", None),
        ("task_timer", "Show how long a task is running", None),
        ("usage_warn", "Warn about usage limits", [("Off", 0), ("at 70 %", 70), ("at 80 %", 80), ("at 90 %", 90)]),
        ("usage_critical", "Critical warning at 95 % of a limit", None),
        ("claude_statusline", "Claude usage via status line (~/.claude)", None),
    ]),
    ("Reactions", [
        ("fidgets", "Little idle actions", None),
        ("react_cpu", "Sweat when the CPU is busy", None),
        ("react_battery", "Battery warnings", None),
        ("react_network", "Notice when offline", None),
        ("react_greet", "Say hi when you come back", None),
        ("todo_greet", "Mention open to-dos when you come back", None),
        ("react_lock", "React to screen lock", None),
        ("react_night", "Yawn late at night", None),
        ("react_hover", "Blush when you hover over it", None),
        ("react_clipboard", "React to copying and screenshots", None),
        ("trash_watch", "Remind me of a full recycle bin", None),
        ("clicker", "Count my clicks and key presses (only the number)", None),
        ("break_nudge", "Suggest a short break after 75 minutes", None),
    ]),
    ("Music, games & Discord", [
        ("react_music", "Dance to music (Spotify / any audio)", None),
        ("beat_sync", "Dance on the beat (listens to audio output)", None),
        ("game_mode", "Hide during fullscreen apps and games", None),
        ("discord", "Headset when in a Discord call", None),
        ("discord_messages", "Show Discord messages (needs setup)", None),
    ]),
    ("Sound & focus", [
        ("mute_all", "Mute all sounds (overrides everything below)", None),
        ("sound_done", "Notification sound (tasks done, questions, alarms)", None),
        ("notify_volume", "Notification volume", VOLUMES),
        ("sfx", "Fun sounds (off in do not disturb and sleep)", None),
        ("talk_blips", "Babble sounds when it talks", None),
        ("volume", "Fun sound volume", VOLUMES),
        ("focus_min", "Focus time", FOCUS),
        ("break_min", "Break time", BREAKS),
    ]),
    ("General", [
        ("sleep_after_min", "Fall asleep after", SLEEPS),
        ("dnd", "Do not disturb (lamp off)", None),
        ("mini_side", "Mini mode side", [("Right", "right"), ("Left", "left")]),
        ("on_top", "Always on top", None),
        ("autostart", "Start with Windows", None),
        ("auto_update", "Install updates automatically", None),
    ]),
]

class SettingsWindow(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.Window)
        self.app = app
        self.setWindowTitle("Smellyfish Settings")
        theme.apply(self, app)
        self.resize(1180, 860)
        self.widgets = {}
        self.pending = {}
        self._loading = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 10)
        outer.addWidget(theme.banner("Settings", f"Smellyfish {__version__}"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        root = QVBoxLayout(inner)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        grid = QGridLayout()
        self.sliders = {}
        for i, (title, items) in enumerate(SCHEMA):
            box = QGroupBox(title.replace("&", "&&"))
            lay = QVBoxLayout(box)
            for key, label, choices in items:
                if key in ("volume", "notify_volume"):
                    row = QHBoxLayout()
                    row.addWidget(QLabel(label))
                    slider = QSlider(Qt.Horizontal)
                    slider.setRange(0, 100)
                    value_label = QLabel("")
                    slider.valueChanged.connect(lambda v, lb=value_label, k=key: (lb.setText(f"{v} %"),
                                                                                  self.changed(k, v)))
                    test = QPushButton("Test")
                    test.setObjectName("secondary")
                    test.clicked.connect(lambda _c=False, k=key, sl=slider: app.test_sound(k, sl.value()))
                    row.addWidget(slider, 1)
                    row.addWidget(value_label)
                    row.addWidget(test)
                    lay.addLayout(row)
                    self.sliders[key] = (slider, value_label)
                    continue
                if callable(choices):
                    choices = choices()
                if choices:
                    row = QHBoxLayout()
                    row.addWidget(QLabel(label))
                    combo = QComboBox()
                    for text, value in choices:
                        combo.addItem(text, value)
                    combo.currentIndexChanged.connect(lambda _i, k=key, c=combo: self.changed(k, c.currentData()))
                    row.addWidget(combo, 1)
                    if key == "skin":
                        pick = QPushButton("Pick...")
                        pick.setObjectName("secondary")
                        pick.clicked.connect(self.pick_color)
                        row.addWidget(pick)
                    if key == "scale":
                        self.custom = QSpinBox()
                        self.custom.setRange(1, 16)
                        self.custom.setPrefix("Custom: ")
                        self.custom.valueChanged.connect(lambda v: self.changed("scale", v))
                        row.addWidget(self.custom)
                    lay.addLayout(row)
                    self.widgets[key] = combo
                else:
                    cb = QCheckBox(label)
                    cb.toggled.connect(lambda on, k=key: self.changed(k, on))
                    lay.addWidget(cb)
                    self.widgets[key] = cb
            lay.addStretch(1)
            grid.addWidget(box, i // 2, i % 2)

        keys = QGroupBox("Hotkeys (global)")
        kl = QVBoxLayout(keys)
        self.key_edits = {}
        for action, label in hotkeys.ACTIONS:
            row = QHBoxLayout()
            lab = QLabel(label)
            lab.setMinimumWidth(170)
            row.addWidget(lab)
            edit = QKeySequenceEdit()
            edit.setMaximumSequenceLength(1)
            edit.editingFinished.connect(self.keys_changed)
            row.addWidget(edit, 1)
            clear = QPushButton("x")
            clear.setObjectName("secondary")
            clear.setFixedWidth(34)
            clear.setToolTip("No hotkey")
            clear.clicked.connect(lambda _=False, e=edit: (e.clear(), self.keys_changed()))
            row.addWidget(clear)
            reset = QPushButton("↺")
            reset.setObjectName("secondary")
            reset.setFixedWidth(34)
            reset.setToolTip(f"Reset to {hotkeys.DEFAULTS[action]}")
            reset.clicked.connect(lambda _=False, e=edit, a=action: (
                e.setKeySequence(QKeySequence(hotkeys.DEFAULTS[a])), self.keys_changed()))
            row.addWidget(reset)
            kl.addLayout(row)
            self.key_edits[action] = edit
        bottom = QHBoxLayout()
        self.key_status = QLabel("")
        self.key_status.setObjectName("hint")
        self.key_status.setWordWrap(True)
        bottom.addWidget(self.key_status, 1)
        reset_all = QPushButton("Reset all")
        reset_all.setObjectName("secondary")
        reset_all.clicked.connect(self.reset_keys)
        bottom.addWidget(reset_all)
        kl.addLayout(bottom)
        grid.addWidget(keys, len(SCHEMA) // 2, len(SCHEMA) % 2)
        root.addLayout(grid)

        weather = QGroupBox("Weather")
        wl = QHBoxLayout(weather)
        wl.addWidget(QLabel("Place"))
        self.place = QLineEdit()
        self.place.setPlaceholderText("e.g. Berlin")
        self.place.textEdited.connect(lambda t: self.changed("weather_place", t.strip()))
        wl.addWidget(self.place, 1)
        self.weather_status = QLabel(app.weather.text)
        self.weather_status.setObjectName("hint")
        wl.addWidget(self.weather_status, 1)
        root.addWidget(weather)

        tools = QHBoxLayout()
        for text, fn in (("Animation tester...", app.open_gallery), ("Missed...", app.open_history),
                         ("Achievements...", app.open_achievements), ("Discord setup...", app.open_discord_setup),
                         ("Check for updates", lambda: app.updater.check(manual=True))):
            b = QPushButton(text)
            b.setObjectName("secondary")
            b.clicked.connect(fn)
            tools.addWidget(b)
        root.addLayout(tools)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(12, 0, 12, 0)
        for text, fn in (("Set home here", app.set_home_here), ("Go home", app.go_home)):
            b = QPushButton(text)
            b.setObjectName("secondary")
            b.clicked.connect(fn)
            buttons.addWidget(b)
        self.save_status = QLabel("")
        self.save_status.setObjectName("hint")
        buttons.addWidget(self.save_status, 1, Qt.AlignRight)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.cancel)
        buttons.addWidget(cancel)
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save)
        buttons.addWidget(self.save_button)
        outer.addLayout(buttons)
        self.refresh()

    def refresh(self):
        if self.pending and self.isVisible():
            return
        self._loading = True
        self.pending = {}
        self.update_status()
        for key, (slider, value_label) in self.sliders.items():
            slider.setValue(int(self.app.get_setting(key) or 0))
            value_label.setText(f"{slider.value()} %")
        self.place.setText(self.app.get_setting("weather_place") or "")
        for key, w in self.widgets.items():
            value = self.app.get_setting(key)
            if isinstance(w, QComboBox):
                w.setCurrentIndex(w.findData(value))
            else:
                w.setChecked(bool(value))
        self.custom.setValue(int(self.app.get_setting("scale")))
        keys = dict(hotkeys.DEFAULTS, **(self.app.get_setting("hotkeys") or {}))
        for action, edit in self.key_edits.items():
            edit.setKeySequence(QKeySequence(keys.get(action, "")))
        failed = self.app.hotkey_conflicts
        self.key_status.setText("Taken by another app: " + ", ".join(failed) if failed else
                                "Click a field and press the new key combination.")
        self._loading = False

    def pick_color(self):
        color = QColorDialog.getColor(QColor(self.app.get_setting("skin_color") or "#c492ec"), self, "Jellyfish color")
        if color.isValid():
            self.changed("skin_color", color.name())
            self._loading = True
            self.widgets["skin"].setCurrentIndex(self.widgets["skin"].findData("custom"))
            self._loading = False
            self.changed("skin", "custom")

    def set_weather_status(self, text):
        self.weather_status.setText(text)

    def reset_keys(self):
        self._loading = True
        for action, edit in self.key_edits.items():
            edit.setKeySequence(QKeySequence(hotkeys.DEFAULTS[action]))
        self._loading = False
        self.keys_changed()

    def keys_changed(self):
        if self._loading:
            return
        mapping = {a: e.keySequence().toString(QKeySequence.PortableText) for a, e in self.key_edits.items()}
        self.changed("hotkeys", mapping)

    def changed(self, key, value):
        if self._loading or value is None:
            return
        if value == self.app.get_setting(key):
            self.pending.pop(key, None)
        else:
            self.pending[key] = value
        self.update_status()

    def update_status(self):
        n = len(self.pending)
        self.save_status.setText(f"{n} unsaved change{'s' if n != 1 else ''}" if n else "")
        self.save_button.setEnabled(bool(n))
        self.setWindowTitle("Smellyfish Settings" + (" *" if n else ""))

    def save(self):
        changes, self.pending = dict(self.pending), {}
        for key in sorted(changes, key=lambda k: k != "skin_color"):
            self.app.apply_setting(key, changes[key])
        problems = self.app.verify_saved([k for k in changes if k not in ("hooks", "codex_hooks", "autostart",
                                                                           "claude_statusline")])
        self.refresh()
        self.save_status.setText("Could not save: " + problems if problems else "Saved")

    def cancel(self):
        self.pending = {}
        self.close()

    def closeEvent(self, e):
        if self.pending:
            box = QMessageBox(QMessageBox.Question, "Unsaved changes", "Save your changes before closing?",
                              QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, self)
            theme.apply(box, self.app)
            answer = box.exec()
            if answer == QMessageBox.Cancel:
                return e.ignore()
            if answer == QMessageBox.Save:
                self.save()
            self.pending = {}
        e.accept()
