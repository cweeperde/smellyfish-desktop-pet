"""Shared pixel-art look for all windows: bevelled panels, chunky buttons and pixel headers.

Everything exists in a dark and a light version. set_dark() switches the palette and restyles every open window."""
import os
import weakref

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QAbstractSlider, QAbstractSpinBox, QApplication, QComboBox, QLabel, QScrollArea, QScrollBar

from smellyfish.art import sprite
from smellyfish.paths import HOME_DIR

INK = "#221634"

PALETTES = {
    True: dict(BG="#1d1828", PANEL="#2a2438", FIELD="#141019", TEXT="#f2ecfa", MUTED="#a898c0", LAV="#c492ec",
               LIGHT="#e2c0fa", DARK="#8c60be", DEEP="#5a3d80", HEAD="#e2c0fa", EDGE="#0a0810", SEC="#3a3150",
               SEC_TOP="#5a4d74", SEC_BOT="#141019", SEC_HOVER="#4a3f66", GOOD="#82e696", WARN="#ffd250",
               BAD="#ff8a8a", PREVIEW="#222430", ARROW=(226, 192, 250, 255), SHADOW=(34, 22, 52, 255),
               SUB=(168, 152, 192, 255), TITLE=(226, 192, 250, 255)),
    False: dict(BG="#f4f0fa", PANEL="#ffffff", FIELD="#ffffff", TEXT="#2a1f3d", MUTED="#7a6c96", LAV="#c492ec",
                LIGHT="#eadcfb", DARK="#8c60be", DEEP="#a98bd0", HEAD="#6a3fa0", EDGE="#cbbfe0", SEC="#e6dcf3",
                SEC_TOP="#f6f0fd", SEC_BOT="#bba9d8", SEC_HOVER="#dccff0", GOOD="#2e8f52", WARN="#a87400",
                BAD="#c0392b", PREVIEW="#e9e3f4", ARROW=(90, 61, 128, 255), SHADOW=(226, 214, 244, 255),
                SUB=(122, 108, 150, 255), TITLE=(106, 63, 160, 255)),
}
IS_DARK = True
globals().update(PALETTES[True])

_themed = weakref.WeakSet()
_banners = weakref.WeakSet()
_listeners = []


def listen(fn):
    """Calls fn whenever the dark/light mode changes."""
    _listeners.append(fn)


def _style():
    return f"""
* {{ font-family: "Cascadia Mono", "Consolas", monospace; }}
QWidget {{ background: {BG}; color: {TEXT}; font-size: 13px; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: {BG}; border: none; }}
QGroupBox {{ background: {PANEL}; border: 3px solid {DARK}; border-top-color: {LAV}; border-left-color: {LAV};
             border-bottom-color: {DEEP}; border-right-color: {DEEP};
             margin-top: 18px; padding: 12px 10px 8px 10px; font-weight: bold; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 2px 8px;
                    background: {LAV}; color: {INK}; }}
QGroupBox QWidget {{ background: {PANEL}; }}
QLabel {{ background: transparent; }}
QLabel#hint {{ color: {MUTED}; font-size: 11px; }}
QLabel#title {{ color: {HEAD}; font-size: 15px; font-weight: bold; }}
QCheckBox {{ spacing: 10px; background: transparent; }}
QCheckBox:unchecked {{ color: {MUTED}; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 3px solid {DEEP}; background: {FIELD}; }}
QCheckBox::indicator:hover {{ border-color: {LAV}; }}
QCheckBox::indicator:checked {{ background: {LAV}; border-color: {LIGHT}; image: url(CHECK_PNG); }}
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit, QKeySequenceEdit, QTextEdit, QPlainTextEdit {{
    background: {FIELD}; color: {TEXT}; border: 3px solid {DEEP}; border-top-color: {EDGE};
    border-left-color: {EDGE}; padding: 4px 8px; selection-background-color: {DARK}; selection-color: #ffffff; }}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QKeySequenceEdit:focus {{
    border-color: {LAV}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url(ARROW_PNG); width: 10px; height: 6px; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 18px; background: {DEEP}; border: none; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url(UP_PNG); width: 10px; height: 6px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url(ARROW_PNG); width: 10px; height: 6px; }}
QComboBox QAbstractItemView {{ background: {PANEL}; color: {TEXT}; border: 3px solid {DARK};
                               selection-background-color: {DARK}; selection-color: #ffffff; outline: none; }}
QListWidget {{ background: {FIELD}; border: 3px solid {DEEP}; outline: none; padding: 4px; }}
QListWidget::item {{ padding: 4px 6px; }}
QListWidget::indicator {{ width: 14px; height: 14px; border: 3px solid {DEEP}; background: {FIELD}; }}
QListWidget::indicator:checked {{ background: {LAV}; border-color: {LIGHT}; image: url(CHECK_PNG); }}
QListWidget::item:selected {{ background: {DARK}; color: #ffffff; }}
QPushButton {{ background: {LAV}; color: {INK}; font-weight: bold; padding: 7px 14px;
               border: 3px solid {DARK}; border-top-color: {LIGHT}; border-left-color: {LIGHT};
               border-bottom-color: {DEEP}; border-right-color: {DEEP}; }}
QPushButton:hover {{ background: {LIGHT}; }}
QPushButton:pressed {{ border-top-color: {DEEP}; border-left-color: {DEEP}; border-bottom-color: {LIGHT};
                       border-right-color: {LIGHT}; padding: 8px 13px 6px 15px; }}
QPushButton#primary {{ background: {LAV}; color: {INK}; }}
QPushButton#primary:hover {{ background: {LIGHT}; }}
QPushButton#secondary {{ background: {SEC}; color: {TEXT}; border-top-color: {SEC_TOP}; border-left-color: {SEC_TOP};
                         border-bottom-color: {SEC_BOT}; border-right-color: {SEC_BOT}; }}
QPushButton#secondary:hover {{ background: {SEC_HOVER}; }}
QPushButton:disabled {{ background: {SEC}; color: {MUTED}; border-color: {SEC_TOP}; }}
QPushButton#chip {{ background: {PANEL}; color: {HEAD}; padding: 4px 10px; border: 3px solid {DEEP}; }}
QPushButton#chip:hover {{ background: {DEEP}; }}
QSlider::groove:horizontal {{ height: 8px; background: {FIELD}; border: 2px solid {DEEP}; }}
QSlider::sub-page:horizontal {{ background: {DARK}; }}
QSlider::handle:horizontal {{ width: 12px; background: {LIGHT}; border: 2px solid {INK}; margin: -5px 0; }}
QScrollBar:vertical {{ background: {BG}; width: 14px; border: none; }}
QScrollBar::handle:vertical {{ background: {DEEP}; min-height: 30px; border: 2px solid {BG}; }}
QScrollBar::handle:vertical:hover {{ background: {DARK}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QToolTip {{ background: {PANEL}; color: {TEXT}; border: 2px solid {LAV}; }}
"""


def _icon(name, pixels, size):
    path = os.path.join(HOME_DIR, "ui", f"{name}.png")
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        for x, y, c in pixels:
            img.putpixel((x, y), c)
        img.resize((size[0] * 2, size[1] * 2), Image.NEAREST).save(path)
    return path.replace(os.sep, "/")


def stylesheet():
    ink = (34, 22, 52, 255)
    arrow = ARROW
    tag = "d" if IS_DARK else "l"
    check = [(x, y, ink) for x, y in ((1, 4), (2, 5), (3, 6), (4, 5), (5, 4), (6, 3), (7, 2), (2, 4), (3, 5),
                                       (4, 4), (5, 3), (6, 2))]
    down = [(x, y, arrow) for y, row in enumerate(["#####", ".###.", "..#.."]) for x, c in enumerate(row) if c == "#"]
    up = [(x, 2 - y, c) for x, y, c in down]
    return (_style().replace("CHECK_PNG", _icon("check", check, (8, 8)))
            .replace("ARROW_PNG", _icon("down_" + tag, down, (5, 3)))
            .replace("UP_PNG", _icon("up_" + tag, up, (5, 3))))


class _NoWheel(QObject):
    """Dropdowns, number fields and sliders ignore the mouse wheel (no accidental changes);
    the wheel scrolls the page instead."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and isinstance(obj, (QComboBox, QAbstractSpinBox, QAbstractSlider)) \
                and not isinstance(obj, QScrollBar):
            w = obj.parent()
            while w is not None and not isinstance(w, QScrollArea):
                w = w.parent()
            if w is not None:
                QApplication.sendEvent(w.verticalScrollBar(), event)
            return True
        return False


_no_wheel = None

DARK_APP = f"""
QMenu {{ background: {PANEL}; color: {TEXT}; border: 3px solid {DARK}; border-top-color: {LAV};
         border-left-color: {LAV}; border-bottom-color: {DEEP}; border-right-color: {DEEP}; padding: 4px;
         font-weight: bold; }}
QMenu::item {{ padding: 5px 26px 5px 24px; background: transparent; }}
QMenu::item:selected {{ background: {DARK}; color: {TEXT}; }}
QMenu::item:disabled {{ color: {MUTED}; }}
QMenu::separator {{ height: 2px; background: {DEEP}; margin: 4px 8px; }}
QMenu::indicator {{ width: 12px; height: 12px; border: 2px solid {DEEP}; background: {FIELD}; margin-left: 4px; }}
QMenu::indicator:checked {{ background: {LAV}; border-color: {LIGHT}; }}
QToolTip {{ background: {PANEL}; color: {TEXT}; border: 2px solid {LAV}; }}
QDialog, QDialog QWidget {{ background: {BG}; color: {TEXT}; font-size: 13px; }}
QDialog QLineEdit, QDialog QComboBox, QDialog QSpinBox, QDialog QPlainTextEdit {{ background: {FIELD}; color: {TEXT};
    border: 3px solid {DEEP}; padding: 4px 8px; }}
QDialog QPushButton {{ background: {LAV}; color: {INK}; font-weight: bold; padding: 6px 14px; border: 3px solid {DARK}; }}
QDialog QPushButton:hover {{ background: {LIGHT}; }}
"""
_light = PALETTES[False]
LIGHT_APP = f"""
QMenu {{ background: {_light['PANEL']}; color: {INK}; border: 3px solid {DARK}; border-top-color: {LAV};
         border-left-color: {LAV}; border-bottom-color: {_light['DEEP']}; border-right-color: {_light['DEEP']};
         padding: 4px; font-weight: bold; }}
QMenu::item {{ padding: 5px 26px 5px 24px; background: transparent; }}
QMenu::item:selected {{ background: {LAV}; color: {INK}; }}
QMenu::item:disabled {{ color: {_light['MUTED']}; }}
QMenu::separator {{ height: 2px; background: #d9d2e8; margin: 4px 8px; }}
QMenu::indicator {{ width: 12px; height: 12px; border: 2px solid {DARK}; background: #ffffff; margin-left: 4px; }}
QMenu::indicator:checked {{ background: {LAV}; border-color: {_light['DEEP']}; }}
QToolTip {{ background: {_light['PANEL']}; color: {INK}; border: 2px solid {LAV}; }}
QDialog, QDialog QWidget {{ background: {_light['BG']}; color: {_light['TEXT']}; font-size: 13px; }}
QDialog QLineEdit, QDialog QComboBox, QDialog QSpinBox, QDialog QPlainTextEdit {{ background: #ffffff;
    color: {_light['TEXT']}; border: 3px solid {LAV}; padding: 4px 8px; }}
QDialog QPushButton {{ background: {LAV}; color: {INK}; font-weight: bold; padding: 6px 14px; border: 3px solid {DARK}; }}
QDialog QPushButton:hover {{ background: {_light['LIGHT']}; }}
"""
DARK_TITLES = False


def dark_titlebar(widget):
    """Dark window title bar (Windows 10/11)."""
    try:
        import ctypes
        import sys
        if sys.platform == "win32":
            on = ctypes.c_int(1 if DARK_TITLES else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(int(widget.winId()), 20, ctypes.byref(on), 4)
    except Exception:
        pass


def set_dark(on):
    """Switches the whole look: window palette, menus, tooltips, dialogs, title bars and the banners."""
    global DARK_TITLES, IS_DARK
    IS_DARK = DARK_TITLES = bool(on)
    globals().update(PALETTES[IS_DARK])
    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(DARK_APP if on else LIGHT_APP)
    for w in list(_themed):
        try:
            w.setStyleSheet(stylesheet())
            if w.windowTitle().startswith("Smellyfish") or w.isWindow():
                dark_titlebar(w)
        except RuntimeError:
            pass
    for label in list(_banners):
        try:
            _paint_banner(label)
            label.setStyleSheet(f"background: {PANEL}; border-bottom: 3px solid {DEEP}; padding: 4px;")
        except RuntimeError:
            pass
    for fn in list(_listeners):
        try:
            fn()
        except RuntimeError:
            pass


def apply(widget, app):
    global _no_wheel
    if _no_wheel is None and QApplication.instance() is not None:
        _no_wheel = _NoWheel()
        QApplication.instance().installEventFilter(_no_wheel)
    widget.setStyleSheet(stylesheet())
    widget.setWindowIcon(app.tray_icon())
    _themed.add(widget)
    if DARK_TITLES:
        dark_titlebar(widget)


def _pixel_text(text, color, scale=2):
    font = ImageFont.load_default_imagefont()
    pad = int(font.getlength(" "))
    box = font.getbbox(" " + text)
    img = Image.new("RGBA", (box[2] + 2, 13), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((1, 2), " " + text, font=font, fill=SHADOW)
    d.text((0, 1), " " + text, font=font, fill=color)
    img = img.crop((pad - 1, 0, img.width, 13))
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)


def banner_image(title, subtitle="", pose=None, extra=None, scale=3):
    """A pixel banner: the jellyfish on the left, a pixel title and subtitle on the right."""
    pet = sprite.render(pose or sprite.Pose(eyes="happy", blush=True), scale)
    if extra:
        pet = extra(pet)
    pet = pet.crop(pet.getbbox() or (0, 0, pet.width, pet.height))
    t = _pixel_text(title.upper(), TITLE, 3)
    s = _pixel_text(subtitle, SUB, 2) if subtitle else None
    h = max(pet.height, t.height + (s.height + 4 if s else 0)) + 16
    w = pet.width + 20 + max(t.width, s.width if s else 0) + 16
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    img.alpha_composite(pet, (8, (h - pet.height) // 2))
    tx = pet.width + 24
    ty = (h - t.height - (s.height + 4 if s else 0)) // 2
    img.alpha_composite(t, (tx, ty))
    if s:
        img.alpha_composite(s, (tx, ty + t.height + 4))
    return img


def _paint_banner(label):
    title, subtitle, pose = label.banner_args
    img = banner_image(title, subtitle, pose).convert("RGBA")
    q = QImage(img.tobytes("raw", "RGBA"), img.width, img.height, QImage.Format_RGBA8888).copy()
    label.setPixmap(QPixmap.fromImage(q))


def banner(title, subtitle="", pose=None):
    label = QLabel()
    label.banner_args = (title, subtitle, pose)
    _paint_banner(label)
    label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    label.setStyleSheet(f"background: {PANEL}; border-bottom: 3px solid {DEEP}; padding: 4px;")
    _banners.add(label)
    return label
