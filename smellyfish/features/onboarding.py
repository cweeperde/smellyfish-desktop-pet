"""The first-start tour: the pet explains the basics in its bubbles and asks the questions that set up the most
important settings. Answers are only collected while you go back and forth; nothing is changed or installed until
you confirm them on the last page."""

import sys

from PySide6.QtGui import QGuiApplication

from smellyfish import settings as cfg_mod
from smellyfish.integrations import install_hooks

INFO = ("hello", "basics", "badge")


def _screens():
    out = []
    for i, sc in enumerate(QGuiApplication.screens(), 1):
        g = sc.geometry()
        main = sc is QGuiApplication.primaryScreen()
        out.append((f"Screen {i}" + (" (main)" if main else ""), "primary" if main else f"{g.x()},{g.y()}"))
    return out


class Onboarding:
    def __init__(self, app, replay=False):
        self.app = app
        self.replay = replay
        self.steps = [
            "hello",
            "basics",
            "badge",
            "hooks",
            "statusline",
            "screen",
            "roam",
            "home",
            "weather",
            "units",
            "sounds",
            "autostart",
            "confirm",
        ]
        if len(QGuiApplication.screens()) < 2:
            self.steps.remove("screen")
        self.answers = {}
        self.city = ""
        self.i = 0

    # ------------------------------------------------------------ flow
    def start(self):
        self.i = 0
        self.show()

    def show(self, direction=1):
        while 0 <= self.i < len(self.steps):
            spec = self.spec(self.steps[self.i])
            if spec is not None:
                return self.app.set_info(self.decorate(spec), force=True)
            self.i += direction
        if self.i < 0:
            self.i = 0
            return self.show()
        self.finish(applied=False)

    def decorate(self, spec):
        step = self.steps[self.i]
        visible = [s for s in self.steps if s == step or self.spec(s) is not None]
        spec.update(
            kind="onboard",
            step=step,
            chip=spec.get("chip", "Hello!" if step == "hello" else "Setup"),
            right=f"{visible.index(step) + 1}/{len(visible)}",
        )
        chosen = self.answers.get(step)
        if chosen is not None:
            spec["buttons"] = [(label, value, value == ("onb", chosen)) for label, value, _p in spec["buttons"]]
        links = []
        if self.i > 0:
            links.append(("< Back", ("onb", "__back__")))
        if step not in ("hello", "confirm") and step not in INFO:
            links.append(("Next >", ("onb", "__next__")))
        if step != "confirm":
            links.append(("Cancel tour", ("onb", "skip")))
        spec["links"] = links
        spec["max_lines"] = 10
        return spec

    def answer(self, value):
        step = self.steps[self.i] if self.i < len(self.steps) else None
        if value == "skip":
            return self.finish(applied=False, skipped=True)
        if value == "__back__":
            self.i -= 1
            return self.show(direction=-1)
        if value == "__next__":
            self.i += 1
            return self.show()
        if step == "confirm":
            return self.finish(applied=value == "apply")
        if step == "weather" and value == "type":
            from PySide6.QtWidgets import QInputDialog

            text, ok = QInputDialog.getText(None, "Smellyfish - weather", "City (e.g. Berlin):", text=self.city)
            if not ok or not text.strip():
                return self.show()
            self.city = text.strip()[:80]
        if step not in INFO:
            self.answers[step] = value
        self.i += 1
        self.show()

    def finish(self, applied, skipped=False):
        app = self.app
        app.onboarding = None
        app.cfg.set("onboarded", True)
        if applied:
            self.apply()
            app.set_info(
                {
                    "kind": "done",
                    "chip": "All set",
                    "text": "Done! Everything else is in the settings. "
                    "To see the tour again: right-click > More > Show the tour.",
                    "buttons": [("Thanks!", "ok", True)],
                },
                force=True,
            )
            app.player.once("happy")
        elif skipped or self.answers:
            app.set_info(
                {
                    "kind": "wait",
                    "chip": "Okay!",
                    "text": "Nothing was changed. The tour is under right-click > More > Show the tour.",
                    "buttons": [("OK", "ok", True)],
                },
                force=True,
            )
        else:
            app.set_info(None, force=True)
        app.build_menu()

    # ------------------------------------------------------------ pages
    def spec(self, step):
        a = self.app
        b = lambda *items: [(label, ("onb", value), i == 0) for i, (label, value) in enumerate(items)]
        if step == "hello":
            return {
                "text": "Hi, I'm Smellyfish! I live on your desktop, keep an eye on Claude Code and your PC, "
                "and like a bit of company. Got a minute for a quick tour? It also sets up a few things, "
                "and nothing changes before you say so on the last page.",
                "buttons": b(("Let's go", "next"), ("Skip the tour", "skip")),
            }
        if step == "basics":
            return {
                "text": "Grab me with the mouse to carry me around, throw me if you must. Stroke my head to "
                "pet me, wiggle the cursor over my tentacles to tickle me. Right-click me for the menu.",
                "buttons": b(("Next", "next")),
            }
        if step == "badge":
            return {
                "text": "The little pills above me show timers, missed messages, appointments and what is "
                "playing. Hover over me to see them all, click a pill to open it. Every bubble has an x in "
                "the corner to close it.",
                "buttons": b(("Next", "next")),
            }
        if step == "hooks":
            if install_hooks.is_installed("user"):
                return None
            return {
                "text": "Should I show what Claude Code is doing, and let you answer its questions and "
                "permission requests in my bubbles? I would add hooks to Claude Code's user settings. "
                "You can remove them in my settings any time.",
                "buttons": b(("Yes, add the hooks", "yes"), ("No thanks", "no")),
            }
        if step == "statusline":
            hooks = self.answers.get("hooks") == "yes" or install_hooks.is_installed("user")
            if not hooks or install_hooks.statusline_state() is not None:
                return None
            return {
                "text": "Want to see your Claude usage limits too? For that I would set Claude Code's status "
                "line (you have none yet).",
                "buttons": b(("Yes", "yes"), ("No", "no")),
            }
        if step == "screen":
            return {"text": "Which screen should I live on?", "buttons": b(*_screens(), ("All of them", "all"))}
        if step == "roam":
            return {
                "text": "May I hop around by myself? I can also sit on your windows and climb them.",
                "buttons": b(
                    ("Yes, use the windows too", "windows"),
                    ("Only along the Dock" if sys.platform == "darwin" else "Only along the taskbar", "floor"),
                    ("Please stay where I am", "stay"),
                ),
            }
        if step == "home":
            return {
                "text": "Would you like me to have a little home: bed, lamp, plant and a sign? It sits at the "
                "bottom of the screen.",
                "buttons": b(("Yes, a home", "yes"), ("No furniture", "no")),
            }
        if step == "weather":
            if a.cfg.get("weather_place"):
                return None
            label = f"City: {self.city}" if self.city else "Enter a city..."
            return {
                "text": "I can dress for the weather and tell you what it's like outside. Which city should I "
                "check? Only the city name goes to the weather service (open-meteo.com).",
                "buttons": b((label, "type"), ("No weather", "no")),
            }
        if step == "units":
            if not a.cfg.get("weather_place") and not (self.answers.get("weather") == "type" and self.city):
                return None
            return {"text": "Celsius or Fahrenheit?", "buttons": b(("°C", "C"), ("°F", "F"))}
        if step == "sounds":
            return {
                "text": "How about sounds? Little noises when I play, and a chime when Claude is done or needs you.",
                "buttons": b(("All sounds", "all"), ("Only the chimes", "notify"), ("Silence", "none")),
            }
        if step == "autostart":
            if cfg_mod.autostart_enabled():
                return None
            when = "when you log in" if sys.platform == "darwin" else "together with Windows"
            return {"text": f"Should I start {when}?", "buttons": b(("Yes", "yes"), ("No", "no"))}
        if step == "confirm":
            return {
                "chip": "Check",
                "text": self.summary(),
                "buttons": b(("Apply", "apply"), ("Cancel, change nothing", "cancel")),
            }
        return None

    def summary(self):
        ans = self.answers
        names = {
            "hooks": {"yes": "add Claude Code hooks", "no": "no hooks"},
            "statusline": {"yes": "set the status line", "no": "no status line"},
            "roam": {
                "windows": "hop around and use windows",
                "floor": "hop along the Dock" if sys.platform == "darwin" else "hop along the taskbar",
                "stay": "stay in place",
            },
            "home": {"yes": "with a home", "no": "no furniture"},
            "units": {"C": "°C", "F": "°F"},
            "sounds": {"all": "all sounds", "notify": "only chimes", "none": "no sounds"},
            "autostart": {
                "yes": "start when you log in" if sys.platform == "darwin" else "start with Windows",
                "no": "no autostart",
            },
        }
        parts = []
        for step in ("hooks", "statusline", "screen", "roam", "home", "weather", "units", "sounds", "autostart"):
            v = ans.get(step)
            if v is None:
                continue
            if step == "screen":
                parts.append(
                    "screen: " + next((label for label, val in _screens() + [("all screens", "all")] if val == v), v)
                )
            elif step == "weather":
                parts.append(f"weather for {self.city}" if v == "type" and self.city else "no weather")
            else:
                parts.append(names[step].get(v, v))
        if not parts:
            return "You did not pick anything, so nothing will change. Apply to finish the tour."
        text = "I'll set this up: " + ", ".join(parts) + ". Go back to change something."
        if sys.platform == "darwin":
            text += (
                " A few extras need your OK in macOS first, so they start off: dancing on the beat, counting "
                "clicks, the Trash reminder and sitting on desktop icons. Switch them on in the settings any time."
            )
        return text

    def apply(self):
        a, ans = self.app, self.answers
        if "hooks" in ans:
            a.apply_setting("hooks", ans["hooks"] == "yes")
        if ans.get("statusline") == "yes":
            a.apply_setting("claude_statusline", True)
        if "screen" in ans:
            a.apply_setting("monitor", ans["screen"])
        if "roam" in ans:
            a.apply_setting("wander", ans["roam"] != "stay")
            a.apply_setting("sit_on_windows", ans["roam"] == "windows")
            a.apply_setting("window_hop", ans["roam"] == "windows")
        if "home" in ans:
            a.apply_setting("show_house", ans["home"] == "yes")
        if ans.get("weather") == "type" and self.city:
            a.apply_setting("weather_place", self.city)
            a.apply_setting("weather", True)
        if "units" in ans:
            a.apply_setting("temp_unit", ans["units"])
        if "sounds" in ans:
            a.apply_setting("sfx", ans["sounds"] == "all")
            a.apply_setting("talk_blips", ans["sounds"] == "all")
            a.apply_setting("sound_done", ans["sounds"] != "none")
        if ans.get("autostart") == "yes":
            a.apply_setting("autostart", True)
