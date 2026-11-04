"""Mood, statistics and achievements (all persisted in the settings)."""
import time

ACHIEVEMENTS = [
    ("first_task", "First task", "Claude or Codex finished a task", "tasks_done", 1),
    ("task_10", "Busy bee", "10 finished tasks", "tasks_done", 10),
    ("task_100", "Workhorse", "100 finished tasks", "tasks_done", 100),
    ("codex_first", "Polyglot", "Codex finished a task", "codex_done", 1),
    ("answers_10", "Good listener", "Answered 10 questions in a bubble", "answered", 10),
    ("snacks_10", "Well fed", "Fed 10 snacks", "snacks", 10),
    ("pokes_100", "Poke master", "Poked it 100 times", "pokes", 100),
    ("throws_25", "Frequent flyer", "Threw it 25 times", "throws", 25),
    ("plant_10", "Green thumb", "Watered the plant 10 times", "watered", 10),
    ("focus_5", "Deep work", "Finished 5 focus rounds", "focus_rounds", 5),
    ("climb_10", "Mountaineer", "Climbed 10 windows", "climbs", 10),
    ("fetch_20", "Good fetch", "Fetched the ball 20 times", "fetches", 20),
    ("photo_10", "Paparazzi", "Took 10 screenshots", "screenshots", 10),
    ("days_7", "Old friends", "Spent 7 days together", "days", 7),
    ("angry_1", "Oops", "Made it really angry", "angry", 1),
    ("night_owl", "Night owl", "Still working after 2 am", "night_owl", 1),
    ("tickle_10", "Giggles", "Tickled its tentacles 10 times", "tickles", 10),
    ("pet_10", "Head pats", "Petted it 10 times", "pets", 10),
    ("trash_1", "Clean desk", "Emptied the recycle bin", "trash_emptied", 1),
]


class Life:
    def __init__(self, cfg):
        self.cfg = cfg
        self.stats = dict(cfg.get("stats") or {})
        self.unlocked = dict(cfg.get("achievements") or {})
        self.mood = float(cfg.get("mood") if cfg.get("mood") is not None else 70)
        self.snack_times = []
        self._decay_from = float(cfg.get("mood_at") or time.time())
        self.decay()
        today = time.strftime("%Y-%m-%d")
        if self.stats.get("last_day") != today:
            self.stats["last_day"] = today
            self.stats["days"] = self.stats.get("days", 0) + 1
            self.save()

    def save(self):
        self.cfg["stats"] = self.stats
        self.cfg["achievements"] = self.unlocked
        self.cfg["mood"] = round(self.mood, 1)
        self.cfg["mood_at"] = self._decay_from
        self.cfg.save()

    def decay(self):
        """Mood slowly drops (1 point per 10 minutes) towards 20."""
        now = time.time()
        steps = int((now - self._decay_from) // 600)
        if steps > 0:
            self.mood = max(20.0, self.mood - steps)
            self._decay_from += steps * 600
            self.save()

    def change_mood(self, delta):
        self.mood = max(0.0, min(100.0, self.mood + delta))
        self.save()

    def bump(self, stat, n=1):
        """Count something; returns achievements that were just unlocked."""
        self.stats[stat] = self.stats.get(stat, 0) + n
        new = []
        for aid, title, desc, key, need in ACHIEVEMENTS:
            if aid not in self.unlocked and self.stats.get(key, 0) >= need:
                self.unlocked[aid] = time.time()
                new.append((title, desc))
        self.save()
        return new

    def feed(self):
        """True if it was hungry enough to enjoy the snack."""
        now = time.time()
        self.snack_times = [t for t in self.snack_times if now - t < 3600] + [now]
        enjoyed = len(self.snack_times) <= 5
        self.change_mood(15 if enjoyed else 2)
        return enjoyed

    def mood_label(self):
        m = self.mood
        return "happy" if m >= 75 else "content" if m >= 45 else "a bit sad" if m >= 25 else "sad"
