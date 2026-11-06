"""Settings window and the shared option schema (also used by the tray menu)."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap
from PySide6.QtCore import QSize
from PIL import Image
from smellyfish.art import sprite
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout,
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

def skin_icon(pal):
    """A little jellyfish in the given skin colours, for the colour list."""
    img = sprite.render(sprite.Pose(eyes="happy"), 1, pal=pal)
    img = img.crop((sprite.BX, sprite.BY, sprite.BX + 16, sprite.BY + 13)).resize((48, 39), Image.NEAREST)
    q = QImage(img.tobytes("raw", "RGBA"), img.width, img.height, QImage.Format_RGBA8888).copy()
    return QIcon(QPixmap.fromImage(q))


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
        ("dark_ui", "Dark mode", None),
        ("seasonal", "Seasonal outfits", None),
        ("weather", "Weather outfits", None),
        ("weather_auto", "Weather: use my current location", None),
        ("weather_ip", "Weather: use my IP if location is off", None),
        ("temp_unit", "Temperature", [("°C", "C"), ("°F", "F")]),
    ]),
    ("Movement", [
        ("gravity", "Gravity", None),
        ("sit_on_windows", "Sit on windows", None),
        ("sit_on_icons", "Sit on desktop icons and files", None),
        ("window_hop", "Jump between windows", None),
        ("ceiling_hang", "Hang upside down under windows", None),
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
        ("codex_hooks", "Codex hooks", None),
        ("task_timer", "Show how long a task is running", None),
        ("usage_warn", "Warn about usage limits", [("Off", 0), ("at 70 %", 70), ("at 80 %", 80), ("at 90 %", 90)]),
        ("usage_critical", "Critical warning at 95 % of a limit", None),
        ("claude_statusline", "Claude usage via status line", None),
    ]),
    ("Reactions", [
        ("fidgets", "Little idle actions", None),
        ("react_cpu", "Sweat when the CPU is busy", None),
        ("react_battery", "Battery warnings", None),
        ("react_network", "Notice when offline", None),
        ("react_greet", "Say hi when you come back", None),
        ("todo_greet", "Mention open to-dos on return", None),
        ("react_lock", "React to screen lock", None),
        ("react_night", "Yawn late at night", None),
        ("react_hover", "Blush when you hover over it", None),
        ("react_clipboard", "React to copying and screenshots", None),
        ("trash_watch", "Remind me of a full recycle bin", None),
        ("clicker", "Count clicks and key presses", None),
        ("break_nudge", "Suggest a break after 75 minutes", None),
    ]),
    ("Music, games & Discord", [
        ("react_music", "Dance to music", None),
        ("beat_sync", "Dance on the beat", None),
        ("game_mode", "Hide in fullscreen apps and games", None),
        ("discord", "Headset when in a Discord call", None),
        ("discord_messages", "Show Discord messages", None),
    ]),
    ("Sound & focus", [
        ("mute_all", "Mute all sounds", None),
        ("sound_done", "Notification sound", None),
        ("notify_volume", "Notification volume", VOLUMES),
        ("sfx", "Fun sounds", None),
        ("talk_blips", "Babble sounds when it talks", None),
        ("volume", "Fun sound volume", VOLUMES),
        ("focus_min", "Focus time", FOCUS),
        ("break_min", "Break time", BREAKS),
    ]),
    ("Local AI chat (Ollama / llama.cpp)", [
        ("llm_enabled", "Chat with a local model (stays on this PC)", None),
        ("llm_backend", "Server", [("Ollama", "ollama"), ("llama.cpp server", "llamacpp")]),
        ("llm_reply", "Show answers in", [("Speech bubble", "bubble"), ("Chat window", "window")]),
        ("llm_autostart", "Start the model server in the background", None),
        ("llm_autoload", "Load the model when the chat opens", None),
        ("llm_idle_min", "Unload the model after", [("2 minutes", 2), ("5 minutes", 5), ("15 minutes", 15),
                                                      ("30 minutes", 30), ("60 minutes", 60)]),
        ("llm_unload_on_quit", "Unload the model when Smellyfish quits", None),
    ]),
    ("Multiplayer (LAN lobby)", [
        ("lan_visits", "Let lobby friends visit me", None),
        ("lan_letters", "Accept letters from a lobby", None),
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
        slot = 0
        self.llm_group = None
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
                        combo.setIconSize(QSize(48, 39))
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
            if title.startswith("Local AI"):
                self.llm_group = box
            else:
                grid.addWidget(box, slot // 2, slot % 2)
                slot += 1

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
        grid.addWidget(keys, slot // 2, slot % 2)
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

        ai = QGroupBox("Local model")
        al = QVBoxLayout(ai)
        row = QHBoxLayout()
        row.addWidget(QLabel("Address"))
        self.llm_url = QLineEdit()
        self.llm_url.setPlaceholderText("default: this PC")
        self.llm_url.textEdited.connect(lambda t: self.changed("llm_url", t.strip()))
        row.addWidget(self.llm_url, 1)
        row.addWidget(QLabel("Model"))
        self.llm_model = QComboBox()
        self.llm_model.setEditable(True)
        self.llm_model.setMinimumWidth(220)
        self.llm_model.currentTextChanged.connect(lambda t: self.changed("llm_model", t.strip()))
        row.addWidget(self.llm_model, 1)
        find = QPushButton("Find models")
        find.setObjectName("secondary")
        find.clicked.connect(self.find_models)
        row.addWidget(find)
        al.addLayout(row)
        self.llm_status = QLabel("Only this PC or private network addresses are used. Nothing leaves your network.")
        self.llm_status.setObjectName("hint")
        al.addWidget(self.llm_status)
        row = QHBoxLayout()
        row.addWidget(QLabel("Program"))
        self.llm_binary = QLineEdit()
        self.llm_binary.setPlaceholderText("ollama.exe / llama-server.exe (empty = find it automatically)")
        self.llm_binary.textEdited.connect(lambda t: self.changed("llm_binary", t.strip()))
        row.addWidget(self.llm_binary, 1)
        al.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("Models folder"))
        self.llm_folder = QLineEdit()
        self.llm_folder.setPlaceholderText("llama.cpp only: folder with your .gguf files")
        self.llm_folder.textEdited.connect(lambda t: self.changed("llm_models_dir", t.strip()))
        row.addWidget(self.llm_folder, 1)
        al.addLayout(row)
        al.addWidget(QLabel("Extra instructions for its personality (optional)"))
        self.llm_prompt = QLineEdit()
        self.llm_prompt.setMaxLength(600)
        self.llm_prompt.setPlaceholderText("e.g. call me captain, reply in German")
        self.llm_prompt.textEdited.connect(lambda t: self.changed("llm_prompt", t.strip()))
        al.addWidget(self.llm_prompt)
        self.adv_button = QPushButton("Advanced model settings  [+]")
        self.adv_button.setObjectName("secondary")
        self.adv_button.setCheckable(True)
        self.adv_button.toggled.connect(self.toggle_advanced)
        al.addWidget(self.adv_button)
        self.adv = QWidget()
        ag = QGridLayout(self.adv)
        ag.setContentsMargins(0, 0, 0, 0)
        self.llm_adv = {}
        rows = [
            ("llm_max_tokens", "Longest answer (tokens)", "spin", (32, 4000, 10)),
            ("llm_think", "Thinking", "combo", [("Off (fast)", "off"), ("Model default", "auto"), ("On (slow)", "on")]),
            ("llm_ctx", "Context size", "combo", [("Model default", 0), ("2048", 2048), ("4096", 4096),
                                                  ("8192", 8192), ("16384", 16384), ("32768", 32768)]),
            ("llm_temp", "Creativity", "dspin", (0.0, 1.5, 0.1)),
            ("llm_history", "Remembered messages", "spin", (0, 20, 1)),
            ("llm_persona", "Cute jellyfish personality", "check", None),
        ]
        for r, (key, label, kind, arg) in enumerate(rows):
            if kind == "check":
                w = QCheckBox(label)
                w.toggled.connect(lambda on, k=key: self.changed(k, on))
                ag.addWidget(w, r, 0, 1, 2)
            else:
                ag.addWidget(QLabel(label), r, 0)
                if kind == "spin":
                    w = QSpinBox()
                    w.setRange(arg[0], arg[1])
                    w.setSingleStep(arg[2])
                    w.valueChanged.connect(lambda v, k=key: self.changed(k, v))
                elif kind == "dspin":
                    w = QDoubleSpinBox()
                    w.setRange(arg[0], arg[1])
                    w.setSingleStep(arg[2])
                    w.setDecimals(1)
                    w.valueChanged.connect(lambda v, k=key: self.changed(k, round(v, 1)))
                else:
                    w = QComboBox()
                    for text, value in arg:
                        w.addItem(text, value)
                    w.currentIndexChanged.connect(lambda _i, k=key, c=w: self.changed(k, c.currentData()))
                ag.addWidget(w, r, 1)
            self.llm_adv[key] = w
        unload = QPushButton("Unload model now")
        unload.setObjectName("secondary")
        unload.clicked.connect(app.unload_llm)
        ag.addWidget(unload, len(rows), 0, 1, 2)
        ag.setColumnStretch(1, 1)
        self.adv.hide()
        al.addWidget(self.adv)
        self.llm_panel = QWidget()
        pl = QVBoxLayout(self.llm_panel)
        pl.setContentsMargins(0, 0, 0, 0)
        if self.llm_group is not None:
            pl.addWidget(self.llm_group)
        pl.addWidget(ai)
        self.llm_toggle = QPushButton("Local AI chat (Ollama / llama.cpp)  [+]")
        self.llm_toggle.setObjectName("secondary")
        self.llm_toggle.setCheckable(True)
        self.llm_toggle.toggled.connect(self.toggle_llm)
        root.addWidget(self.llm_toggle)
        root.addWidget(self.llm_panel)
        self.llm_panel.hide()
        app.llm.models_ready.connect(self.on_models)

        tools = QHBoxLayout()
        for text, fn in (("Lobby (LAN)...", app.open_lobby), ("Animation tester...", app.open_gallery), ("Missed...", app.open_history),
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
        self.llm_url.setText(self.app.get_setting("llm_url") or "")
        self.llm_prompt.setText(self.app.get_setting("llm_prompt") or "")
        self.llm_binary.setText(self.app.get_setting("llm_binary") or "")
        for key, w in self.llm_adv.items():
            value = self.app.get_setting(key)
            if isinstance(w, QCheckBox):
                w.setChecked(value is not False)
            elif isinstance(w, QComboBox):
                w.setCurrentIndex(max(0, w.findData(value)))
            elif isinstance(w, QDoubleSpinBox):
                w.setValue(float(value or 0))
            else:
                w.setValue(int(value or 0))
        self.llm_folder.setText(self.app.get_setting("llm_models_dir") or "")
        self.llm_model.setCurrentText(self.app.get_setting("llm_model") or "")
        for key, w in self.widgets.items():
            value = self.app.get_setting(key)
            if isinstance(w, QComboBox):
                w.setCurrentIndex(w.findData(value))
            else:
                w.setChecked(bool(value))
        self.custom.setValue(int(self.app.get_setting("scale")))
        self.refresh_skin_icons()
        keys = dict(hotkeys.DEFAULTS, **(self.app.get_setting("hotkeys") or {}))
        for action, edit in self.key_edits.items():
            edit.setKeySequence(QKeySequence(keys.get(action, "")))
        failed = self.app.hotkey_conflicts
        self.key_status.setText("Taken by another app: " + ", ".join(failed) if failed else
                                "Click a field and press the new key combination.")
        self._loading = False

    def refresh_skin_icons(self):
        combo = self.widgets.get("skin")
        if combo is None:
            return
        c = (self.pending.get("skin_color") or self.app.get_setting("skin_color") or "#c492ec").lstrip("#")
        custom = sprite.skin_from_color(tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)))
        for i in range(combo.count()):
            value = combo.itemData(i)
            pal = custom if value == "custom" else sprite.SKINS.get(value)
            combo.setItemIcon(i, skin_icon(pal))

    def pick_color(self):
        color = QColorDialog.getColor(QColor(self.app.get_setting("skin_color") or "#c492ec"), self, "Jellyfish color")
        if color.isValid():
            self.changed("skin_color", color.name())
            self.refresh_skin_icons()
            self._loading = True
            self.widgets["skin"].setCurrentIndex(self.widgets["skin"].findData("custom"))
            self._loading = False
            self.changed("skin", "custom")

    def toggle_llm(self, on):
        self.llm_panel.setVisible(on)
        self.llm_toggle.setText("Local AI chat (Ollama / llama.cpp)  [-]" if on else
                                "Local AI chat (Ollama / llama.cpp)  [+]")

    def toggle_advanced(self, on):
        self.adv.setVisible(on)
        self.adv_button.setText("Advanced model settings  [-]" if on else "Advanced model settings  [+]")

    def find_models(self):
        for key in ("llm_backend", "llm_url", "llm_binary", "llm_models_dir", "llm_autostart"):
            self.app.cfg.set(key, self.pending.get(key, self.app.get_setting(key)))
        self.llm_status.setText("Looking...")
        self.app.llm.refresh_models()

    def on_models(self, models, error):
        if error:
            self.llm_status.setText(f"Could not list models: {error}")
            return
        current = self.llm_model.currentText()
        self._loading = True
        self.llm_model.clear()
        self.llm_model.addItems(models)
        self.llm_model.setCurrentText(current or (models[0] if models else ""))
        self._loading = False
        if self.llm_model.currentText() != (self.app.get_setting("llm_model") or ""):
            self.changed("llm_model", self.llm_model.currentText())
        self.llm_status.setText(f"{len(models)} model{'s' if len(models) != 1 else ''} found")

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
