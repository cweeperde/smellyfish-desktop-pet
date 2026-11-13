"""The to-do list window."""

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from smellyfish.art import sprite
from smellyfish.features import export
from smellyfish.features.todos import fmt_due
from smellyfish.ui import theme

PRESETS = [
    ("No reminder", None),
    ("In 15 min", 15),
    ("In 1 hour", 60),
    ("In 3 hours", 180),
    ("Tomorrow 9:00", "tomorrow"),
    ("At a time...", "at"),
]


def tomorrow_nine():
    t = time.localtime(time.time() + 86400)
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 9, 0, 0, 0, 0, -1))


def parse_clock(text):
    """'14:30' or '9' -> the next time the clock shows that (today, or tomorrow when it has passed)."""
    text = text.strip().replace(".", ":")
    try:
        h, _, m = text.partition(":")
        h, m = int(h), int(m or 0)
        if not (0 <= h < 24 and 0 <= m < 60):
            return None
    except ValueError:
        return None
    now = time.time()
    t = time.localtime(now)
    due = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, h, m, 0, 0, 0, -1))
    return due if due > now else due + 86400


def ask_due(parent, choice):
    """Turns a preset (see PRESETS) into a timestamp; returns (ok, due)."""
    if choice is None:
        return True, None
    if choice == "tomorrow":
        return True, tomorrow_nine()
    if choice == "at":
        text, ok = QInputDialog.getText(parent, "Smellyfish - Remind me", "Time (24 h, e.g. 14:30):")
        due = parse_clock(text) if ok else None
        return (True, due) if due else (False, None)
    return True, time.time() + choice * 60


class TodoWindow(QWidget):
    def __init__(self, app):
        super().__init__(None, Qt.Window)
        self.app = app
        self.building = False
        self.setWindowTitle("Smellyfish - To-do")
        theme.apply(self, app)
        self.resize(520, 560)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 12)
        root.setSpacing(8)
        board = sprite.Pose(
            ex=1, ey=1, arm_f=("rest_l", "up_r"), parts=[(sprite._clipboard(2), sprite.BX + 16, sprite.BY)]
        )
        root.addWidget(theme.banner("To-do", "Things to get done", board))

        body = QVBoxLayout()
        body.setContentsMargins(14, 0, 14, 0)
        body.setSpacing(8)
        root.addLayout(body, 1)

        add = QHBoxLayout()
        self.text = QLineEdit()
        self.text.setPlaceholderText("Add a task and press Enter")
        self.text.setMaxLength(200)
        self.text.returnPressed.connect(self.add)
        self.when = QComboBox()
        for label, _v in PRESETS:
            self.when.addItem(label)
        button = QPushButton("Add")
        button.clicked.connect(self.add)
        add.addWidget(self.text, 1)
        add.addWidget(self.when)
        add.addWidget(button)
        body.addLayout(add)

        self.list = QListWidget()
        self.list.setDragDropMode(QListWidget.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.menu)
        self.list.itemChanged.connect(self.changed)
        self.list.itemDoubleClicked.connect(self.edit)
        self.list.model().rowsMoved.connect(self.moved)
        body.addWidget(self.list, 1)

        hint = QLabel(
            "Tick a task to finish it. Double-click to rename, right-click for reminders, drag to reorder, Del removes."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        body.addWidget(hint)

        row = QHBoxLayout()
        self.clear_btn = QPushButton("Clear finished")
        self.clear_btn.setObjectName("secondary")
        self.clear_btn.clicked.connect(self.app.todo_clear_done)
        exp = QPushButton("Export...")
        exp.setObjectName("secondary")
        exp_menu = QMenu(exp)
        exp_menu.addAction("As Markdown (.md)...", lambda: self.export("md"))
        exp_menu.addAction("As CSV for Excel (.csv)...", lambda: self.export("csv"))
        exp.setMenu(exp_menu)
        exp.setProperty("menu", "1")
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row.addWidget(self.clear_btn)
        row.addWidget(exp)
        row.addStretch(1)
        row.addWidget(close)
        body.addLayout(row)
        self.text.setFocus()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Delete and self.list.hasFocus() and self.list.currentItem() is not None:
            self.app.todo_delete(self.list.currentItem().data(Qt.UserRole))
        elif e.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    def refresh(self):
        self.building = True
        keep = self.list.currentItem().data(Qt.UserRole) if self.list.currentItem() else None
        self.list.clear()
        todos = self.app.todos
        now = time.time()
        for t in todos.open_items() + [t for t in todos.items if t["done"]]:
            label = t["text"]
            if t["due"] and not t["done"]:
                label += f"   [{fmt_due(t['due'], now)}]"
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, t["id"])
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            it.setCheckState(Qt.Checked if t["done"] else Qt.Unchecked)
            font = QFont(it.font())
            if t["done"]:
                font.setStrikeOut(True)
                it.setForeground(QColor(theme.MUTED))
            elif t["due"] and t["due"] <= now:
                it.setForeground(QColor(theme.BAD))
            it.setFont(font)
            self.list.addItem(it)
            if t["id"] == keep:
                self.list.setCurrentItem(it)
        self.building = False
        n = len(todos.open_items())
        self.setWindowTitle(f"Smellyfish - To-do ({n} open)" if n else "Smellyfish - To-do")
        self.clear_btn.setEnabled(any(t["done"] for t in todos.items))

    def add(self):
        text = self.text.text().strip()
        if not text:
            return
        ok, due = ask_due(self, PRESETS[self.when.currentIndex()][1])
        if not ok:
            return
        self.text.clear()
        self.when.setCurrentIndex(0)
        self.app.todo_add(text, due)

    def changed(self, it):
        if self.building:
            return
        self.app.todo_set_done(it.data(Qt.UserRole), it.checkState() == Qt.Checked)

    def moved(self, *_):
        if not self.building:
            self.app.todos.reorder([self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())])

    def edit(self, it):
        tid = it.data(Qt.UserRole)
        t = self.app.todos.get(tid)
        if not t:
            return
        text, ok = QInputDialog.getText(self, "Smellyfish - Rename task", "Task:", text=t["text"])
        if ok and text.strip():
            self.app.todos.edit(tid, text=text)
            self.app.todos_changed()

    def menu(self, pos):
        it = self.list.itemAt(pos)
        if it is None:
            return
        tid = it.data(Qt.UserRole)
        m = QMenu(self)
        m.addAction("Rename...", lambda: self.edit(it))
        remind = m.addMenu("Remind me")
        for label, value in PRESETS[1:]:
            remind.addAction(label, lambda _c=False, v=value: self.remind(tid, v))
        remind.addAction("Remove reminder", lambda: self.remind(tid, None))
        m.addSeparator()
        m.addAction("Delete", lambda: self.app.todo_delete(tid))
        m.exec(self.list.viewport().mapToGlobal(pos))

    def remind(self, tid, choice):
        ok, due = ask_due(self, choice)
        if ok:
            self.app.todos.edit(tid, due=due)
            self.app.todos_changed()

    def export(self, kind):
        name = f"smellyfish-todo-{time.strftime('%Y-%m-%d')}.{kind}"
        filt = "Markdown (*.md)" if kind == "md" else "CSV (*.csv)"
        path, _ = QFileDialog.getSaveFileName(self, "Export to-dos and reminders", name, filt)
        if not path:
            return
        todos, reminders = self.app.todos.items, list(self.app.cfg.get("reminders") or [])
        text = export.todos_markdown(todos, reminders) if kind == "md" else export.todos_csv(todos, reminders)
        try:
            export.save(path, text)
        except OSError as e:
            QMessageBox.warning(self, "Smellyfish", f"Could not save the file:\n{e}")
