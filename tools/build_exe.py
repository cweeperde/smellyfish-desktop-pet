"""Builds dist/Smellyfish.exe: one portable file for Windows.

The fast hook relay is built separately (onedir) and packed into the exe as relay.zip;
the app unpacks it to %APPDATA%\\Smellyfish\\relay on first start, so Claude Code / Codex
hooks never have to wait for the big single-file exe to unpack.
"""
import os
import shutil
import subprocess
import sys
import zipfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from smellyfish.art import sprite  # noqa: E402
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")


def pyinstaller(*args):
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", *args], cwd=ROOT, check=True)


def make_icon(path):
    b = sprite.BX, sprite.BY
    img = sprite.render(sprite.Pose(), 8).crop(((b[0] - 1) * 8, (b[1] - 2) * 8, (b[0] + 17) * 8, (b[1] + 16) * 8))
    side = max(img.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(img, ((side - img.width) // 2, (side - img.height) // 2))
    square = square.resize((256, 256), Image.NEAREST)
    square.save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    square.save(os.path.join(BUILD, "icon_preview.png"))


def main():
    os.makedirs(BUILD, exist_ok=True)
    icon = os.path.join(BUILD, "smellyfish.ico")
    make_icon(icon)

    relay_dist = os.path.join(BUILD, "relay_dist")
    pyinstaller("--onedir", "--console", "--name", "smellyfish-relay", "--icon", icon,
                "--distpath", relay_dist, "--workpath", os.path.join(BUILD, "relay_work"),
                "--specpath", BUILD, os.path.join(ROOT, "smellyfish", "integrations", "hook_relay.py"))
    relay_zip = os.path.join(BUILD, "relay.zip")
    src = os.path.join(relay_dist, "smellyfish-relay")
    with zipfile.ZipFile(relay_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, _, files in os.walk(src):
            for f in files:
                full = os.path.join(folder, f)
                z.write(full, os.path.relpath(full, src))

    pyinstaller("--onefile", "--noconsole", "--name", "Smellyfish", "--icon", icon,
                "--add-data", f"{relay_zip}{os.pathsep}.",
                "--collect-all", "soundcard",
                "--exclude-module", "tkinter", "--exclude-module", "matplotlib",
                "--paths", ROOT,
                "--distpath", DIST, "--workpath", os.path.join(BUILD, "main_work"),
                "--specpath", BUILD, os.path.join(ROOT, "smellyfish", "__main__.py"))
    exe = os.path.join(DIST, "Smellyfish.exe")
    print(f"built {exe} ({os.path.getsize(exe) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
