"""Finder right-click entries (Quick Actions) for files and folders on macOS.

Each entry is a small workflow in ~/Library/Services that runs the hook relay with "shell <action> <path>"; the relay
hands the request to the running pet over 127.0.0.1 and exits. Nothing outside ~/Library/Services is changed.
"""

import os
import plistlib
import shlex
import shutil
import subprocess
import uuid

from smellyfish import __version__, paths

SERVICES = os.path.join(os.path.expanduser("~"), "Library", "Services")
PREFIX = "Smellyfish - "
MARK = "smellyfish-quick-action"


def _workflows():
    try:
        return [n for n in os.listdir(SERVICES) if n.startswith(PREFIX) and n.endswith(".workflow")]
    except OSError:
        return []


def _script(action):
    exe, args = paths.relay_command()
    cmd = " ".join(shlex.quote(p) for p in [exe, *args, "shell", action])
    return f'# {MARK} {__version__}\nfor f in "$@"; do\n  {cmd} "$f"\ndone\n'


def _document(action):
    ids = [str(uuid.uuid4()).upper() for _ in range(3)]
    run = {
        "AMAccepts": {"Container": "List", "Optional": True, "Types": ["com.apple.cocoa.string"]},
        "AMActionVersion": "2.0.3",
        "AMApplication": ["Automator"],
        "AMParameterProperties": {
            "COMMAND_STRING": {},
            "CheckedForUserDefaultShell": {},
            "inputMethod": {},
            "shell": {},
            "source": {},
        },
        "AMProvides": {"Container": "List", "Types": ["com.apple.cocoa.string"]},
        "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
        "ActionName": "Run Shell Script",
        "ActionParameters": {
            "COMMAND_STRING": _script(action),
            "CheckedForUserDefaultShell": True,
            "inputMethod": 1,
            "shell": "/bin/zsh",
            "source": "",
        },
        "BundleIdentifier": "com.apple.RunShellScript",
        "CFBundleVersion": "2.0.3",
        "CanShowSelectedItemsWhenRun": False,
        "CanShowWhenRun": True,
        "Category": ["AMCategoryUtilities"],
        "Class Name": "RunShellScriptAction",
        "InputUUID": ids[0],
        "Keywords": ["Shell", "Script", "Command", "Run", "Unix"],
        "OutputUUID": ids[1],
        "UUID": ids[2],
        "UnlocalizedApplications": ["Automator"],
        "isViewVisible": 1,
        "location": "309.000000:253.000000",
        "nibPath": "/System/Library/Automator/Run Shell Script.action/Contents/Resources/Base.lproj/main.nib",
    }
    return {
        "AMApplicationBuild": "523",
        "AMApplicationVersion": "2.10",
        "AMDocumentVersion": "2",
        "actions": [{"action": run, "isViewVisible": 1}],
        "connectors": {},
        "workflowMetaData": {
            "applicationBundleIDsByPath": {},
            "applicationPaths": [],
            "inputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "outputTypeIdentifier": "com.apple.Automator.nothing",
            "presentationMode": 15,
            "processesInput": 0,
            "serviceApplicationBundleID": "com.apple.finder",
            "serviceApplicationPath": "/System/Library/CoreServices/Finder.app",
            "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject",
            "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
            "serviceProcessesInput": 0,
            "systemImageName": "NSActionTemplate",
            "useAutomaticInputType": 0,
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
        },
    }


def _write(title, action):
    root = os.path.join(SERVICES, f"{PREFIX}{title}.workflow", "Contents")
    os.makedirs(root, exist_ok=True)
    info = {
        "NSServices": [
            {
                "NSMenuItem": {"default": f"{PREFIX}{title}"},
                "NSMessage": "runWorkflowAsService",
                "NSRequiredContext": {"NSApplicationIdentifier": "com.apple.finder"},
                "NSSendFileTypes": ["public.item"],
            }
        ]
    }
    with open(os.path.join(root, "Info.plist"), "wb") as f:
        plistlib.dump(info, f)
    with open(os.path.join(root, "document.wflow"), "wb") as f:
        plistlib.dump(_document(action), f)


def _refresh_services():
    try:
        subprocess.run(["/System/Library/CoreServices/pbs", "-update"], capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        pass


def is_installed():
    return bool(_workflows())


def signature():
    from smellyfish.system import shellmenu

    return "|".join([paths.relay_command()[0], __version__] + [cmd for cmd, _ in shellmenu.installed_agents()])


def current():
    """The entries were written by this version for the CLIs installed now."""
    path = os.path.join(SERVICES, f"{PREFIX}Details.workflow", "Contents", "document.wflow")
    try:
        with open(path, "rb") as f:
            script = plistlib.load(f)["actions"][0]["action"]["ActionParameters"]["COMMAND_STRING"]
    except (OSError, KeyError, IndexError, ValueError):
        return False
    from smellyfish.system import shellmenu

    labels = {f"{PREFIX}Start {label} here.workflow" for _, label in shellmenu.installed_agents()}
    have = {n for n in _workflows() if n != f"{PREFIX}Details.workflow"}
    return f"{MARK} {__version__}" in script and paths.relay_command()[0] in script and labels == have


def apply(install=True):
    from smellyfish.system import shellmenu

    for name in _workflows():
        shutil.rmtree(os.path.join(SERVICES, name), ignore_errors=True)
    if install:
        _write("Details", "details")
        for cmd, label in shellmenu.installed_agents():
            _write(f"Start {label} here", "agent:" + cmd)
    _refresh_services()
    return True


def refresh():
    if not is_installed() or current():
        return False
    return apply(True)
