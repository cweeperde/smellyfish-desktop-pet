"""Turns hook payloads of Gemini CLI, Cursor and GitHub Copilot into the Claude Code shape the app understands."""

AGENTS = ("gemini", "cursor", "copilot", "antigravity", "deepseek")

EVENTS = {
    "beforeagent": "UserPromptSubmit",
    "beforesubmitprompt": "UserPromptSubmit",
    "userpromptsubmitted": "UserPromptSubmit",
    "beforetool": "PreToolUse",
    "posttooluse": "PreToolUse",
    "afteragent": "Stop",
    "stop": "Stop",
    "agentstop": "Stop",
    "sessionend": "SessionEnd",
    "notification": "Notification",
    "preinvocation": "UserPromptSubmit",
    "message_submit": "UserPromptSubmit",
    "tool_call_after": "PreToolUse",
    "turn_end": "Stop",
    "session_end": "SessionEnd",
    "waiting_for_user": "Notification",
}

TOOLS = {
    "run_shell_command": "Bash",
    "shell": "Bash",
    "bash": "Bash",
    "powershell": "Bash",
    "terminal": "Bash",
    "read_file": "Read",
    "read_many_files": "Read",
    "read": "Read",
    "view": "Read",
    "list_directory": "Glob",
    "glob": "Glob",
    "ls": "Glob",
    "search_file_content": "Grep",
    "grep_search": "Grep",
    "grep": "Grep",
    "search": "Grep",
    "google_web_search": "WebSearch",
    "web_search": "WebSearch",
    "web_fetch": "WebFetch",
    "fetch": "WebFetch",
    "write_todos": "TodoWrite",
    "todo": "TodoWrite",
    "todowrite": "TodoWrite",
    "run_command": "Bash",
    "view_file": "Read",
    "find_by_name": "Glob",
    "list_dir": "Glob",
    "search_web": "WebSearch",
    "read_url_content": "WebFetch",
    "replace_file_content": "Edit",
    "multi_replace_file_content": "Edit",
    "write_to_file": "Write",
    "exec_shell": "Bash",
    "grep_files": "Grep",
    "fetch_url": "WebFetch",
    "todo_write": "TodoWrite",
    "edit_file": "Edit",
    "replace": "Edit",
    "edit": "Edit",
    "write_file": "Write",
    "write": "Write",
    "apply_patch": "Edit",
}


def _first(p, *keys):
    for k in keys:
        if p.get(k) is not None:
            return p[k]
    return None


def normalize(source, event, payload):
    """A Claude-shaped copy of the payload, or None when the event is of no interest."""
    if source not in AGENTS:
        return payload
    raw = str(event or payload.get("hook_event_name") or payload.get("hookEventName") or "")
    mapped = EVENTS.get(raw.lower())
    if mapped is None:
        return None
    out = dict(payload)
    sid = _first(payload, "session_id", "sessionId", "conversation_id", "conversationId")
    out["session_id"] = f"{source}:{sid or 'main'}"
    out["hook_event_name"] = mapped
    if raw.lower() == "preinvocation" and (payload.get("invocationNum") or 1) > 1:
        out["hook_event_name"] = mapped = "PostToolUse"
    call = payload.get("toolCall")
    tool = _first(payload, "tool_name", "toolName") or (call.get("name") if isinstance(call, dict) else None)
    if tool:
        out["tool_name"] = TOOLS.get(str(tool).lower(), str(tool))
    if mapped == "Stop":
        status = str(payload.get("status") or "").lower()
        if status == "aborted":
            out["hook_event_name"] = "Interrupt"
        elif status == "error" or payload.get("error"):
            out["hook_event_name"] = "StopFailure"
            out["error"] = "error"
        out["last_assistant_message"] = _first(
            payload, "prompt_response", "text", "response", "lastMessage", "message"
        ) or str(payload.get("error") or "")
    if mapped == "Notification":
        kind = str(_first(payload, "notification_type", "notificationType", "type") or "").lower()
        out["notification_type"] = (
            "permission_prompt"
            if "permission" in kind
            else "idle_prompt"
            if ("idle" in kind or "input" in kind)
            else kind
        )
        out["message"] = _first(payload, "message", "text") or ""
    return out
