"""Shared pixel-art look for all windows: bevelled panels, chunky buttons and pixel headers."""
import os

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QAbstractSlider, QAbstractSpinBox, QApplication, QComboBox, QLabel, QScrollArea, QScrollBar

from smellyfish.art import sprite
from smellyfish.paths import HOME_DIR

INK = "#221634"
BG = "#1d1828"
PANEL = "#2a2438"
FIELD = "#141019"
LAV = "#c492ec"
LIGHT = "#e2c0fa"
DARK = "#8c60be"
DEEP = "#5a3d80"
TEXT = "#f2ecfa"
MUTED = "#a898c0"

STYLE = f"""
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
QLabel#title {{ color: {LIGHT}; font-size: 15px; font-weight: bold; }}
QCheckBox {{ spacing: 10px; background: transparent; }}
QCheckBox:unchecked {{ color: {MUTED}; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 3px solid {DEEP}; background: {FIELD}; }}
QCheckBox::indicator:hover {{ border-color: {LAV}; }}
QCheckBox::indicator:checked {{ background: {LAV}; border-color: {LIGHT}; image: url(CHECK_PNG); }}
QComboBox, QSpinBox, QLineEdit, QKeySequenceEdit, QTextEdit, QPlainTextEdit {{
    background: {FIELD}; color: {TEXT}; border: 3px solid {DEEP}; border-top-color: #0a0810;
    border-left-color: #0a0810; padding: 4px 8px; selection-background-color: {DARK}; }}
QComboBox:focus, QSpinBox:focus, QLineEdit:focus, QKeySequenceEdit:focus {{ border-color: {LAV}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url(ARROW_PNG); width: 10px; height: 6px; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 18px; background: {DEEP}; border: none; }}
QSpinBox::up-arrow {{ image: url(UP_PNG); width: 10px; height: 6px; }}
QSpinBox::down-arrow {{ image: url(ARROW_PNG); width: 10px; height: 6px; }}
QComboBox QAbstractItemView {{ background: {PANEL}; border: 3px solid {DARK}; selection-background-color: {DARK};
                               outline: none; }}
QListWidget {{ background: {FIELD}; border: 3px solid {DEEP}; outline: none; padding: 4px; }}
QListWidget::item {{ padding: 4px 6px; }}
QListWidget::item:selected {{ background: {DARK}; color: {TEXT}; }}
QPushButton {{ background: {LAV}; color: {INK}; font-weight: bold; padding: 7px 14px;
               border: 3px solid {DARK}; border-top-color: {LIGHT}; border-left-color: {LIGHT};
               border-bottom-color: {DEEP}; border-right-color: {DEEP}; }}
QPushButton:hover {{ background: {LIGHT}; }}
QPushButton:pressed {{ border-top-color: {DEEP}; border-left-color: {DEEP}; border-bottom-color: {LIGHT};
                       border-right-color: {LIGHT}; padding: 8px 13px 6px 15px; }}
QPushButton#secondary {{ background: #3a3150; color: {TEXT}; border-top-color: #5a4d74; border-left-color: #5a4d74;
                         border-bottom-color: #141019; border-right-color: #141019; }}
QPushButton#secondary:hover {{ background: #4a3f66; }}
QPushButton#chip {{ background: {PANEL}; color: {LIGHT}; padding: 4px 10px; border: 3px solid {DEEP}; }}
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
    light = (226, 192, 250, 255)
    check = [(x, y, ink) for x, y in ((1, 4), (2, 5), (3, 6), (4, 5), (5, 4), (6, 3), (7, 2), (2, 4), (3, 5),
                                       (4, 4), (5, 3), (6, 2))]
    down = [(x, y, light) for y, row in enumerate(["#####", ".###.", "..#.."]) for x, c in enumerate(row) if c == "#"]
    up = [(x, 2 - y, c) for x, y, c in down]
    return (STYLE.replace("CHECK_PNG", _icon("check", check, (8, 8)))
            .replace("ARROW_PNG", _icon("down", down, (5, 3)))
            .replace("UP_PNG", _icon("up", up, (5, 3))))


class _NoWheel(QObject):
    """Dropdowns, number fields and sliders ignore the mouse wheel (no accidental changes);
    the wheel scrolls the page instead."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and isinstance(obj, (QComboBox, QAbstractSpinBox, QAbstractSlider))                 and not isinstance(obj, QScrollBar):
            w = obj.parent()
            while w is not None and not isinstance(w, QScrollArea):
                w = w.parent()
            if w is not None:
                QApplication.sendEvent(w.verticalScrollBar(), event)
            return True
        return False


_no_wheel = None


def apply(widget, app):
    global _no_wheel
    if _no_wheel is None and QApplication.instance() is not None:
        _no_wheel = _NoWheel()
        QApplication.instance().installEventFilter(_no_wheel)
    widget.setStyleSheet(stylesheet())
    widget.setWindowIcon(app.tray_icon())


def _pixel_text(text, color, scale=2):
    font = ImageFont.load_default_imagefont()
    w = font.getbbox(text)[2] + 2
    img = Image.new("RGBA", (w, 13), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((1, 2), text, font=font, fill=(34, 22, 52, 255))
    d.text((0, 1), text, font=font, fill=color)
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)


def banner_image(title, subtitle="", pose=None, extra=None, scale=3):
    """A pixel banner: the jellyfish on the left, a pixel title and subtitle on the right."""
    pet = sprite.render(pose or sprite.Pose(eyes="happy", blush=True), scale)
    if extra:
        pet = extra(pet)
    pet = pet.crop(pet.getbbox() or (0, 0, pet.width, pet.height))
    t = _pixel_text(title.upper(), (226, 192, 250, 255), 3)
    s = _pixel_text(subtitle, (168, 152, 192, 255), 2) if subtitle else None
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


def banner(title, subtitle="", pose=None):
    img = banner_image(title, subtitle, pose).convert("RGBA")
    q = QImage(img.tobytes("raw", "RGBA"), img.width, img.height, QImage.Format_RGBA8888).copy()
    label = QLabel()
    label.setPixmap(QPixmap.fromImage(q))
    label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    label.setStyleSheet(f"background: {PANEL}; border-bottom: 3px solid {DEEP}; padding: 4px;")
    return label
