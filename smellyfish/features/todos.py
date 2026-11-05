"""A personal to-do list (persisted in the settings) with optional due times."""
import time
import uuid

MAX_TEXT = 200


class Todos:
    def __init__(self, cfg):
        self.cfg = cfg
        self.items = [self._clean(t) for t in (cfg.get("todos") or []) if isinstance(t, dict) and t.get("text")]

    @staticmethod
    def _clean(t):
        return {"id": str(t.get("id") or uuid.uuid4().hex[:8]), "text": str(t["text"])[:MAX_TEXT],
                "done": bool(t.get("done")), "created": float(t.get("created") or time.time()),
                "due": float(t["due"]) if t.get("due") else None,
                "done_at": float(t["done_at"]) if t.get("done_at") else None,
                "notified": bool(t.get("notified"))}

    def save(self):
        self.cfg.set("todos", list(self.items))

    def get(self, tid):
        return next((t for t in self.items if t["id"] == tid), None)

    def add(self, text, due=None):
        text = " ".join(str(text).split())[:MAX_TEXT]
        if not text:
            return None
        item = self._clean({"text": text, "due": due})
        self.items.append(item)
        self.save()
        return item

    def edit(self, tid, text=None, due=False):
        t = self.get(tid)
        if not t:
            return
        if text is not None and text.strip():
            t["text"] = " ".join(text.split())[:MAX_TEXT]
        if due is not False:
            t["due"], t["notified"] = due, False
        self.save()

    def set_done(self, tid, done=True):
        t = self.get(tid)
        if not t or t["done"] == done:
            return False
        t["done"] = done
        t["done_at"] = time.time() if done else None
        self.save()
        return True

    def remove(self, tid):
        self.items = [t for t in self.items if t["id"] != tid]
        self.save()

    def clear_done(self):
        self.items = [t for t in self.items if not t["done"]]
        self.save()

    def reorder(self, ids):
        order = {i: n for n, i in enumerate(ids)}
        self.items.sort(key=lambda t: order.get(t["id"], len(order)))
        self.save()

    def snooze(self, tid, minutes=5):
        t = self.get(tid)
        if t:
            t["due"], t["notified"] = time.time() + minutes * 60, False
            self.save()

    def open_items(self):
        return [t for t in self.items if not t["done"]]

    def overdue(self, now=None):
        now = now or time.time()
        return [t for t in self.open_items() if t["due"] and t["due"] <= now]

    def take_due(self, now=None):
        """Open tasks whose time has come and that were not announced yet."""
        due = [t for t in self.overdue(now) if not t["notified"]]
        for t in due:
            t["notified"] = True
        if due:
            self.save()
        return due


def fmt_due(ts, now=None):
    now = now or time.time()
    lt, ln = time.localtime(ts), time.localtime(now)
    clock = time.strftime("%H:%M", lt)
    if lt[:3] == ln[:3]:
        return clock
    tomorrow = time.localtime(now + 86400)
    if lt[:3] == tomorrow[:3]:
        return "tomorrow " + clock
    return time.strftime("%d.%m. ", lt) + clock
