"""LAN lobby window: host or join a lobby, chat, visit and send letters."""
import time

from PIL import Image
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QStackedWidget, QTextBrowser, QVBoxLayout,
                               QWidget)

from smellyfish import __version__
from smellyfish.art import sprite
from smellyfish.integrations import lan
from smellyfish.ui import theme

CROWN = ["Y...Y...Y", "YY.YYY.YY", "YYYYYYYYY", "YYYYYYYYY", "ooooooooo"]


def crown_icon():
    img = Image.new("RGBA", (9, 5), (0, 0, 0, 0))
    for y, row in enumerate(CROWN):
        for x, c in enumerate(row):
            if c != ".":
                img.putpixel((x, y), sprite.PAL[c] + (255,))
    img = img.resize((27, 15), Image.NEAREST)
    q = QImage(img.tobytes("raw", "RGBA"), img.width, img.height, QImage.Format_RGBA8888).copy()
    return QIcon(QPixmap.fromImage(q))


class LobbyWindow(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.Window)
        self.app = app
        self.service = app.lan
        self.setWindowTitle("Smellyfish - Lobby")
        theme.apply(self, app)
        self.resize(540, 640)
        self.crown = crown_icon()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 12)
        root.setSpacing(8)
        root.addWidget(theme.banner("Lobby", "Visit friends on your network",
                                    sprite.Pose(eyes="happy", arm_f=("rest_l", "up_r"))))
        body = QVBoxLayout()
        body.setContentsMargins(14, 0, 14, 0)
        body.setSpacing(8)
        root.addLayout(body, 1)

        self.name_row = QWidget()
        row = QHBoxLayout(self.name_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Your name"))
        self.name = QLineEdit(app.lan_name())
        self.name.setMaxLength(lan.NAME_LIMIT)
        self.name.editingFinished.connect(self.save_name)
        row.addWidget(self.name, 1)
        body.addWidget(self.name_row)

        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        self.pages.addWidget(self.build_start())
        self.pages.addWidget(self.build_room())

        self.status = QLabel("")
        self.status.setObjectName("hint")
        self.status.setWordWrap(True)
        body.addWidget(self.status)

        s = self.service
        s.state.connect(self.on_state)
        s.members.connect(self.on_members)
        s.chat.connect(self.on_chat)
        s.notice.connect(self.set_status)
        s.lobbies.connect(self.on_lobbies)
        self.tick = QTimer(self, timeout=self.update_buttons)
        self.tick.start(500)
        self.on_state(self.state_name())
        self.on_members(s.roster)

    # ------------------------------------------------------------ pages
    def build_start(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)

        host = QGroupBox("Create a lobby")
        hl = QVBoxLayout(host)
        r = QHBoxLayout()
        self.lobby_name = QLineEdit()
        self.lobby_name.setPlaceholderText("Lobby name")
        self.lobby_name.setMaxLength(24)
        self.password = QLineEdit()
        self.password.setPlaceholderText(f"Password (empty = make one up, at least {lan.MIN_PASSWORD})")
        self.password.setMaxLength(40)
        r.addWidget(self.lobby_name, 1)
        r.addWidget(self.password, 1)
        hl.addLayout(r)
        create = QPushButton("Create lobby")
        create.setObjectName("primary")
        create.clicked.connect(self.create)
        hl.addWidget(create)
        hint = QLabel("Friends on your network see it and need the password to come in. Everything is encrypted "
                      "and stays inside your network. As the owner you relay (and can read) the messages.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        hl.addWidget(hint)
        lay.addWidget(host)

        join = QGroupBox("Join a lobby")
        jl = QVBoxLayout(join)
        self.found = QListWidget()
        self.found.setMinimumHeight(90)
        self.found.itemSelectionChanged.connect(self.pick_found)
        self.found.itemDoubleClicked.connect(lambda _i: self.join())
        jl.addWidget(self.found, 1)
        r = QHBoxLayout()
        self.address = QLineEdit()
        self.address.setPlaceholderText("or type an address, e.g. 192.168.1.20:47813")
        r.addWidget(self.address, 1)
        again = QPushButton("Refresh")
        again.setObjectName("secondary")
        again.clicked.connect(self.rescan)
        r.addWidget(again)
        go = QPushButton("Join...")
        go.setObjectName("primary")
        go.clicked.connect(self.join)
        r.addWidget(go)
        jl.addLayout(r)
        self.empty_hint = QLabel("Nothing shows up? Ask the host for the address (it is shown in their lobby) "
                                 "and type it above. Both sides need the same Smellyfish version.")
        self.empty_hint.setObjectName("hint")
        self.empty_hint.setWordWrap(True)
        jl.addWidget(self.empty_hint)
        lay.addWidget(join, 1)
        self.lobbies = []
        return page

    def build_room(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        top = QHBoxLayout()
        self.room_title = QLabel("")
        self.room_title.setObjectName("title")
        top.addWidget(self.room_title, 1)
        self.room_count = QLabel("")
        self.room_count.setObjectName("hint")
        top.addWidget(self.room_count)
        leave = QPushButton("Leave")
        leave.setObjectName("secondary")
        leave.clicked.connect(self.service.leave)
        top.addWidget(leave)
        lay.addLayout(top)

        self.lock = QLabel()
        self.lock.setObjectName("hint")
        self.lock.setTextFormat(Qt.RichText)
        self.lock.setWordWrap(True)
        lay.addWidget(self.lock)
        self.retint()
        theme.listen(self.retint)
        theme.listen(self.render_log)

        self.pw_row = QWidget()
        pr = QHBoxLayout(self.pw_row)
        pr.setContentsMargins(0, 0, 0, 0)
        pr.addWidget(QLabel("Password"))
        self.pw_field = QLineEdit()
        self.pw_field.setReadOnly(True)
        self.pw_field.setEchoMode(QLineEdit.Password)
        pr.addWidget(self.pw_field, 1)
        self.pw_show = QPushButton("Show")
        self.pw_show.setObjectName("secondary")
        self.pw_show.setCheckable(True)
        self.pw_show.toggled.connect(self.toggle_password)
        pr.addWidget(self.pw_show)
        copy = QPushButton("Copy")
        copy.setObjectName("secondary")
        copy.clicked.connect(self.copy_password)
        pr.addWidget(copy)
        lay.addWidget(self.pw_row)
        self.addr_hint = QLabel("")
        self.addr_hint.setObjectName("hint")
        self.addr_hint.setWordWrap(True)
        lay.addWidget(self.addr_hint)

        mid = QHBoxLayout()
        self.members = QListWidget()
        self.members.setMaximumWidth(190)
        self.members.setIconSize(QSize(27, 15))
        self.members.itemSelectionChanged.connect(self.update_buttons)
        mid.addWidget(self.members)
        side = QVBoxLayout()
        self.visit_button = QPushButton("Visit")
        self.visit_button.setObjectName("primary")
        self.visit_button.clicked.connect(self.visit)
        self.letter_button = QPushButton("Send letter...")
        self.letter_button.setObjectName("primary")
        self.letter_button.clicked.connect(self.letter)
        self.kick_button = QPushButton("Remove from lobby")
        self.kick_button.setObjectName("secondary")
        self.kick_button.clicked.connect(self.kick)
        side.addWidget(self.visit_button)
        side.addWidget(self.letter_button)
        side.addWidget(self.kick_button)
        note = QLabel("Pick someone in the list. Visits and letters arrive through their door.")
        note.setObjectName("hint")
        note.setWordWrap(True)
        side.addWidget(note)
        side.addStretch(1)
        mid.addLayout(side, 1)
        lay.addLayout(mid)

        self.log = QTextBrowser()
        lay.addWidget(self.log, 1)
        r = QHBoxLayout()
        self.text = QLineEdit()
        self.text.setMaxLength(lan.TEXT_LIMIT["chat"])
        self.text.setPlaceholderText("Say something to everyone")
        self.text.setMinimumHeight(36)
        self.text.returnPressed.connect(self.chat)
        send = QPushButton("Send")
        send.setObjectName("primary")
        send.clicked.connect(self.chat)
        r.addWidget(self.text, 1)
        r.addWidget(send)
        lay.addLayout(r)
        self.entries = []
        return page

    # ------------------------------------------------------------ actions
    def state_name(self):
        s = self.service
        if s.role == "host":
            return "hosting"
        if s.role == "client":
            return "joined" if s.me is not None else "connecting"
        return "off"

    def save_name(self):
        self.app.cfg.set("lan_name", lan.clean(self.name.text(), lan.NAME_LIMIT))

    def my_name(self):
        self.save_name()
        return self.app.lan_name()

    def create(self):
        password = self.service.host(self.my_name(), self.app.lan_color(), self.lobby_name.text(),
                                     self.password.text())
        if password:
            self.password.clear()

    def pick_found(self):
        i = self.found.currentRow()
        if 0 <= i < len(self.lobbies):
            item = self.lobbies[i]
            self.address.setText(f"{item['ip']}:{item['port']}")

    def join(self):
        i = self.found.currentRow()
        chosen = self.lobbies[i] if 0 <= i < len(self.lobbies) else None
        if chosen is not None and not chosen.get("ok", True):
            return self.set_status(f"That lobby runs Smellyfish {chosen['ver']} and you have {__version__}. "
                                   "Update so both match.")
        text = self.address.text().strip()
        host, _, port = text.rpartition(":")
        if not host or not port.isdigit():
            return self.set_status("Pick a lobby or type its address, like 192.168.1.20:47813")
        label = chosen["name"] if chosen is not None and f"{chosen['ip']}:{chosen['port']}" == text else text
        password, ok = QInputDialog.getText(self, "Join lobby", f"Password for {label}:", QLineEdit.Password)
        if not ok or not password.strip():
            return
        self.service.join(host, int(port), password, self.my_name(), self.app.lan_color())

    def rescan(self):
        self.service.browse(False)
        self.service.browse(True)
        self.on_lobbies([])
        self.set_status("Looking for lobbies on your network...")

    def selected(self):
        item = self.members.currentItem()
        return item.data(Qt.UserRole) if item else None

    def selected_name(self):
        item = self.members.currentItem()
        return item.data(Qt.UserRole + 1) if item else ""

    def visit(self):
        target = self.selected()
        if target is None:
            return self.set_status("Select someone first")
        self.set_status(self.service.send("visit", to=target) or "Off you go! Your jellyfish waves.")

    def letter(self):
        target = self.selected()
        if target is None:
            return self.set_status("Select someone first")
        text, ok = QInputDialog.getText(self, "Smellyfish - Letter", "Your letter:", QLineEdit.Normal, "")
        if ok and text.strip():
            self.set_status(self.service.send("letter", to=target, text=text) or "Letter is on its way!")

    def kick(self):
        target = self.selected()
        if target is None or self.service.role != "host":
            return
        name = self.selected_name()
        ask = QMessageBox.question(self, "Remove from lobby", f"Remove {name} from the lobby?",
                                   QMessageBox.Yes | QMessageBox.No)
        if ask == QMessageBox.Yes:
            self.service.kick(target)

    def chat(self):
        text = self.text.text()
        if not text.strip():
            return
        result = self.service.send("chat", text=text)
        if result:
            return self.set_status(result)
        self.text.clear()

    def toggle_password(self, on):
        self.pw_field.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)
        self.pw_show.setText("Hide" if on else "Show")

    def copy_password(self):
        QGuiApplication.clipboard().setText(self.service.password)
        self.set_status("Password copied")

    # ------------------------------------------------------------ updates
    def retint(self):
        self.lock.setText(f'<span style="color:{theme.GOOD}">Encrypted.</span> Everything is scrambled on its way. '
                          "The lobby owner's PC passes the messages on, so the owner can read them.")

    def set_status(self, text):
        self.status.setText(text)

    def refresh(self):
        self.name.setText(self.app.lan_name())
        self.service.browse(self.state_name() == "off")

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def closeEvent(self, e):
        self.service.browse(False)
        super().closeEvent(e)

    def on_state(self, state):
        room = state in ("hosting", "joined")
        self.pages.setCurrentIndex(1 if room else 0)
        self.name_row.setVisible(not room)
        if self.isVisible():
            self.service.browse(not room and state != "connecting")
        if state == "connecting":
            self.set_status("Connecting...")
        if room:
            host = state == "hosting"
            self.room_title.setText(self.service.lobby_name)
            self.pw_row.setVisible(host)
            self.addr_hint.setVisible(host)
            self.kick_button.setVisible(host)
            self.pw_field.setText(self.service.password if host else "")
            self.pw_show.setChecked(False)
            if host:
                port = self.service.server.serverPort() if self.service.server else lan.DEFAULT_PORT
                where = ", ".join(f"{ip}:{port}" for ip in lan.local_addresses()[:3])
                self.addr_hint.setText("Friends find the lobby by themselves. If not, they can type: "
                                       + (where or "your IP address"))
            self.set_status("You are the owner." if host else "You are in.")
            self.entries = []
            self.render_log()
        elif state == "off":
            self.set_status("")
        self.update_buttons()

    def on_members(self, roster):
        keep = self.selected()
        self.members.clear()
        me = self.service.me.id if self.service.me else None
        for m in roster:
            item = QListWidgetItem(m["name"] + ("  (you)" if m["id"] == me else ""))
            item.setData(Qt.UserRole, m["id"])
            item.setData(Qt.UserRole + 1, m["name"])
            item.setForeground(QColor(m["color"]))
            if m.get("owner"):
                item.setIcon(self.crown)
            if m["id"] == me:
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.members.addItem(item)
            if m["id"] == keep:
                self.members.setCurrentItem(item)
        self.room_count.setText(f"{len(roster)}/{lan.MAX_MEMBERS}" if roster else "")
        self.update_buttons()

    def on_lobbies(self, items):
        self.lobbies = items
        keep = self.address.text()
        self.found.clear()
        for it in items:
            tag = f"v{it['ver']}" + ("" if it.get("ok", True) else "  (needs the same version)")
            row = QListWidgetItem(f"{it['name']}   {it['n']}/{it['max']}   {it['ip']}   {tag}")
            if not it.get("ok", True):
                row.setForeground(QColor(theme.MUTED))
            self.found.addItem(row)
        if not items:
            self.found.addItem("Looking for lobbies on your network...")
        self.empty_hint.setVisible(not items)
        self.address.setText(keep)

    def update_buttons(self):
        s = self.service
        has = self.selected() is not None
        self.visit_button.setEnabled(has and s.cooldown_left("visit") <= 0)
        self.letter_button.setEnabled(has and s.cooldown_left("letter") <= 0)
        self.kick_button.setEnabled(has and s.role == "host")
        waits = [(k, s.cooldown_left(k)) for k in ("visit", "letter")]
        self.visit_button.setText("Visit" if waits[0][1] <= 0 else f"Visit ({int(waits[0][1]) + 1} s)")
        self.letter_button.setText("Send letter..." if waits[1][1] <= 0 else f"Letter ({int(waits[1][1]) + 1} s)")

    def on_chat(self, name, text):
        self.entries.append((time.strftime("%H:%M"), name, text))
        del self.entries[:-200]
        self.render_log()

    def render_log(self):
        def esc(t):
            return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.log.setHtml("".join(
            f'<p><span style="color:{theme.MUTED}">{t}</span> <b style="color:{theme.HEAD}">{esc(n)}</b> '
            f'{esc(x)}</p>' for t, n, x in self.entries))
        bar = self.log.verticalScrollBar()
        bar.setValue(bar.maximum())
