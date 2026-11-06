"""Statistics and achievements (persisted in the settings)."""
import time

ACHIEVEMENTS = [
    ("first_task", "First task", "Your AI agent finished a task", "tasks_done", 1),
    ("task_10", "Busy bee", "10 finished AI tasks", "tasks_done", 10),
    ("task_100", "Workhorse", "100 finished AI tasks", "tasks_done", 100),
    ("answers_10", "Good listener", "Answered 10 questions in a bubble", "answered", 10),
    ("days_7", "Old friends", "Spent 7 days together", "days", 7),
    ("days_30", "Best friends", "Spent 30 days together", "days", 30),
    ("pokes_100", "Poke master", "Poked it 100 times", "pokes", 100),
    ("pokes_500", "Boop overload", "Booped it 500 times. It remembers.", "pokes", 500),
    ("angry_1", "Oops", "Made it really angry", "angry", 1),
    ("dizzy_5", "Spin cycle", "Made it dizzy 5 times", "dizzy", 5),
    ("throws_25", "Frequent flyer", "Threw it 25 times", "throws", 25),
    ("yeet_1", "YEET", "Threw it really, really fast", "yeets", 1),
    ("fall_1", "Butterfingers", "Dropped it from way up high", "big_falls", 1),
    ("climb_10", "Mountaineer", "It climbed 10 windows", "climbs", 10),
    ("tickle_10", "Giggles", "Tickled its tentacles 10 times", "tickles", 10),
    ("tickle_50", "Tickle monster", "Tickled it 50 times. Please let it breathe.", "tickles", 50),
    ("pet_10", "Head pats", "Petted it 10 times", "pets", 10),
    ("snacks_10", "Well fed", "Fed 10 snacks", "snacks", 10),
    ("snacks_50", "Bottomless", "Fed 50 snacks. Where does it put them?", "snacks", 50),
    ("fetch_20", "Good fetch", "Fetched the ball 20 times", "fetches", 20),
    ("plant_10", "Green thumb", "Watered the plant 10 times", "watered", 10),
    ("weather_10", "Weather nerd", "Checked the weather 10 times", "weather_checks", 10),
    ("photo_10", "Paparazzi", "Took 10 screenshots", "screenshots", 10),
    ("trash_1", "Clean desk", "Emptied the recycle bin", "trash_emptied", 1),
    ("trash_5", "Neat freak", "Emptied the recycle bin 5 times", "trash_emptied", 5),
    ("focus_5", "Deep work", "Finished 5 focus rounds", "focus_rounds", 5),
    ("breaks_10", "Hydrated", "Took 10 breaks when it asked", "breaks", 10),
    ("todo_1", "Ticked off", "Finished your first to-do", "todos_done", 1),
    ("todo_25", "Getting things done", "Finished 25 to-dos", "todos_done", 25),
    ("todo_100", "Productivity wizard", "Finished 100 to-dos", "todos_done", 100),
    ("todo_clear_5", "Inbox zero", "Cleared your whole list 5 times", "todo_clears", 5),
    ("letter_1", "Mailbox", "Received your first letter", "letters", 1),
    ("letter_10", "Pen pal", "Received 10 letters", "letters", 10),
    ("night_owl", "Night owl", "Still at the computer after 2 am", "night_owl", 1),
    ("clicks_1k", "Warming up", "1,000 clicks and key presses", "clicks", 1000),
    ("clicks_100k", "Clicky fingers", "100,000 clicks and key presses", "clicks", 100000),
    ("clicks_day", "Keyboard warrior", "10,000 clicks and key presses in one day", "best_day_clicks", 10000),
]


class Life:
    def __init__(self, cfg):
        self.cfg = cfg
        self.stats = dict(cfg.get("stats") or {})
        self.unlocked = dict(cfg.get("achievements") or {})
        today = time.strftime("%Y-%m-%d")
        if self.stats.get("last_day") != today:
            self.stats["last_day"] = today
            self.stats["days"] = self.stats.get("days", 0) + 1
            self.save()

    def save(self):
        self.cfg["stats"] = self.stats
        self.cfg["achievements"] = self.unlocked
        self.cfg.save()

    def unlocked_count(self):
        known = {a[0] for a in ACHIEVEMENTS}
        return sum(1 for aid in self.unlocked if aid in known)

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
