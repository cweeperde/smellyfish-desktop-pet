"""Builds the app: dist/Smellyfish.exe (one portable file) on Windows, dist/Smellyfish.app and
dist/Smellyfish.dmg on macOS.

The fast hook relay is built separately (onedir) and packed into the app as relay.zip;
the app unpacks it next to the settings on first start, so the agents' hooks never have to wait
for the big app to start.
"""

import os
import plistlib
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
IS_MAC = sys.platform == "darwin"
BUNDLE_ID = "io.github.cweeperde.smellyfish"
MAC_MODULES = [
    "objc",
    "Foundation",
    "AppKit",
    "Quartz",
    "CoreFoundation",
    "ApplicationServices",
    "ScreenCaptureKit",
    "CoreMedia",
    "CoreLocation",
]


def pyinstaller(*args):
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", *args], cwd=ROOT, check=True)


def make_icon(path):
    b = sprite.BX, sprite.BY
    img = sprite.render(sprite.Pose(), 8).crop(((b[0] - 1) * 8, (b[1] - 2) * 8, (b[0] + 17) * 8, (b[1] + 16) * 8))
    side = max(img.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(img, ((side - img.width) // 2, (side - img.height) // 2))
    square = square.resize((256, 256), Image.NEAREST)
    if path.endswith(".icns"):
        square.resize((1024, 1024), Image.NEAREST).save(path, format="ICNS")
    else:
        square.save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    square.save(os.path.join(BUILD, "icon_preview.png"))


def make_version_file(path):
    """Windows file properties of the exe: author, product, version."""
    from smellyfish import REPO, __version__

    nums = tuple(int(p) for p in __version__.split(".")[:3]) + (0,)
    strings = {
        "CompanyName": "cweeper",
        "FileDescription": "Smellyfish - a pixel jellyfish desktop pet",
        "FileVersion": ".".join(map(str, nums)),
        "InternalName": "Smellyfish",
        "LegalCopyright": "Copyright (c) 2026 cweeper. All rights reserved.",
        "OriginalFilename": "Smellyfish.exe",
        "ProductName": "Smellyfish",
        "ProductVersion": __version__,
        "Comments": f"Created by cweeper - https://github.com/{REPO}",
    }
    items = ", ".join(f"StringStruct({k!r}, {v!r})" for k, v in strings.items())
    text = (
        f"VSVersionInfo(ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, "
        f"fileType=0x1, subtype=0x0, date=(0, 0)), kids=[StringFileInfo([StringTable('040904B0', [{items}])]), "
        "VarFileInfo([VarStruct('Translation', [1033, 1200])])])\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def zip_relay(relay_dist):
    relay_zip = os.path.join(BUILD, "relay.zip")
    src = os.path.join(relay_dist, "smellyfish-relay")
    with zipfile.ZipFile(relay_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, _, files in os.walk(src):
            for f in files:
                full = os.path.join(folder, f)
                z.write(full, os.path.relpath(full, src))
    return relay_zip


def mac_plist(app):
    """Menu bar app without a Dock icon, the macOS minimum and the texts macOS shows when it asks for access."""
    from smellyfish import __version__

    path = os.path.join(app, "Contents", "Info.plist")
    with open(path, "rb") as f:
        info = plistlib.load(f)
    info.update(
        {
            "CFBundleName": "Smellyfish",
            "CFBundleDisplayName": "Smellyfish",
            "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "LSUIElement": True,
            "LSMinimumSystemVersion": "13.0",
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "Copyright (c) 2026 cweeper. All rights reserved.",
            "NSAppleEventsUsageDescription": "Smellyfish asks Finder about the Trash and your desktop icons, and "
            "controls Spotify or Music when you press a button in its music bubble.",
            "NSLocationWhenInUseUsageDescription": "Smellyfish shows the weather where you are. Only the "
            "coordinates go to the weather service.",
            "NSLocationUsageDescription": "Smellyfish shows the weather where you are. Only the coordinates go to "
            "the weather service.",
            "NSLocalNetworkUsageDescription": "Smellyfish finds friends' jellyfish in your local network for the "
            "lobby, and can talk to a model server on your network.",
        }
    )
    with open(path, "wb") as f:
        plistlib.dump(info, f)


def sign(path):
    """Ad-hoc signature, or a stable one when SMELLYFISH_SIGN_ID names a code-signing identity in the keychain
    (macOS then keeps the granted permissions across updates)."""
    identity = os.environ.get("SMELLYFISH_SIGN_ID") or "-"
    subprocess.run(["codesign", "--force", "--deep", "--sign", identity, path], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", path], check=True)


def main_mac():
    os.makedirs(BUILD, exist_ok=True)
    icon = os.path.join(BUILD, "smellyfish.icns")
    make_icon(icon)
    arch = ["--target-architecture", os.environ["SMELLYFISH_MAC_ARCH"]] if os.environ.get("SMELLYFISH_MAC_ARCH") else []
    relay_dist = os.path.join(BUILD, "relay_dist")
    pyinstaller(
        "--onedir",
        "--console",
        "--name",
        "smellyfish-relay",
        *arch,
        "--distpath",
        relay_dist,
        "--workpath",
        os.path.join(BUILD, "relay_work"),
        "--specpath",
        BUILD,
        os.path.join(ROOT, "smellyfish", "integrations", "hook_relay.py"),
    )
    relay_zip = zip_relay(relay_dist)
    collect = []
    for mod in MAC_MODULES:
        collect += ["--collect-all", mod]
    pyinstaller(
        "--onedir",
        "--windowed",
        "--name",
        "Smellyfish",
        "--icon",
        icon,
        "--osx-bundle-identifier",
        BUNDLE_ID,
        *arch,
        "--add-data",
        f"{relay_zip}{os.pathsep}.",
        "--add-data",
        f"{os.path.join(ROOT, 'LICENSE')}{os.pathsep}.",
        "--add-data",
        f"{os.path.join(ROOT, 'THIRD_PARTY_NOTICES.txt')}{os.pathsep}.",
        *collect,
        "--collect-data",
        "dateutil",
        "--exclude-module",
        "tkinter",
        "--exclude-module",
        "matplotlib",
        "--exclude-module",
        "pytest",
        "--exclude-module",
        "_pytest",
        "--exclude-module",
        "winrt",
        "--exclude-module",
        "soundcard",
        "--paths",
        ROOT,
        "--distpath",
        DIST,
        "--workpath",
        os.path.join(BUILD, "main_work"),
        "--specpath",
        BUILD,
        os.path.join(ROOT, "smellyfish", "__main__.py"),
    )
    app = os.path.join(DIST, "Smellyfish.app")
    mac_plist(app)
    sign(app)
    stage = os.path.join(BUILD, "dmg")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    subprocess.run(["ditto", app, os.path.join(stage, "Smellyfish.app")], check=True)
    os.symlink("/Applications", os.path.join(stage, "Applications"))
    dmg = os.path.join(DIST, "Smellyfish.dmg")
    if os.path.exists(dmg):
        os.remove(dmg)
    subprocess.run(
        ["hdiutil", "create", "-volname", "Smellyfish", "-srcfolder", stage, "-ov", "-format", "UDZO", dmg],
        check=True,
    )
    print(f"built {dmg} ({os.path.getsize(dmg) / 1e6:.1f} MB)")


def main():
    if IS_MAC:
        return main_mac()
    os.makedirs(BUILD, exist_ok=True)
    version = os.path.join(BUILD, "version_info.txt")
    make_version_file(version)
    icon = os.path.join(BUILD, "smellyfish.ico")
    make_icon(icon)

    relay_dist = os.path.join(BUILD, "relay_dist")
    pyinstaller(
        "--onedir",
        "--console",
        "--name",
        "smellyfish-relay",
        "--icon",
        icon,
        "--version-file",
        version,
        "--distpath",
        relay_dist,
        "--workpath",
        os.path.join(BUILD, "relay_work"),
        "--specpath",
        BUILD,
        os.path.join(ROOT, "smellyfish", "integrations", "hook_relay.py"),
    )
    relay_zip = zip_relay(relay_dist)

    pyinstaller(
        "--onefile",
        "--noconsole",
        "--name",
        "Smellyfish",
        "--icon",
        icon,
        "--version-file",
        version,
        "--add-data",
        f"{relay_zip}{os.pathsep}.",
        "--add-data",
        f"{os.path.join(ROOT, 'LICENSE')}{os.pathsep}.",
        "--add-data",
        f"{os.path.join(ROOT, 'THIRD_PARTY_NOTICES.txt')}{os.pathsep}.",
        "--collect-all",
        "soundcard",
        "--collect-all",
        "winrt",
        "--collect-data",
        "dateutil",
        "--exclude-module",
        "tkinter",
        "--exclude-module",
        "matplotlib",
        "--exclude-module",
        "pytest",
        "--exclude-module",
        "_pytest",
        "--paths",
        ROOT,
        "--distpath",
        DIST,
        "--workpath",
        os.path.join(BUILD, "main_work"),
        "--specpath",
        BUILD,
        os.path.join(ROOT, "smellyfish", "__main__.py"),
    )
    exe = os.path.join(DIST, "Smellyfish.exe")
    print(f"built {exe} ({os.path.getsize(exe) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
