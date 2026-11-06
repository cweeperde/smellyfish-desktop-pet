"""A small window to send a letter or a visit to someone in your lobby without opening the lobby window."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from smellyfish.art import sprite
from smellyfish.integrations import lan
from smellyfish.ui import theme


class QuickSend(QDialog):
    def __init__(self, app, mode="letter", target_name=None):
        super().__init__(None, Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.app, self.mode = app, mode
        self.setWindowTitle("Smellyfish - " + ("Letter" if mode == "letter" else "Visit"))
        theme.apply(self, app)
        self.setMinimumWidth(440)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 12)
        root.setSpacing(8)
        root.addWidget(theme.banner("Letter" if mode == "letter" else "Visit",
                                    "Write to someone in the lobby" if mode == "letter" else "Drop by someone's desktop",
                                    sprite.Pose(eyes="happy", arm_f=("rest_l", "up_r"))))
        body = QVBoxLayout()
        body.setContentsMargins(16, 4, 16, 0)
        body.setSpacing(8)
        root.addLayout(body)

        row = QHBoxLayout()
        row.addWidget(QLabel("To"))
        self.to = QComboBox()
        me = app.lan.me.id if app.lan.me else None
        for m in app.lan.roster:
            if m["id"] != me:
                self.to.addItem(m["name"] + ("  (owner)" if m.get("owner") else ""), m["id"])
                if target_name and m["name"] == target_name:
                    self.to.setCurrentIndex(self.to.count() - 1)
        row.addWidget(self.to, 1)
        body.addLayout(row)

        self.text = QLineEdit()
        self.text.setMaxLength(lan.TEXT_LIMIT["letter"])
        self.text.setPlaceholderText("Your letter...")
        self.text.setMinimumHeight(40)
        self.text.returnPressed.connect(self.send)
        if mode == "letter":
            body.addWidget(self.text)
        self.status = QLabel("")
        self.status.setObjectName("hint")
        self.status.setWordWrap(True)
        body.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        self.go = QPushButton("Send letter" if mode == "letter" else "Visit")
        self.go.setObjectName("primary")
        self.go.clicked.connect(self.send)
        buttons.addWidget(cancel)
        buttons.addWidget(self.go)
        body.addLayout(buttons)
        if self.to.count() == 0:
            self.status.setText("Nobody else is in the lobby yet.")
            self.go.setEnabled(False)
        (self.text if mode == "letter" else self.to).setFocus()

    def send(self):
        target = self.to.currentData()
        if target is None:
            return
        if self.mode == "letter":
            result = self.app.lan.send("letter", to=target, text=self.text.text())
        else:
            result = self.app.lan.send("visit", to=target)
        if result.startswith("Wait"):
            fields = {"to": target}
            if self.mode == "letter":
                fields["text"] = self.text.text()
            if not self.app.queue_send(self.mode, **fields):
                return self.status.setText("Too many waiting messages, try again in a moment.")
            what = "Letter" if self.mode == "letter" else "Visit"
            secs = "".join(c for c in result if c.isdigit()) or "a few"
            self.app.notice({"kind": "wait", "chip": "Lobby", "text": f"{what} is queued and goes out in "
                             f"about {secs} s (cooldown)."}, seconds=5)
            return self.accept()
        if result:
            return self.status.setText(result)
        self.app.notice({"kind": "wait", "chip": "Lobby", "text": "Letter is on its way!" if self.mode == "letter"
                         else "Off you go! Your jellyfish waves."}, seconds=4)
        self.accept()
