"""Release notes, newest first. Shown in the app after an update and used for the GitHub release texts.

Kinds: "new", "better", "fix".
"""
KINDS = {"new": "New", "better": "Improved", "fix": "Fixed"}

CHANGELOG = [
    {"version": "1.3.2", "date": "2026-11-05", "title": "What's new", "items": [
        ("new", "After an update the jellyfish tells you and shows what changed. You can open this window "
                "any time from the tray menu."),
        ("new", "Every GitHub release now comes with proper release notes."),
    ]},
    {"version": "1.3.1", "date": "2026-11-05", "title": "Cleaner restarts", "items": [
        ("fix", "After an update the new version now starts as a fresh app. Before, restarting from the "
                "update bubble could end in \"parent process has different executable\"."),
    ]},
    {"version": "1.3.0", "date": "2026-11-05", "title": "To-do list and desktop icons", "items": [
        ("new", "To-do list: add tasks, tick them off, rename, drag to reorder and set a reminder "
                "(tray menu or Ctrl+Alt+F5). Due tasks pop up in a bubble with Done and Snooze."),
        ("new", "The jellyfish checks off a task with a little clipboard animation, cheers when the list is empty "
                "and mentions open tasks when you come back to your PC."),
        ("new", "Four new achievements for finished to-dos."),
        ("new", "It can sit on desktop icons, but only on ones with free space above, so it never covers another "
                "icon. It hops away when you reach for the icon. Switch it off under Movement."),
        ("better", "New scarf, sunglasses and seasonal hats (Santa, witch, party, Valentine)."),
        ("better", "Sunglasses also work in the side view."),
        ("fix", "Update check and weather now answer while the jellyfish is asleep or in do-not-disturb."),
    ]},
    {"version": "1.2.0", "date": "2026-11-05", "title": "Global mute", "items": [
        ("new", "Mute all sounds with one switch (settings and tray menu)."),
    ]},
    {"version": "1.1.0", "date": "2026-11-05", "title": "More polish and safer saving", "items": [
        ("new", "Questions that allow several answers can be answered in the bubble."),
        ("new", "Seven new idle animations: yo-yo, juggling, tea, handheld game, paper plane, bubble gum, doodle."),
        ("new", "Optional click and key press counter (only the number) and a break reminder after 75 minutes."),
        ("new", "Critical warning at 95 % of a usage limit, and a check for updates button in the settings."),
        ("new", "Settings are saved with Save and discarded with Cancel."),
        ("better", "Headset, headphones, focus band and sweat stay on during any activity; weather clothes "
                   "go with them and work in the side view."),
        ("better", "Climbing uses both sides of a window and wanders in small tours."),
        ("better", "Pending questions keep priority over other sessions finishing."),
        ("better", "The mouse wheel no longer changes dropdowns, numbers or sliders by accident."),
        ("fix", "Only one Smellyfish runs per profile, so an old process can no longer write stale settings."),
        ("fix", "Settings saves are locked across processes and never fail silently."),
        ("fix", "Updates are only installed when GitHub publishes a matching SHA-256 digest."),
        ("fix", "Codex hooks run in PowerShell and cmd."),
    ]},
    {"version": "1.0.0", "date": "2026-11-04", "title": "First release", "items": [
        ("new", "A pixel-art jellyfish that sits on your windows, hops, climbs and goes home to its house."),
        ("new", "Tool animations for Claude Code and Codex, with questions and permission requests answered in "
                "a speech bubble."),
        ("new", "Task timer, done summaries, usage limit warnings and a badge for everything you missed."),
        ("new", "Reacts to your PC: CPU, battery, network, music, Discord calls, recycle bin and fullscreen games."),
        ("new", "Focus timer, reminders, weather, achievements and toys."),
        ("new", "Automatic updates from GitHub releases."),
    ]},
]


def entry(version):
    return next((e for e in CHANGELOG if e["version"] == str(version).lstrip("vV")), None)


def markdown(version):
    """GitHub release text for one version."""
    e = entry(version)
    if not e:
        return ""
    lines = [f"## {e['title']}", ""]
    for kind, label in KINDS.items():
        items = [t for k, t in e["items"] if k == kind]
        if items:
            lines += [f"### {label}"] + [f"- {t}" for t in items] + [""]
    return "\n".join(lines).rstrip() + "\n"


def since(old, new):
    """Entries newer than `old` up to and including `new`, newest first."""
    from smellyfish.updater import parse
    lo, hi = parse(old or "0"), parse(new)
    return [e for e in CHANGELOG if lo < parse(e["version"]) <= hi]
