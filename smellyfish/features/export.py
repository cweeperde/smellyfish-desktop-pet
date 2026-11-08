"""Exports of the to-do list and the reminders as Markdown or CSV."""
import csv
import io
import time


def _when(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else ""


def todos_markdown(todos, reminders):
    lines = [f"# Smellyfish to-do ({time.strftime('%Y-%m-%d')})", ""]
    open_items = [t for t in todos if not t["done"]]
    done = [t for t in todos if t["done"]]
    for title, items in (("Open", open_items), ("Done", done)):
        if not items:
            continue
        lines += [f"## {title}", ""]
        for t in items:
            due = f" (due {_when(t['due'])})" if t.get("due") and not t["done"] else ""
            lines.append(f"- [{'x' if t['done'] else ' '}] {t['text']}{due}")
        lines.append("")
    if reminders:
        lines += ["## Reminders", ""]
        for r in sorted(reminders, key=lambda r: r["due"]):
            lines.append(f"- {_when(r['due'])}: {r['text']}")
        lines.append("")
    if len(lines) == 2:
        lines.append("Nothing on the list.")
    return "\n".join(lines).rstrip() + "\n"


def todos_csv(todos, reminders):
    """Semicolon-separated so Excel in German and other European locales splits the columns."""
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\r\n")
    w.writerow(["Type", "Text", "Status", "Due", "Created", "Finished"])
    for t in todos:
        w.writerow(["To-do", t["text"], "done" if t["done"] else "open", _when(t.get("due")),
                    _when(t.get("created")), _when(t.get("done_at"))])
    for r in sorted(reminders, key=lambda r: r["due"]):
        w.writerow(["Reminder", r["text"], "pending", _when(r["due"]), "", ""])
    return out.getvalue()


def save(path, text):
    encoding = "utf-8-sig" if path.lower().endswith(".csv") else "utf-8"
    with open(path, "w", encoding=encoding, newline="") as f:
        f.write(text)
