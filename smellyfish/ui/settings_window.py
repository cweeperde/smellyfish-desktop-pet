"""Settings window: pages in a sidebar with search; every change applies at once."""

import sys

from PIL import Image
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from smellyfish import __version__
from smellyfish.art import sprite
from smellyfish.system import hotkeys
from smellyfish.ui import theme

SIZES = [("Tiny", 2), ("Small", 3), ("Medium", 4), ("Large", 5), ("Huge", 6), ("Giant", 8), ("Colossal", 10)]
OPACITIES = [(f"{int(o * 100)} %", o) for o in (1.0, 0.85, 0.7, 0.5, 0.3)]
SLEEPS = [("1 minute", 1), ("3 minutes", 3), ("10 minutes", 10), ("30 minutes", 30), ("Never", 0)]
VOLUMES = [("Quiet", 25), ("Normal", 60), ("Loud", 100)]
FOCUS = [("15 min", 15), ("25 min", 25), ("45 min", 45), ("60 min", 60)]
BREAKS = [("3 min", 3), ("5 min", 5), ("10 min", 10), ("15 min", 15)]
SKIN_CHOICES = [
    ("Lavender", "lavender"),
    ("Pink", "pink"),
    ("Blue", "blue"),
    ("Mint", "mint"),
    ("Peach", "peach"),
    ("Night", "night"),
    ("Lemon", "lemon"),
    ("Snow", "snow"),
    ("Custom", "custom"),
]
HATS = [
    ("By season", "auto"),
    ("None", "none"),
    ("Santa hat", "santa"),
    ("Witch hat", "witch"),
    ("Party hat", "party"),
    ("Hearts", "valentine"),
    ("Bunny ears", "bunny"),
    ("Straw hat", "straw"),
    ("Pumpkin", "pumpkin"),
]
ACCESSORIES = [
    ("By weather", "auto"),
    ("None", "none"),
    ("Scarf", "scarf"),
    ("Sunglasses", "shades"),
    ("Umbrella", "umbrella"),
]


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
    (
        "Appearance",
        [
            ("scale", "Size", SIZES),
            ("opacity", "Opacity", OPACITIES),
            ("show_house", "Show the house (lamp, bed, plant)", None),
            ("skin", "Color", SKIN_CHOICES),
            ("dark_ui", "Dark mode", None),
            ("seasonal", "Seasonal outfits", None),
            ("hat", "Hat", HATS),
            ("accessory", "Accessory", ACCESSORIES),
            ("weather", "Weather outfits", None),
            ("weather_auto", "Weather: use my current location", None),
            ("weather_ip", "Weather: use my IP if location is off", None),
            ("temp_unit", "Temperature", [("°C", "C"), ("°F", "F")]),
        ],
    ),
    (
        "Movement",
        [
            ("gravity", "Gravity", None),
            ("sit_on_windows", "Sit on windows", None),
            ("sit_on_icons", "Sit on desktop icons and files", None),
            ("window_hop", "Jump between windows", None),
            ("ceiling_hang", "Hang from a tentacle under windows", None),
            ("wander", "Hop around by itself", None),
            ("trips_home", "Go home now and then", None),
            ("auto_water", "Water the plant now and then", None),
            ("eyes_follow", "Eyes follow the cursor", None),
            ("tentacle_sim", "Tentacles trail behind when it moves", None),
            ("monitor", "Stay on", monitor_choices),
        ],
    ),
    (
        "Coding agents",
        [
            ("ask_in_bubble", "Answer questions in bubble", None),
            ("perm_in_bubble", "Answer permissions in bubble", None),
            ("done_bubble", "Show summary when done", None),
            ("hooks", "Claude Code hooks (all projects)", None),
            ("codex_hooks", "Codex hooks", None),
            ("gemini_hooks", "Gemini CLI hooks", None),
            ("cursor_hooks", "Cursor hooks", None),
            ("copilot_hooks", "GitHub Copilot hooks", None),
            ("antigravity_hooks", "Antigravity CLI hooks", None),
            ("deepseek_hooks", "DeepSeek-TUI hooks (community)", None),
            ("task_timer", "Show how long a task is running", None),
            ("usage_warn", "Warn about usage limits", [("Off", 0), ("at 70 %", 70), ("at 80 %", 80), ("at 90 %", 90)]),
            ("usage_critical", "Critical warning at 95 % of a limit", None),
            ("claude_statusline", "Claude usage via status line", None),
        ],
    ),
    (
        "Reactions",
        [
            ("fidgets", "Idle actions", None),
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
        ],
    ),
    (
        "Music, games & Discord",
        [
            ("react_music", "Dance to music", None),
            ("media", "Show what is playing (Spotify, browser, other players)", None),
            (
                "media_note",
                "Music note in the badge",
                [("While playing", "playing"), ("Always", "always"), ("Off", "off")],
            ),
            ("beat_sync", "Dance on the beat", None),
            ("game_mode", "Hide in fullscreen apps and games", None),
            ("discord", "Headset when in a Discord call", None),
            ("discord_messages", "Show Discord messages", None),
            ("discord_presence", 'Show "Playing Smellyfish" on Discord', None),
        ],
    ),
    (
        "Sound & focus",
        [
            ("mute_all", "Mute all sounds", None),
            ("sound_done", "Notification sound", None),
            ("notify_volume", "Notification volume", VOLUMES),
            ("sfx", "Fun sounds", None),
            ("talk_blips", "Babble sounds when it talks", None),
            ("volume", "Fun sound volume", VOLUMES),
            ("focus_min", "Focus time", FOCUS),
            ("break_min", "Break time", BREAKS),
        ],
    ),
    (
        "Local AI chat (Ollama / llama.cpp)",
        [
            ("llm_enabled", "Chat with a local model (stays on this PC)", None),
            ("llm_backend", "Server", [("Ollama", "ollama"), ("llama.cpp server", "llamacpp")]),
            ("llm_reply", "Show answers in", [("Speech bubble", "bubble"), ("Chat window", "window")]),
            ("llm_autostart", "Start the model server in the background", None),
            ("llm_autoload", "Load the model when the chat opens", None),
            (
                "llm_idle_min",
                "Unload the model after",
                [("2 minutes", 2), ("5 minutes", 5), ("15 minutes", 15), ("30 minutes", 30), ("60 minutes", 60)],
            ),
            ("llm_unload_on_quit", "Unload the model when Smellyfish quits", None),
        ],
    ),
    (
        "Multiplayer (LAN lobby)",
        [
            ("lan_visits", "Let lobby friends visit me", None),
            ("lan_letters", "Accept letters from a lobby", None),
        ],
    ),
    (
        "General",
        [
            ("sleep_after_min", "Fall asleep after", SLEEPS),
            ("dnd", "Do not disturb (lamp off)", None),
            ("mini_side", "Mini mode side", [("Right", "right"), ("Left", "left")]),
            ("on_top", "Always on top", None),
            ("autostart", "Start with Windows", None),
            ("shell_menu", "Explorer right-click menu", None),
            ("auto_update", "Install updates automatically", None),
        ],
    ),
]

if sys.platform == "darwin":
    MAC_LABELS = {
        "autostart": "Start when I log in",
        "shell_menu": "Finder right-click actions",
        "trash_watch": "Remind me of a full Trash",
    }
    SCHEMA = [(title, [(k, MAC_LABELS.get(k, label), c) for k, label, c in items]) for title, items in SCHEMA]

SCHEMA_BY_KEY = {key: (label, choices) for _title, items in SCHEMA for key, label, choices in items}

# page name -> [(section title, section hint, [keys or @blocks])]
PAGES = [
    (
        "General",
        [
            ("Behavior", "", ["sleep_after_min", "dnd", "mini_side", "on_top"]),
            ("Where it lives", "", ["monitor", "@home"]),
            ("Windows", "", ["autostart", "shell_menu", "auto_update"]),
        ],
    ),
    (
        "Look",
        [
            ("Size and color", "", ["scale", "opacity", "skin", "dark_ui"]),
            ("Outfits and house", "", ["hat", "accessory", "seasonal", "weather", "show_house"]),
        ],
    ),
    (
        "Movement & Reactions",
        [
            (
                "Movement",
                "",
                [
                    "gravity",
                    "sit_on_windows",
                    "sit_on_icons",
                    "window_hop",
                    "ceiling_hang",
                    "wander",
                    "trips_home",
                    "auto_water",
                    "eyes_follow",
                    "tentacle_sim",
                ],
            ),
            (
                "Reactions",
                "",
                [
                    "fidgets",
                    "react_cpu",
                    "react_battery",
                    "react_network",
                    "react_greet",
                    "todo_greet",
                    "react_lock",
                    "react_night",
                    "react_hover",
                    "react_clipboard",
                    "trash_watch",
                    "break_nudge",
                ],
            ),
            ("Counting", "", ["clicker"]),
        ],
    ),
    (
        "Sound",
        [
            ("Sounds", "", ["mute_all", "sound_done", "notify_volume", "sfx", "volume", "talk_blips"]),
            ("Focus timer", "", ["focus_min", "break_min"]),
        ],
    ),
    (
        "Agents & Hooks",
        [
            ("In the bubble", "", ["ask_in_bubble", "perm_in_bubble", "done_bubble", "task_timer"]),
            (
                "Hooks",
                "Hooks let a coding agent tell Smellyfish what it is doing. Each switch adds or removes only "
                "Smellyfish's own entries in that tool's settings file.",
                [
                    "hooks",
                    "codex_hooks",
                    "gemini_hooks",
                    "cursor_hooks",
                    "copilot_hooks",
                    "antigravity_hooks",
                    "deepseek_hooks",
                ],
            ),
            ("Usage limits", "", ["usage_warn", "usage_critical", "claude_statusline"]),
        ],
    ),
    (
        "Integrations",
        [
            ("Music", "", ["react_music", "media", "media_note", "beat_sync"]),
            ("Games", "", ["game_mode"]),
            ("Discord", "", ["discord", "discord_messages", "discord_presence", "@discord_setup"]),
            ("Weather", "", ["@weather", "weather_auto", "weather_ip", "temp_unit"]),
            ("Lobby (LAN)", "", ["lan_visits", "lan_letters", "@lobby"]),
        ],
    ),
    (
        "Local AI",
        [
            (
                "Chat",
                "",
                [
                    "llm_enabled",
                    "llm_backend",
                    "llm_reply",
                    "llm_autostart",
                    "llm_autoload",
                    "llm_idle_min",
                    "llm_unload_on_quit",
                ],
            ),
            (
                "Model",
                "Only this PC or private network addresses are used. Nothing leaves your network.",
                ["@llm_connection", "@llm_prompt", "@llm_advanced"],
            ),
        ],
    ),
    (
        "Hotkeys",
        [
            ("Global hotkeys", "Click a field and press the new key combination.", ["@hotkeys"]),
        ],
    ),
    (
        "Tools",
        [
            ("Tools", "", ["@tools"]),
        ],
    ),
    (
        "About",
        [
            ("Smellyfish", "", ["@about"]),
        ],
    ),
]

HINTS = {
    "sit_on_icons": "Rests on desktop icons and files.",
    "window_hop": "Hops from one window top to another.",
    "ceiling_hang": "Now and then hangs under the lower edge of a window.",
    "tentacle_sim": "Soft, swinging tentacles while it moves.",
    "trips_home": "Walks back to its house from time to time.",
    "dnd": "It sleeps and only shows small badges.",
    "mini_side": "Where it sits in mini mode.",
    "shell_menu": "Adds Smellyfish to the right-click menu of files and folders: details and start a CLI agent "
    "there. On Windows 11 it is under Show more options.",
    "auto_update": "Downloads new versions from GitHub and checks their SHA-256 before installing.",
    "game_mode": "Hides while a fullscreen app or game is in front.",
    "clicker": "Only counts how often you click or press a key, never which keys.",
    "media": "Reads the Windows media controls. Nothing leaves the PC.",
    "beat_sync": "Listens to the PC sound output to move with the beat.",
    "react_clipboard": "Reacts when you copy something or take a screenshot.",
    "usage_warn": "Warns when Claude Code or Codex use this much of a limit.",
    "claude_statusline": "Needs the Claude Code status line. Your own status line is never replaced.",
    "llm_enabled": "Talks to Ollama or llama.cpp on this PC or in your local network.",
    "llm_autostart": "Starts the model server itself when you chat.",
    "lan_visits": "Friends in your lobby can send their jellyfish over.",
    "weather_auto": "Uses the Windows location service.",
    "weather_ip": "Falls back to a rough location from your IP address.",
    "ask_in_bubble": "Answer a coding agent's questions with buttons instead of in the terminal.",
    "perm_in_bubble": "Allow or deny tool permissions with buttons instead of in the terminal.",
    "monitor": "The screen it lives on.",
}
if sys.platform == "darwin":
    HINTS.update(
        {
            "sit_on_icons": "Rests on desktop icons and files. Asks Finder where they are (macOS asks you once).",
            "shell_menu": "Adds Quick Actions to the right-click menu of files and folders in Finder: details and "
            "start a CLI agent there.",
            "trash_watch": "Asks Finder how full the Trash is (macOS asks you once). With Accessibility allowed it "
            "swims to the Trash in the Dock.",
            "clicker": "Only counts how often you click or press a key, never which keys. Needs Input Monitoring.",
            "media": "Spotify and Music report what they play. The buttons ask macOS once for access to the player.",
            "beat_sync": "Listens to the Mac's sound output to move with the beat. Needs Screen & System Audio "
            "Recording.",
            "weather_auto": "Uses the macOS location service.",
        }
    )
    PAGES = [
        (page, [("macOS" if title == "Windows" else title, hint, keys) for title, hint, keys in sections])
        for page, sections in PAGES
    ]

ADVANCED_ROWS = [
    ("llm_max_tokens", "Longest answer (tokens)", "spin", (32, 4000, 10)),
    ("llm_think", "Thinking", "combo", [("Off (fast)", "off"), ("Model default", "auto"), ("On (slow)", "on")]),
    (
        "llm_ctx",
        "Context size",
        "combo",
        [("Model default", 0), ("2048", 2048), ("4096", 4096), ("8192", 8192), ("16384", 16384), ("32768", 32768)],
    ),
    ("llm_temp", "Creativity", "dspin", (0.0, 1.5, 0.1)),
    ("llm_history", "Remembered messages", "spin", (0, 20, 1)),
    ("llm_persona", "Cute jellyfish personality", "check", None),
]

SPECIAL_SAVE = (
    "hooks",
    "codex_hooks",
    "gemini_hooks",
    "cursor_hooks",
    "copilot_hooks",
    "antigravity_hooks",
    "deepseek_hooks",
    "shell_menu",
    "autostart",
    "claude_statusline",
)


class Fold(QWidget):
    """A section that stays closed until it is opened (or a search matches something inside)."""

    def __init__(self, title):
        super().__init__()
        self.title, self.hits = title, 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.button = QPushButton()
        self.button.setObjectName("secondary")
        self.button.setCheckable(True)
        self.button.toggled.connect(self.set_open)
        lay.addWidget(self.button)
        self.body = QWidget()
        self.inner = QVBoxLayout(self.body)
        self.inner.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.body)
        self.set_open(False)

    def set_open(self, on):
        self.body.setVisible(on)
        self.button.blockSignals(True)
        self.button.setChecked(on)
        self.button.blockSignals(False)
        self.button.setText(f"{self.title}  [{'-' if on else '+'}]")


class SettingsWindow(QWidget):
    @staticmethod
    def _upd_busy(b, on, idle):
        try:
            b.setEnabled(not on)
            b.setText("Checking..." if on else idle)
        except RuntimeError:
            pass

    def __init__(self, app):
        super().__init__(None, Qt.Window)
        self.app = app
        self.setWindowTitle("Smellyfish Settings")
        theme.apply(self, app)
        self.resize(980, 700)
        self.setMinimumSize(760, 520)
        self.widgets, self.sliders, self.rows, self.sections, self.folds = {}, {}, [], [], []
        self.key_edits, self.llm_adv = {}, {}
        self._loading = True
        self._queue = {}
        self._timer = QTimer(self, singleShot=True, interval=450)
        self._timer.timeout.connect(self.flush)
        self._note_timer = QTimer(self, singleShot=True, interval=2500)
        self._note_timer.timeout.connect(lambda: self.note(""))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 10)
        outer.setSpacing(0)
        outer.addWidget(theme.banner("Settings", f"Smellyfish {__version__}"))
        body = QHBoxLayout()
        body.setContentsMargins(12, 12, 12, 0)
        body.setSpacing(12)
        outer.addLayout(body, 1)

        side = QVBoxLayout()
        side.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search settings...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter)
        side.addWidget(self.search)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(224)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav.setStyleSheet("QListWidget#nav::item { padding: 9px 8px; font-size: 14px; }")
        side.addWidget(self.nav, 1)
        body.addLayout(side)

        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)

        for index, (name, sections) in enumerate(PAGES):
            self.nav.addItem(name)
            self.stack.addWidget(self.build_page(index, sections))
        empty = QLabel("Nothing matches your search.")
        empty.setObjectName("hint")
        empty.setAlignment(Qt.AlignCenter)
        self.stack.addWidget(empty)
        self.nav.currentRowChanged.connect(lambda r: self.stack.setCurrentIndex(r) if r >= 0 else None)

        foot = QHBoxLayout()
        foot.setContentsMargins(12, 8, 12, 0)
        self.save_status = QLabel("Changes apply right away.")
        self.save_status.setObjectName("hint")
        foot.addWidget(self.save_status, 1)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        foot.addWidget(close)
        outer.addLayout(foot)

        app.llm.models_ready.connect(self.on_models)
        self.nav.setCurrentRow(0)
        self.refresh()

    # ------------------------------------------------------------ building
    def build_page(self, index, sections):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(12)
        scroll.setWidget(inner)
        self.page_index = index
        for title, hint, items in sections:
            box = QGroupBox(title.replace("&", "&&"))
            box_lay = QVBoxLayout(box)
            box_lay.setSpacing(10)
            if hint:
                h = QLabel(hint)
                h.setObjectName("hint")
                h.setWordWrap(True)
                box_lay.addWidget(h)
            self.sections.append(box)
            for item in items:
                if item.startswith("@"):
                    getattr(self, "block_" + item[1:])(box_lay, box)
                else:
                    self.add_option(box_lay, box, item)
            lay.addWidget(box)
        lay.addStretch(1)
        return scroll

    def register(self, lay, box, widget, text, fold=None):
        lay.addWidget(widget)
        if fold is not None:
            text = f"{text} {fold.title}"
        self.rows.append((widget, text.lower(), box, self.page_index, fold))

    @staticmethod
    def field_label(text):
        lab = QLabel(text)
        lab.setMinimumWidth(230)
        return lab

    def hint_label(self, text):
        h = QLabel(text)
        h.setObjectName("hint")
        h.setWordWrap(True)
        h.setContentsMargins(24, 0, 0, 0)
        return h

    def row_widget(self, hint=""):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(top)
        if hint:
            lay.addWidget(self.hint_label(hint))
        return w, top

    def add_option(self, lay, box, key, fold=None):
        label, choices = SCHEMA_BY_KEY[key]
        hint = HINTS.get(key, "")
        w, top = self.row_widget(hint)
        text = f"{label} {hint}"
        if key in ("volume", "notify_volume"):
            top.addWidget(self.field_label(label))
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            value_label = QLabel("")
            value_label.setMinimumWidth(44)
            slider.valueChanged.connect(
                lambda v, lb=value_label, k=key: (lb.setText(f"{v} %"), self.changed(k, v, later=True))
            )
            test = QPushButton("Test")
            test.setObjectName("secondary")
            test.clicked.connect(lambda _c=False, k=key, sl=slider: self.app.test_sound(k, sl.value()))
            top.addWidget(slider, 1)
            top.addWidget(value_label)
            top.addWidget(test)
            self.sliders[key] = (slider, value_label)
        elif callable(choices) or choices:
            if callable(choices):
                choices = choices()
            top.addWidget(self.field_label(label))
            combo = QComboBox()
            for t, value in choices:
                combo.addItem(t, value)
            combo.currentIndexChanged.connect(lambda _i, k=key, c=combo: self.changed(k, c.currentData()))
            top.addWidget(combo, 1)
            if key == "skin":
                combo.setIconSize(QSize(48, 39))
                pick = QPushButton("Pick...")
                pick.setObjectName("secondary")
                pick.clicked.connect(self.pick_color)
                top.addWidget(pick)
            if key == "scale":
                self.custom = QSpinBox()
                self.custom.setRange(1, 16)
                self.custom.setPrefix("Custom: ")
                self.custom.valueChanged.connect(lambda v: self.changed("scale", v, later=True))
                top.addWidget(self.custom)
            self.widgets[key] = combo
        else:
            cb = QCheckBox(label)
            cb.toggled.connect(lambda on, k=key: self.changed(k, on))
            top.addWidget(cb, 1)
            self.widgets[key] = cb
        self.register(lay, box, w, text, fold)

    def text_row(self, lay, box, label, edit, placeholder="", extra=None, hint="", fold=None):
        w, top = self.row_widget(hint)
        top.addWidget(self.field_label(label))
        edit.setPlaceholderText(placeholder)
        top.addWidget(edit, 1)
        for e in extra or []:
            top.addWidget(e)
        self.register(lay, box, w, f"{label} {placeholder} {hint}", fold)

    def button_row(self, lay, box, text, fn, hint, keep=None):
        w, top = self.row_widget()
        b = QPushButton(text)
        b.setObjectName("secondary")
        b.setMinimumWidth(190)
        b.clicked.connect(fn)
        top.addWidget(b)
        h = QLabel(hint)
        h.setObjectName("hint")
        h.setWordWrap(True)
        top.addWidget(h, 1)
        self.register(lay, box, w, f"{text} {hint}")
        return b

    # ------------------------------------------------------------ special blocks
    def block_home(self, lay, box):
        self.button_row(lay, box, "Set home here", self.app.set_home_here, "Moves its house to where it stands now.")
        self.button_row(lay, box, "Go home", self.app.go_home, "Sends it back to its house.")

    def block_discord_setup(self, lay, box):
        self.button_row(lay, box, "Discord setup...", self.app.open_discord_setup, "Step by step guide to connect it.")

    def block_lobby(self, lay, box):
        self.button_row(lay, box, "Open the lobby...", self.app.open_lobby, "Meet other jellyfish on your network.")

    def block_weather(self, lay, box):
        self.place = QLineEdit()
        self.place.textEdited.connect(lambda t: self.changed("weather_place", t.strip(), later=True))
        self.weather_status = QLabel(self.app.weather.text)
        self.weather_status.setObjectName("hint")
        self.weather_status.setWordWrap(True)
        self.text_row(lay, box, "Place", self.place, "e.g. Berlin", hint="")
        self.rows[-1][0].layout().addWidget(self.weather_status)

    def block_llm_connection(self, lay, box):
        self.llm_url = QLineEdit()
        self.llm_url.textEdited.connect(lambda t: self.changed("llm_url", t.strip(), later=True))
        self.text_row(lay, box, "Address", self.llm_url, "default: this PC")
        self.llm_model = QComboBox()
        self.llm_model.setEditable(True)
        self.llm_model.setMinimumWidth(220)
        self.llm_model.currentTextChanged.connect(lambda t: self.changed("llm_model", t.strip(), later=True))
        find = QPushButton("Find models")
        find.setObjectName("secondary")
        find.clicked.connect(self.find_models)
        w, top = self.row_widget()
        top.addWidget(self.field_label("Model"))
        top.addWidget(self.llm_model, 1)
        top.addWidget(find)
        self.register(lay, box, w, "Model find models")
        self.llm_status = QLabel("")
        self.llm_status.setObjectName("hint")
        lay.addWidget(self.llm_status)

    def block_llm_prompt(self, lay, box):
        self.llm_prompt = QLineEdit()
        self.llm_prompt.setMaxLength(600)
        self.llm_prompt.textEdited.connect(lambda t: self.changed("llm_prompt", t.strip(), later=True))
        self.text_row(
            lay,
            box,
            "Personality",
            self.llm_prompt,
            "extra instructions, e.g. call me captain",
            hint="Optional text added to every chat.",
        )

    def block_llm_advanced(self, lay, box):
        fold = Fold("Advanced model settings")
        self.folds.append(fold)
        lay.addWidget(fold)
        self.llm_binary = QLineEdit()
        self.llm_binary.textEdited.connect(lambda t: self.changed("llm_binary", t.strip(), later=True))
        self.text_row(
            fold.inner, box, "Program", self.llm_binary, "ollama / llama-server (empty = automatic)", fold=fold
        )
        self.llm_folder = QLineEdit()
        self.llm_folder.textEdited.connect(lambda t: self.changed("llm_models_dir", t.strip(), later=True))
        self.text_row(
            fold.inner, box, "Models folder", self.llm_folder, "llama.cpp only: folder with .gguf files", fold=fold
        )
        for key, label, kind, arg in ADVANCED_ROWS:
            w, top = self.row_widget()
            if kind == "check":
                c = QCheckBox(label)
                c.toggled.connect(lambda on, k=key: self.changed(k, on))
                top.addWidget(c, 1)
            else:
                top.addWidget(self.field_label(label))
                if kind == "spin":
                    c = QSpinBox()
                    c.setRange(arg[0], arg[1])
                    c.setSingleStep(arg[2])
                    c.valueChanged.connect(lambda v, k=key: self.changed(k, v, later=True))
                elif kind == "dspin":
                    c = QDoubleSpinBox()
                    c.setRange(arg[0], arg[1])
                    c.setSingleStep(arg[2])
                    c.setDecimals(1)
                    c.valueChanged.connect(lambda v, k=key: self.changed(k, round(v, 1), later=True))
                else:
                    c = QComboBox()
                    for t, value in arg:
                        c.addItem(t, value)
                    c.currentIndexChanged.connect(lambda _i, k=key, cb=c: self.changed(k, cb.currentData()))
                top.addWidget(c, 1)
            self.llm_adv[key] = c
            self.register(fold.inner, box, w, label, fold)
        w, top = self.row_widget()
        unload = QPushButton("Unload model now")
        unload.setObjectName("secondary")
        unload.clicked.connect(self.app.unload_llm)
        top.addWidget(unload)
        top.addStretch(1)
        self.register(fold.inner, box, w, "unload model now", fold)

    def block_hotkeys(self, lay, box):
        for action, label in hotkeys.ACTIONS:
            w, top = self.row_widget()
            lab = QLabel(label)
            lab.setMinimumWidth(230)
            top.addWidget(lab)
            edit = QKeySequenceEdit()
            edit.setMaximumSequenceLength(1)
            edit.editingFinished.connect(self.keys_changed)
            top.addWidget(edit, 1)
            clear = QPushButton("Clear")
            clear.setObjectName("secondary")
            clear.setToolTip("Remove this hotkey")
            clear.clicked.connect(lambda _=False, e=edit: (e.clear(), self.keys_changed()))
            top.addWidget(clear)
            default = hotkeys.DEFAULTS[action]
            reset = QPushButton("Default")
            reset.setObjectName("secondary")
            reset.setToolTip(f"Back to {default}" if default else "Back to no hotkey")
            reset.clicked.connect(
                lambda _=False, e=edit, a=action: (
                    e.setKeySequence(QKeySequence(hotkeys.DEFAULTS[a])),
                    self.keys_changed(),
                )
            )
            top.addWidget(reset)
            self.key_edits[action] = edit
            self.register(lay, box, w, f"{label} hotkey shortcut {default}")
        w, top = self.row_widget()
        self.key_status = QLabel("")
        self.key_status.setObjectName("hint")
        self.key_status.setWordWrap(True)
        top.addWidget(self.key_status, 1)
        reset_all = QPushButton("Reset all")
        reset_all.setObjectName("secondary")
        reset_all.clicked.connect(self.reset_keys)
        top.addWidget(reset_all)
        self.register(lay, box, w, "reset all hotkeys")

    def block_tools(self, lay, box):
        app = self.app
        for text, fn, hint in (
            ("Animation tester...", app.open_gallery, "Play every animation."),
            ("Show detected edges", app.show_edges, "Draws the window edges it can stand on for a moment."),
            ("Missed...", app.open_history, "Bubbles that came while you were away."),
            ("Achievements...", app.open_achievements, "Your trophies and counters."),
            ("Show the tour", lambda: (self.close(), app.start_tour(True)), "The short intro again."),
        ):
            self.button_row(lay, box, text, fn, hint)

    def block_about(self, lay, box):
        app = self.app
        h = QLabel(
            f"Version {__version__}. Smellyfish works fully offline; the only connection it makes on its "
            "own is the update check to GitHub."
        )
        h.setObjectName("hint")
        h.setWordWrap(True)
        lay.addWidget(h)
        self.button_row(lay, box, "About...", app.open_about, "People, licenses and links.")
        self.button_row(lay, box, "What's new...", app.open_changelog, "Changes in this version.")
        b = self.button_row(
            lay, box, "Check for updates", lambda: app.updater.check(manual=True), "Looks for a newer version now."
        )
        app.updater.busy.connect(lambda on, b=b: self._upd_busy(b, on, "Check for updates"))

    # ------------------------------------------------------------ search
    def filter(self, text):
        t = text.strip().lower()
        box_hits, page_hits = {}, {}
        for fold in self.folds:
            fold.hits = 0
        for widget, hay, box, page, fold in self.rows:
            show = not t or t in hay
            widget.setVisible(show)
            if show:
                box_hits[box] = box_hits.get(box, 0) + 1
                page_hits[page] = page_hits.get(page, 0) + 1
                if fold is not None:
                    fold.hits += 1
        for box in self.sections:
            box.setVisible(not t or box_hits.get(box, 0) > 0)
        for fold in self.folds:
            fold.setVisible(not t or fold.hits > 0)
            if t and fold.hits:
                fold.set_open(True)
        for i in range(self.nav.count()):
            self.nav.item(i).setHidden(bool(t) and page_hits.get(i, 0) == 0)
        if t and not page_hits:
            self.stack.setCurrentIndex(self.stack.count() - 1)
            return
        cur = self.nav.currentRow()
        if cur < 0 or self.nav.item(cur).isHidden():
            first = next((i for i in range(self.nav.count()) if not self.nav.item(i).isHidden()), 0)
            self.nav.setCurrentRow(first)
        self.stack.setCurrentIndex(max(0, self.nav.currentRow()))

    # ------------------------------------------------------------ applying
    def note(self, text):
        self.save_status.setText(text or "Changes apply right away.")
        if text:
            self._note_timer.start()

    def changed(self, key, value, later=False):
        if self._loading or value is None:
            return
        if later:
            self._queue[key] = value
            self._timer.start()
            return
        self._queue.pop(key, None)
        self.apply_now(key, value)

    def apply_now(self, key, value):
        if value == self.app.get_setting(key):
            return
        self.app.apply_setting(key, value)
        problems = "" if key in SPECIAL_SAVE else self.app.verify_saved([key])
        self.note("Could not save: " + problems if problems else "Saved")

    def flush(self):
        queue, self._queue = self._queue, {}
        for key in sorted(queue, key=lambda k: k != "skin_color"):
            self.apply_now(key, queue[key])

    def closeEvent(self, e):
        self._timer.stop()
        self.flush()
        e.accept()

    # ------------------------------------------------------------ values
    def refresh(self):
        self._loading = True
        queued = self._queue
        for key, (slider, value_label) in self.sliders.items():
            if key not in queued:
                slider.setValue(int(self.app.get_setting(key) or 0))
                value_label.setText(f"{slider.value()} %")
        for edit, key in (
            (self.place, "weather_place"),
            (self.llm_url, "llm_url"),
            (self.llm_prompt, "llm_prompt"),
            (self.llm_binary, "llm_binary"),
            (self.llm_folder, "llm_models_dir"),
        ):
            if key not in queued and not edit.hasFocus():
                edit.setText(self.app.get_setting(key) or "")
        for key, w in self.llm_adv.items():
            if key in queued:
                continue
            value = self.app.get_setting(key)
            if isinstance(w, QCheckBox):
                w.setChecked(value is not False)
            elif isinstance(w, QComboBox):
                w.setCurrentIndex(max(0, w.findData(value)))
            elif isinstance(w, QDoubleSpinBox):
                w.setValue(float(value or 0))
            else:
                w.setValue(int(value or 0))
        if "llm_model" not in queued and not self.llm_model.hasFocus():
            self.llm_model.setCurrentText(self.app.get_setting("llm_model") or "")
        for key, w in self.widgets.items():
            value = self.app.get_setting(key)
            if isinstance(w, QComboBox):
                w.setCurrentIndex(w.findData(value))
            else:
                w.setChecked(bool(value))
        if "scale" not in queued:
            self.custom.setValue(int(self.app.get_setting("scale")))
        self.refresh_skin_icons()
        keys = dict(hotkeys.DEFAULTS, **(self.app.get_setting("hotkeys") or {}))
        for action, edit in self.key_edits.items():
            edit.setKeySequence(QKeySequence(keys.get(action, "")))
        failed = self.app.hotkey_conflicts
        self.key_status.setText("Taken by another app: " + ", ".join(failed) if failed else "")
        self._loading = False

    def refresh_skin_icons(self):
        combo = self.widgets.get("skin")
        if combo is None:
            return
        c = (self.app.get_setting("skin_color") or "#c492ec").lstrip("#")
        custom = sprite.skin_from_color(tuple(int(c[i : i + 2], 16) for i in (0, 2, 4)))
        for i in range(combo.count()):
            value = combo.itemData(i)
            pal = custom if value == "custom" else sprite.SKINS.get(value)
            combo.setItemIcon(i, skin_icon(pal))

    def pick_color(self):
        color = QColorDialog.getColor(QColor(self.app.get_setting("skin_color") or "#c492ec"), self, "Jellyfish color")
        if color.isValid():
            self.changed("skin_color", color.name())
            self.changed("skin", "custom")

    def find_models(self):
        self.flush()
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
