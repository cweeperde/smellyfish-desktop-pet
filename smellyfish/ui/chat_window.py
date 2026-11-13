"""A small window to talk to the local model."""

import re

from PIL import Image, ImageDraw
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser, QVBoxLayout, QWidget

from smellyfish.art import sprite
from smellyfish.ui import theme


class ChatWindow(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.Window)
        self.app = app
        self.setWindowTitle("Smellyfish - Chat")
        theme.apply(self, app)
        self.resize(440, 520)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 12)
        root.setSpacing(8)
        root.addWidget(theme.banner("Chat", "Ask me anything", sprite.Pose(eyes="happy", blush=True)))

        body = QVBoxLayout()
        body.setContentsMargins(14, 0, 14, 0)
        body.setSpacing(8)
        root.addLayout(body, 1)

        self.log = QTextBrowser()
        self.log.setOpenLinks(False)
        body.addWidget(self.log, 1)
        self.bar = QLabel()
        self.bar.setFixedHeight(18)
        body.addWidget(self.bar)
        self.status = QLabel("")
        self.status.setObjectName("hint")
        body.addWidget(self.status)
        self.step = 0
        theme.listen(self.render)
        self.anim = QTimer(self, timeout=self.tick)
        self.anim.start(160)

        row = QHBoxLayout()
        self.text = QLineEdit()
        self.text.setPlaceholderText("Say something and press Enter")
        self.text.setMaxLength(2000)
        self.text.returnPressed.connect(self.send)
        send = QPushButton("Send")
        send.clicked.connect(self.send)
        clear = QPushButton("New chat")
        clear.setObjectName("secondary")
        clear.clicked.connect(self.clear)
        unload = QPushButton("Unload model")
        unload.setObjectName("secondary")
        unload.setToolTip("Frees the memory the model uses right now")
        unload.clicked.connect(self.app.unload_llm)
        font = self.text.font()
        font.setPointSize(11)
        self.text.setFont(font)
        self.text.setMinimumHeight(42)
        body.addWidget(self.text)
        row.addWidget(send)
        row.addWidget(clear)
        row.addWidget(unload)
        row.addStretch(1)
        body.addLayout(row)

    def tick(self):
        self.step += 1
        busy = bool(self.app.llm_phase)
        loaded = self.app.llm.loaded and not busy
        n, on = 24, 3
        off = tuple(int(theme.SEC[i : i + 2], 16) for i in (1, 3, 5))
        img = Image.new("RGBA", (n * 4, 6), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for i in range(n):
            if busy:
                lit = (i - self.step) % n < on * 2
                color = (196, 146, 236) if lit else off
            else:
                color = (130, 230, 150) if loaded else off
            d.rectangle([i * 4, 0, i * 4 + 2, 5], fill=color + (255,))
        big = img.resize((img.width * 3, img.height * 3), Image.NEAREST)
        q = QImage(big.tobytes("raw", "RGBA"), big.width, big.height, QImage.Format_RGBA8888).copy()
        self.bar.setPixmap(QPixmap.fromImage(q))
        if busy and self.step % 3 == 0:
            self.render()
            self.status.setText(self.app.llm_status())

    def refresh(self):
        self.status.setText(self.app.llm_status())
        self.text.setFocus()

    def showEvent(self, e):
        super().showEvent(e)
        self.app.llm.preload()
        self.refresh()
        self.render()

    def render(self):
        def esc(t):
            t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parts = re.split(r"```[^\n]*\n?(.*?)(?:```|$)", t, flags=re.S)
            out = []
            for i, part in enumerate(parts):
                if i % 2:
                    out.append(f'<pre style="background:#0c0a12;color:#82e696;padding:6px">{part.strip(chr(10))}</pre>')
                else:
                    out.append(part.replace("\n", "<br>"))
            return "".join(out)

        html = []
        for who, text in self.app.chat_log:
            if who == "help":
                html.append(f'<p style="color:{theme.MUTED}"><b>how to fix this</b><br>{esc(text)}</p>')
            elif who == "wait":
                dots = "." * (1 + (self.step // 3) % 3)
                html.append(f'<p style="color:{theme.HEAD}"><b>smellyfish</b><br>{esc(text)}{dots}</p>')
            elif who == "you":
                html.append(f'<p style="color:{theme.MUTED}"><b>you</b><br>{esc(text)}</p>')
            else:
                html.append(f'<p style="color:{theme.HEAD}"><b>smellyfish</b><br>{esc(text)}</p>')
        self.log.setHtml("".join(html))
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def send(self):
        text = self.text.text().strip()
        if not text or self.app.llm.busy:
            return
        self.text.clear()
        self.app.ask_llm(text)

    def clear(self):
        self.app.chat_log = []
        self.app.llm.reset()
        self.render()
