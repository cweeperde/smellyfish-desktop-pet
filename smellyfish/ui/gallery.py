"""Animation tester, missed-bubbles history and the Discord setup guide."""

import time

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from smellyfish.art import sprite
from smellyfish.ui import theme

CATEGORIES = [
    (
        "Claude & Codex",
        [
            "thinking",
            "ponder",
            "working",
            "working_b",
            "question",
            "done",
            "done_b",
            "error",
            "exhausted",
            "warn",
            "compact",
        ],
    ),
    ("Tools", ["search", "search_b", "terminal", "terminal_b", "browse", "browse_b", "todo", "cooking"]),
    (
        "Moods",
        [
            "happy",
            "sad",
            "angry",
            "shy",
            "startle",
            "dizzy",
            "hello",
            "bye",
            "yawn",
            "tickled",
            "tickled_b",
            "petted",
            "petted_b",
        ],
    ),
    (
        "Idle",
        [
            "idle",
            "float",
            "breathe",
            "look_around",
            "bubbles",
            "read",
            "sneeze",
            "sleeping",
            "stretch",
            "yoyo",
            "juggle",
            "coffee",
            "gaming",
            "paper_plane",
            "bubblegum",
            "doodle",
            "fishing",
            "fishing_boot",
            "skateboard",
            "stargaze",
        ],
    ),
    ("Weather", ["sunny", "cloudy", "rainy", "stormy", "foggy", "windy", "snowy", "shiver"]),
    (
        "PC & apps",
        [
            "hot",
            "battery_low",
            "charging",
            "zap",
            "offline",
            "music",
            "music_bop",
            "call",
            "call_muted",
            "call_deaf",
            "mail",
            "focus",
        ],
    ),
    ("Calendar & reminders", ["calendar", "reminder", "alarm", "checkoff"]),
    ("Home & moving", ["water", "hop_prep", "rise", "sink", "land", "fall", "swim", "climb", "held", "peek", "tug"]),
    ("Toys & fun", ["snack", "nom", "camera", "trophy", "carry", "trash_full", "sweep"]),
]
SCALE = 8
BG = (34, 36, 48)


def styled(widget, app):
    from smellyfish.ui import theme

    theme.apply(widget, app)


class GalleryWindow(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.Window)
        self.app = app
        self.setWindowTitle("Smellyfish Animations")
        styled(self, app)
        self.anims = sprite.build_all()
        self.frames, self.idx = [], 0
        self.timer = QTimer(self, singleShot=True, timeout=self.next_frame)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(theme.banner("Animations", "Every move it knows", sprite.Pose(eyes="happy", tent="spread")))
        root = QHBoxLayout()
        root.setContentsMargins(10, 6, 10, 10)
        outer.addLayout(root, 1)
        self.list = QListWidget()
        self.list.setMinimumWidth(190)
        known = set()
        for title, names in CATEGORIES:
            head = QListWidgetItem(title.upper())
            head.setFlags(Qt.NoItemFlags)
            self.list.addItem(head)
            for n in names:
                if n in self.anims:
                    known.add(n)
                    it = QListWidgetItem("   " + n.replace("_", " "))
                    it.setData(Qt.UserRole, n)
                    self.list.addItem(it)
        rest = [n for n in self.anims if n not in known]
        if rest:
            head = QListWidgetItem("OTHER")
            head.setFlags(Qt.NoItemFlags)
            self.list.addItem(head)
            for n in rest:
                it = QListWidgetItem("   " + n.replace("_", " "))
                it.setData(Qt.UserRole, n)
                self.list.addItem(it)
        self.list.currentItemChanged.connect(
            lambda cur, _p: cur and cur.data(Qt.UserRole) and self.load(cur.data(Qt.UserRole))
        )
        root.addWidget(self.list)

        right = QVBoxLayout()
        self.view = QLabel()
        self.view.setFixedSize(sprite.CW * SCALE, sprite.CH * SCALE)
        self.view.setStyleSheet("background: #222430; border: 2px solid #8c60be;")
        right.addWidget(self.view)
        self.info = QLabel("")
        right.addWidget(self.info)

        row = QHBoxLayout()
        self.play_btn = QPushButton("Pause")
        self.play_btn.clicked.connect(self.toggle_play)
        prev_btn, next_btn = QPushButton("<"), QPushButton(">")
        prev_btn.clicked.connect(lambda: self.step(-1))
        next_btn.clicked.connect(lambda: self.step(1))
        self.loop = QCheckBox("Loop")
        self.loop.setChecked(True)
        for w in (prev_btn, self.play_btn, next_btn, self.loop):
            row.addWidget(w)
        right.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Speed"))
        self.speed = QSlider(Qt.Horizontal)
        self.speed.setRange(25, 200)
        self.speed.setValue(100)
        self.speed_label = QLabel("100 %")
        self.speed.valueChanged.connect(lambda v: self.speed_label.setText(f"{v} %"))
        row2.addWidget(self.speed, 1)
        row2.addWidget(self.speed_label)
        right.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Outfit"))
        self.outfit = QComboBox()
        self.outfit.addItem("none", None)
        for o in sprite.OUTFITS:
            self.outfit.addItem(o, o)
        self.outfit.currentIndexChanged.connect(lambda _i: self.show_frame())
        row3.addWidget(self.outfit, 1)
        on_pet = QPushButton("Play on Smellyfish")
        on_pet.clicked.connect(lambda: self.app.preview_anim(self.current))
        row3.addWidget(on_pet)
        right.addLayout(row3)
        right.addStretch(1)
        root.addLayout(right)
        self.current = None
        self.playing = True
        self.list.setCurrentRow(1)

    def load(self, name):
        self.current = name
        self.frames = sprite.full(self.anims[name])
        self.idx = 0
        self.show_frame()
        if self.playing:
            self.schedule()

    def show_frame(self):
        if not self.frames:
            return
        pose, ms = self.frames[self.idx]
        pose = sprite.with_outfit(pose, self.outfit.currentData())
        img = sprite.render(pose, SCALE, BG)
        data = img.tobytes()
        from PySide6.QtGui import QImage

        q = QImage(data, img.width, img.height, img.width * 3, QImage.Format_RGB888).copy()
        self.view.setPixmap(QPixmap.fromImage(q))
        self.info.setText(f"{self.current}   frame {self.idx + 1}/{len(self.frames)}   {ms} ms")

    def schedule(self):
        if self.frames:
            ms = self.frames[self.idx][1]
            self.timer.start(max(10, int(ms * 100 / self.speed.value())))

    def next_frame(self):
        if self.idx + 1 >= len(self.frames) and not self.loop.isChecked():
            self.playing = False
            self.play_btn.setText("Play")
            return
        self.idx = (self.idx + 1) % len(self.frames)
        self.show_frame()
        self.schedule()

    def toggle_play(self):
        self.playing = not self.playing
        self.play_btn.setText("Pause" if self.playing else "Play")
        if self.playing:
            if self.idx + 1 >= len(self.frames):
                self.idx = 0
            self.schedule()
        else:
            self.timer.stop()

    def step(self, d):
        self.playing = False
        self.play_btn.setText("Play")
        self.timer.stop()
        if self.frames:
            self.idx = (self.idx + d) % len(self.frames)
            self.show_frame()

    def closeEvent(self, e):
        self.timer.stop()
        super().closeEvent(e)


class HistoryWindow(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.Window)
        self.app = app
        self.setWindowTitle("Smellyfish - Missed")
        styled(self, app)
        self.resize(560, 460)
        root = QVBoxLayout(self)
        root.addWidget(theme.banner("Missed", "While you were away", sprite.Pose(ey=1)))
        hint = QLabel("Things that happened while you were away or in do-not-disturb. Double-click to show again.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.itemDoubleClicked.connect(lambda it: self.app.replay(it.data(Qt.UserRole)))
        root.addWidget(self.list, 1)
        row = QHBoxLayout()
        clear = QPushButton("Clear")
        clear.setObjectName("secondary")
        clear.clicked.connect(self.clear)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row.addWidget(clear)
        row.addStretch(1)
        row.addWidget(close)
        root.addLayout(row)

    def refresh(self):
        self.list.clear()
        for e in reversed(self.app.history):
            stamp = time.strftime("%H:%M", time.localtime(e["t"]))
            it = QListWidgetItem(f"{stamp}  [{e['source']}] {e['title']}\n{e['text']}")
            it.setData(Qt.UserRole, e)
            self.list.addItem(it)

    def clear(self):
        self.app.history.clear()
        self.app.badge_update()
        self.refresh()


DISCORD_STEPS = """<b>Connect Discord (about 3 minutes, once)</b><br><br>
<b>1.</b> Click <i>Open Developer Portal</i> and log in. Press <i>New Application</i>, name it
"Smellyfish", accept the terms.<br>
<b>2.</b> Open <i>OAuth2</i> in the left menu. Copy the <i>Client ID</i> into the field below.
Press <i>Reset Secret</i>, copy the secret into the second field.<br>
<b>3.</b> Still on <i>OAuth2</i>: under <i>Redirects</i> press <i>Add Redirect</i>, paste the redirect
URI shown below (use <i>Copy</i>), then <i>Save Changes</i>.<br>
<b>4.</b> Make sure the Discord desktop app is running, then press <i>Connect</i>. Discord shows a popup -
press <i>Authorize</i>.<br><br>
That's it: Smellyfish now sees mute / deafen and shows your Discord notifications. It reconnects by
itself when Discord restarts."""


class DiscordSetup(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.Window)
        self.app = app
        self.setWindowTitle("Smellyfish - Discord setup")
        styled(self, app)
        self.resize(620, 620)
        root = QVBoxLayout(self)
        root.addWidget(theme.banner("Discord", "Mute, deafen and messages", sprite.Pose(headset=True)))
        guide = QLabel(DISCORD_STEPS)
        guide.setWordWrap(True)
        guide.setTextFormat(Qt.RichText)
        root.addWidget(guide)
        portal = QPushButton("Open Developer Portal")
        portal.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://discord.com/developers/applications")))
        root.addWidget(portal)
        self.fields = {}
        for key, label, secret in (
            ("discord_client_id", "Client ID", False),
            ("discord_client_secret", "Client Secret", True),
            ("discord_redirect", "Redirect URI", False),
        ):
            row = QHBoxLayout()
            lab = QLabel(label)
            lab.setMinimumWidth(100)
            row.addWidget(lab)
            edit = QLineEdit(str(app.cfg.get(key) or ""))
            if secret:
                edit.setEchoMode(QLineEdit.Password)
            edit.editingFinished.connect(lambda k=key, e=edit: app.apply_setting(k, e.text().strip()))
            row.addWidget(edit, 1)
            if key == "discord_redirect":
                copy = QPushButton("Copy")
                copy.setObjectName("secondary")
                copy.clicked.connect(lambda _=False, e=edit: QGuiApplication.clipboard().setText(e.text()))
                row.addWidget(copy)
            root.addLayout(row)
            self.fields[key] = edit
        row = QHBoxLayout()
        self.status = QLabel(app.discord_status_text)
        self.status.setWordWrap(True)
        connect = QPushButton("Connect")
        connect.clicked.connect(self.connect)
        forget = QPushButton("Disconnect")
        forget.setObjectName("secondary")
        forget.clicked.connect(app.disconnect_discord)
        row.addWidget(self.status, 1)
        row.addWidget(forget)
        row.addWidget(connect)
        root.addLayout(row)

    def connect(self):
        for key, edit in self.fields.items():
            self.app.apply_setting(key, edit.text().strip())
        self.app.connect_discord()

    def set_status(self, text):
        self.status.setText(text)


class AchievementsWindow(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.Window)
        self.app = app
        self.setWindowTitle("Smellyfish - Achievements")
        styled(self, app)
        self.resize(520, 620)
        root = QVBoxLayout(self)
        root.addWidget(theme.banner("Achievements", "Collect them all"))
        self.summary = QLabel("")
        root.addWidget(self.summary)
        self.list = QListWidget()
        root.addWidget(self.list, 1)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        root.addWidget(close)

    def refresh(self):
        from smellyfish.features.life import ACHIEVEMENTS

        life = self.app.life
        self.summary.setText(f"Unlocked: {life.unlocked_count()}/{len(ACHIEVEMENTS)}")
        self.list.clear()
        for aid, title, desc, key, need in ACHIEVEMENTS:
            have = life.stats.get(key, 0)
            if aid in life.unlocked:
                when = time.strftime("%d.%m.%Y", time.localtime(life.unlocked[aid]))
                text = f"[x]  {title}  -  {desc}   ({when})"
            else:
                text = f"[ ]  {title}  -  {desc}   ({min(have, need)}/{need})"
            self.list.addItem(text)


from PySide6.QtWidgets import QDialog, QSpinBox  # noqa: E402


class ReminderDialog(QDialog):
    def __init__(self, app):
        super().__init__(None)
        self.setWindowTitle("Smellyfish - Remind me")
        styled(self, app)
        self.setMinimumWidth(460)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 14)
        root.setSpacing(10)
        root.addWidget(theme.banner("Remind me", "I'll tap you on the shoulder", sprite.Pose(arm_f=("rest_l", "up_r"))))
        body = QVBoxLayout()
        body.setContentsMargins(16, 4, 16, 0)
        body.setSpacing(8)
        root.addLayout(body)
        label = QLabel("WHAT?")
        label.setObjectName("title")
        body.addWidget(label)
        self.text = QLineEdit()
        self.text.setPlaceholderText("e.g. Drink some water")
        body.addWidget(self.text)
        label = QLabel("WHEN?")
        label.setObjectName("title")
        body.addWidget(label)
        row = QHBoxLayout()
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 720)
        self.minutes.setValue(20)
        self.minutes.setPrefix("in ")
        self.minutes.setSuffix(" min")
        for m in (5, 15, 30, 60):
            chip = QPushButton(f"{m} min" if m < 60 else "1 h")
            chip.setObjectName("chip")
            chip.clicked.connect(lambda _c=False, v=m: self.minutes.setValue(v))
            row.addWidget(chip)
        row.addWidget(self.minutes, 1)
        body.addLayout(row)
        buttons = QHBoxLayout()
        buttons.setContentsMargins(16, 6, 16, 0)
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Remind me")
        ok.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        root.addLayout(buttons)
        self.text.setFocus()

    def values(self):
        return self.text.text().strip(), self.minutes.value()
