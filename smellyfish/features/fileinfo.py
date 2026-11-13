"""Details about a file or folder for the right-click "Details" entry. Everything stays on the PC."""

import datetime
import hashlib
import mimetypes
import os


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def when(ts):
    return datetime.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def folder_summary(path, limit=20000):
    files = folders = total = seen = 0
    biggest = []
    for root, dirs, names in os.walk(path):
        folders += len(dirs)
        for name in names:
            seen += 1
            if seen > limit:
                return files, folders, total, biggest, True
            try:
                size = os.path.getsize(os.path.join(root, name))
            except OSError:
                continue
            files += 1
            total += size
            biggest.append((size, name))
            biggest.sort(reverse=True)
            del biggest[3:]
    return files, folders, total, biggest, False


def describe(path, with_hash=True):
    """{'title', 'kind', 'text', 'hash'}; text is plain lines for the bubble."""
    name = os.path.basename(path.rstrip("\\/")) or path
    st = os.stat(path)
    lines = [f"Modified {when(st.st_mtime)}", f"Created {when(st.st_ctime)}"]
    if os.path.isdir(path):
        files, folders, total, biggest, cut = folder_summary(path)
        more = "+" if cut else ""
        head = [f"{files}{more} files, {folders} folders", f"Size {human(total)}{more}"]
        if biggest:
            head.append("Biggest: " + ", ".join(f"{n} ({human(s)})" for s, n in biggest))
        return {"title": name, "kind": "Folder", "text": "\n".join(head + lines), "hash": ""}
    ext = os.path.splitext(name)[1].lower()
    kind = mimetypes.guess_type(name)[0] or (ext[1:].upper() + " file" if ext else "File")
    head = [f"Type {kind}", f"Size {human(st.st_size)} ({st.st_size:,} bytes)"]
    digest = ""
    if with_hash:
        try:
            digest = sha256(path)
        except OSError:
            digest = ""
    if digest:
        lines.append(f"SHA-256 {digest[:32]}\n{digest[32:]}")
    return {"title": name, "kind": "File", "text": "\n".join(head + lines), "hash": digest}
