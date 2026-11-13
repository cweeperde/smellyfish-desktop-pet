"""Debug endpoints of the local server, only reachable with SMELLYFISH_DEBUG=1 (used by the release check)."""

import time

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCursor, QGuiApplication

from smellyfish.art import sprite
from smellyfish.ui.about_window import AboutWindow
from smellyfish.ui.changelog_window import ChangelogWindow
from smellyfish.ui.gallery import DiscordSetup, GalleryWindow, HistoryWindow
from smellyfish.ui.lobby_window import LobbyWindow
from smellyfish.ui.settings_window import SettingsWindow
from smellyfish.ui.todo_window import TodoWindow
from smellyfish.ui.views import BODY_X0


def endpoints(app):
    table = {
        "state": lambda _: {
            "anim": app.player.name,
            "base": app.player.base,
            "mode": app.player.mode,
            "bubble": app.bubble_kind(),
            "interactive": len(app.interactive),
            "phys": app.phys,
            "pos": [round(app.x), round(app.y)],
            "feet": round(app.feet()),
            "cx": round(app.cx()),
            "perch": bool(app.perch),
            "homing": app.homing,
            "home": app.home(),
            "unseen": app.unseen,
            "sessions": len(app.sessions),
            "focus": app.focus.phase,
            "badge": app.badge.isVisible(),
            "snacks": app.life.stats.get("snacks", 0),
            "carrying": app.carrying,
            "mini": bool(app.cfg.get("mini")),
            "achievements": sorted(app.life.unlocked),
            "info": {k: v for k, v in (app.info or {}).items() if k in ("chip", "right", "text")},
            "badge_items": [it[0] for it in getattr(app, "badge_items", [])],
            "trash_visit": app.trash_visit,
            "screen": [app.bounds().x(), app.bounds().y()],
            "chasing": time.time() < app.chase_until,
        },
    }
    for name in (
        "click",
        "snap",
        "poke",
        "fling",
        "drag",
        "home",
        "sethome",
        "house",
        "play",
        "focus",
        "dnd",
        "hotkey",
        "snack",
        "ball",
        "clip",
        "mini",
        "trash",
        "setting",
        "stroke",
        "ui",
    ):
        table[name] = (lambda n: lambda p: (app.server.debug_cmd.emit((n, p)), {"queued": True})[1])(name)
    return table


def handle(app, cmd):
    kind, p = cmd
    if kind == "ui":
        from smellyfish.ui.gallery import AchievementsWindow, ReminderDialog

        win = {
            "settings": lambda: app._open("settings_win", SettingsWindow),
            "gallery": lambda: app._open("gallery_win", GalleryWindow),
            "history": lambda: app._open("history_win", HistoryWindow),
            "discord": lambda: app._open("discord_win", DiscordSetup),
            "achievements": lambda: app._open("achievements_win", AchievementsWindow),
            "todo": lambda: app._open("todo_win", TodoWindow),
            "changelog": lambda: app._open("changelog_win", ChangelogWindow),
            "calendar": lambda: (app.open_calendar(), app.calendar_win)[1],
            "about": lambda: app._open("about_win", AboutWindow),
            "lobby": lambda: app._open("lobby_win", LobbyWindow),
            "reminder": lambda: ReminderDialog(app),
        }[p["name"]]()
        win.show()
        if p.get("size"):
            win.resize(*p["size"])
        QTimer.singleShot(600, lambda: (win.grab().save(p["path"]), win.close()))
    if kind == "trash":
        if p.get("emptied"):
            old, app.trash.state = app.trash.state, (0, 0)
            return app.on_trash(old, (0, 0))
        if p.get("state"):
            app.trash.state = tuple(p["state"])
        app.maybe_report_trash(force=True)
    elif kind == "stroke":
        from PySide6.QtCore import QPoint as P

        p0 = app.pix
        y = app.y + ((sprite.BY + 2) if p.get("zone") == "head" else (sprite.BY + 10)) * p0
        app.last_stroke = 0
        for i in range(10):
            x = app.x + (BODY_X0 + (3 if i % 2 else 11)) * p0
            app.check_stroke(P(round(x), round(y)), time.time() + i * 0.1)
    elif kind == "setting":
        app.apply_setting(p["key"], p["value"])
    if kind == "click":
        v = p.get("value")
        app.click_value(tuple(v) if isinstance(v, list) else v)
    elif kind == "snap":
        path = p.get("path", "snap.png")
        app.view.grab().save(path)
        for w, suffix in ((app.bubble, "_bubble"), (app.house, "_house"), (app.badge, "_badge")):
            if w.isVisible():
                w.grab().save(path.replace(".png", suffix + ".png"))
    elif kind == "poke":
        app.poke()
    elif kind == "fling":
        app.tick.stop()
        app.phys = "rest"
        app.move_to(p.get("x", app.x), p.get("y", app.y))
        app.fall(p.get("vx", 0.0), p.get("vy", 0.0))
    elif kind == "drag":
        app.press = (QCursor.pos(), time.time())
        app.start_hang(QCursor.pos())
        QTimer.singleShot(int(p.get("ms", 600)), app.drop)
    elif kind == "home":
        app.go_home()
    elif kind == "sethome":
        app.cfg.set("home", p.get("home"))
        app.refresh_house()
    elif kind == "house":
        app.house_click(p.get("prop"))
    elif kind == "play":
        app.preview_anim(p.get("name"))
    elif kind == "focus":
        app.focus.start(p.get("phase", "focus")) if p.get("start", True) else app.focus.stop()
        if p.get("end"):
            app.focus.ends_at = time.time()
    elif kind == "dnd":
        app.apply_setting("dnd", bool(p.get("on")))
    elif kind == "hotkey":
        app.on_hotkey(p.get("action"))
    elif kind == "snack":
        app.give_snack()
    elif kind == "ball":
        app.throw_ball()
    elif kind == "mini":
        app.toggle_mini()
    elif kind == "clip":
        app.last_clip = 0
        QGuiApplication.clipboard().setText(p.get("text", "hello"))
        app.last_clip = 0
        app.on_clipboard()
