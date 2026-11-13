"""What a hook payload means for the pet: tool animations, agent names, permission and question bubbles."""

import re

TOOL_ANIM = {
    "Read": "search",
    "Grep": "search",
    "Glob": "search",
    "LS": "search",
    "NotebookRead": "search",
    "Bash": "terminal",
    "PowerShell": "terminal",
    "BashOutput": "terminal",
    "shell": "terminal",
    "local_shell": "terminal",
    "exec_command": "terminal",
    "WebFetch": "browse",
    "WebSearch": "browse",
    "web_search": "browse",
    "TodoWrite": "todo",
    "update_plan": "todo",
}


def tool_anim(name):
    name = name or ""
    if name in TOOL_ANIM:
        return TOOL_ANIM[name]
    if name.startswith("mcp__") and ("search" in name.lower() or "fetch" in name.lower()):
        return "browse"
    return "working"


AGENT_HOOKS = {
    "codex_hooks": "codex",
    "gemini_hooks": "gemini",
    "cursor_hooks": "cursor",
    "copilot_hooks": "copilot",
    "antigravity_hooks": "antigravity",
    "deepseek_hooks": "deepseek",
}


# badge pill per running session: short code and colour of the agent
AGENT_BADGE = {
    "claude": ("CL", (204, 120, 92)),
    "codex": ("CX", (70, 150, 130)),
    "gemini": ("GM", (80, 130, 225)),
    "cursor": ("CU", (112, 116, 132)),
    "copilot": ("CP", (130, 96, 200)),
    "antigravity": ("AG", (50, 160, 185)),
    "deepseek": ("DS", (78, 104, 214)),
}
AGENT_NAMES = {
    "claude": "Claude",
    "codex": "Codex",
    "gemini": "Gemini",
    "cursor": "Cursor",
    "copilot": "Copilot",
    "antigravity": "Antigravity",
    "deepseek": "DeepSeek",
}


def source_name(payload):
    return {
        "codex": "Codex",
        "gemini": "Gemini",
        "cursor": "Cursor",
        "copilot": "Copilot",
        "antigravity": "Antigravity",
        "deepseek": "DeepSeek",
    }.get(payload.get("_source"), "Claude")


def perm_spec(payload):
    tool = payload.get("tool_name") or "Tool"
    ti = payload.get("tool_input") or {}
    if tool in ("Bash", "PowerShell"):
        prompt, detail = "Run this command?", "$ " + str(ti.get("command", ""))
    elif tool == "apply_patch":
        files = re.findall(r"\*\*\* (?:Update|Add|Delete) File: (.+)", str(ti.get("command", "")))
        prompt, detail = "Change these files?", ", ".join(files) or str(ti.get("command", ""))[:400]
    elif tool in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        prompt, detail = "Change this file?", str(ti.get("file_path") or ti.get("notebook_path") or "")
    elif tool in ("WebFetch", "WebSearch"):
        prompt, detail = "Go online?", str(ti.get("url") or ti.get("query") or "")
    else:
        prompt = ti.get("description") or "Use this tool?"
        detail = ", ".join(f"{k}: {v}" for k, v in list(ti.items())[:4] if k != "description")[:400]
    short = tool.split("__")[-1] if tool.startswith("mcp__") else tool
    return {
        "kind": "perm",
        "tool": short,
        "prompt": prompt,
        "detail": detail,
        "right": source_name(payload),
        "can_always": bool(payload.get("permission_suggestions")),
    }


class Interactive:
    """A bubble that answers a blocked hook request."""

    def __init__(self, pending):
        self.pending = pending
        self.payload = pending.payload
        self.session = self.payload.get("session_id")
        self.is_ask = self.payload.get("hook_event_name") == "PreToolUse"
        self.questions = (self.payload.get("tool_input") or {}).get("questions") or []
        self.page = 0
        self.answers = {}
        self.picked = []
        self.expanded = False

    def spec(self):
        if not self.is_ask:
            s = perm_spec(self.payload)
        else:
            q = self.questions[self.page]
            s = {
                "kind": "ask",
                "header": q.get("header", ""),
                "question": q.get("question", ""),
                "page": f"{self.page + 1}/{len(self.questions)}",
                "options": [o.get("label", "?") for o in q.get("options", [])],
                "descs": [o.get("description", "") for o in q.get("options", [])],
                "multi": bool(q.get("multiSelect")),
                "picked": list(self.picked),
            }
        s["expanded"] = self.expanded
        return s
