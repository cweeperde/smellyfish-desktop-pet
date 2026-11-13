"""Release notes, newest first. Shown in the app after an update and used for the GitHub release texts.

Kinds: "new", "better", "fix".
"""

KINDS = {"new": "New", "better": "Improved", "fix": "Fixed"}

CHANGELOG = [
    {
        "version": "1.7.0",
        "date": "2026-11-13",
        "title": "Now on the Mac, more agents and new things to do",
        "items": [
            (
                "new",
                "Smellyfish runs on macOS 13 and newer (Apple silicon and Intel) and lives in the menu bar. Features "
                "that need a macOS permission start off and ask when you switch them on.",
            ),
            (
                "new",
                "Hooks for Gemini CLI, Cursor, GitHub Copilot, Antigravity and DeepSeek-TUI, next to Claude Code and "
                "Codex. Each one has its own switch under Settings > Agents & Hooks.",
            ),
            (
                "new",
                "With two or more agents running, the badge shows a small colored tag for each one. Click it to see "
                "which agent works in which folder and for how long.",
            ),
            (
                "new",
                "Right-click a file or folder for its details (size, dates, SHA-256) in a bubble, or to start a CLI "
                "agent in that folder. Off until you switch it on in the settings. On Windows 11 it is under Show "
                "more options, on macOS under Quick Actions.",
            ),
            (
                "new",
                "When Claude Code compacts its context, the jellyfish presses a pile of notes into a small brick.",
            ),
            (
                "new",
                "New idle actions: fishing, a ride on a skateboard and, late in the evening, a look through a "
                "telescope. The terminal and the browser each have a second pose.",
            ),
            (
                "new",
                "Weather knows thunderstorms, fog and wind now, and the weather bubble adds the felt temperature, "
                "today's low and high and the wind.",
            ),
            (
                "new",
                "Hats and accessories can be picked by hand (Settings > Look), independent of season and weather. "
                "New: bunny ears at Easter, a straw hat for the start of summer, a pumpkin on Halloween, and the "
                "colors Night, Lemon and Snow.",
            ),
            (
                "better",
                "The settings window has pages in a sidebar and a search field. The right-click menu is shorter.",
            ),
            (
                "better",
                "Long answer options in a question bubble wrap onto two lines instead of being cut off.",
            ),
            (
                "better",
                "Uses much less CPU while idle: listening for the beat no longer polls the sound output all the "
                "time and pauses when nothing is playing.",
            ),
            (
                "better",
                "Whether the PC is online is read from Windows instead of contacting outside servers. The Discord "
                "sign-in is stored encrypted for your Windows account.",
            ),
            (
                "better",
                "The dance, the giggle and the second laptop pose move more calmly. The click counter counts all "
                "clicks instead of per day.",
            ),
            (
                "fix",
                "The local hook server refuses requests from web pages. Agent settings files are written safely: "
                "the first backup is kept and a damaged file is left alone.",
            ),
            (
                "fix",
                "The music note in the badge no longer disappears when you move the mouse to it. Settings > Music "
                "decides whether it shows only while something plays, always, or never.",
            ),
            (
                "fix",
                "The animation tester sorts the new animations into their groups again.",
            ),
        ],
    },
    {
        "version": "1.6.0",
        "date": "2026-11-08",
        "title": "Calendar, music and a first-start tour",
        "items": [
            (
                "new",
                "Calendar with month, week and day views (Ctrl+Alt+F4 or right-click > Calendar). Add your own events, "
                "import .ics files or subscribe to a calendar link from Google, Outlook or iCloud. Events can repeat "
                "daily, weekly, monthly or yearly, and the jellyfish reminds you before they start.",
            ),
            (
                "new",
                "Removing an imported or subscribed calendar only removes its own events. Calendars can be "
                "exported as .ics, one at a time or all together. Each calendar gets its own color, picked from "
                "swatches, and entries show where an event takes place.",
            ),
            (
                "new",
                "To-dos with a due time and reminders show up in the calendar. The to-do list can be exported as "
                "Markdown or as CSV for Excel.",
            ),
            (
                "new",
                "Subscribed links work with university timetables too (for example HISinOne exports): weekly "
                "lectures, holidays without lectures and the end of the term come through.",
            ),
            (
                "new",
                "Music from Spotify, a browser or any other player that reports to Windows: a note in the badge "
                "while something plays. Click it for a bubble with play, pause and skip and a "
                "progress bar you can click or drag to jump around in the song; the right-click menu has the "
                "same controls.",
            ),
            (
                "new",
                "On the first start the jellyfish shows you around and asks a few setup questions in its bubbles: "
                "Claude Code hooks, screen, wandering, home, weather, sounds and autostart. You can go back and "
                "forth or cancel at any time, and nothing changes until you confirm on the last page. "
                "Right-click > More > Show the tour plays it again.",
            ),
            (
                "new",
                "Every bubble has a little x to close it, and bubbles that close by themselves stay about twice "
                "as long. Closing a Claude Code question hands it back to the terminal.",
            ),
            (
                "better",
                "Bubbles that arrive while another one is open wait their turn instead of replacing it. "
                "Reminders and appointments still come first, and the one they push aside comes back after.",
            ),
            ("better", "Buttons in bubbles sink in while you hold them, and bubbles always show the whole text."),
            (
                "new",
                "Mini mode: drag the jellyfish up or down along the screen edge, it remembers the height. Pull it "
                "away from the edge and it holds on for a moment, then lets go and hangs from your cursor.",
            ),
            (
                "new",
                "The tentacles trail behind when it hops or swims and settle back into shape after landing. "
                "Switch it off under Movement.",
            ),
            (
                "new",
                "Hops look like a jellyfish now: it contracts before pushing off and spreads its tentacles on the "
                "way down.",
            ),
            (
                "new",
                "New animations: floating, breathing, a startle, an appointment page, a second laptop pose, "
                "reading with a magnifier, bopping to music with headphones, and new versions of tickling, "
                "petting and the done celebration.",
            ),
            ("better", "The tea break is a coffee break now."),
            (
                "better",
                "Less predictable: idle actions and walks come at irregular times, recent actions are picked "
                "less often, and the jellyfish is livelier in the late morning and calmer in the evening.",
            ),
            (
                "better",
                "During long tasks it puts the laptop away now and then for a stretch or a cup of coffee. While "
                "music plays it switches between dancing and just wearing headphones.",
            ),
            (
                "better",
                "It reacts to the screen: a startle when you switch windows very fast, and a few hops after a "
                "window you drag across the screen.",
            ),
            (
                "better",
                "Speech bubbles point at the jellyfish even at the screen edge, sit clear of the badge and are "
                "narrower for short messages.",
            ),
            (
                "better",
                "Discord messages no longer pop up while the Discord window is open. Open Discord jumps "
                "straight to the message when Discord tells which channel it is in.",
            ),
            (
                "better",
                "New installs start without the furniture. Hop around by itself is now at the top of the "
                "right-click menu, Show detected edges moved to the settings.",
            ),
            (
                "better",
                "The click counter's day now ends at 4:00 instead of midnight, and an old copy of the settings "
                "can no longer lower counters or remove achievements.",
            ),
            ("fix", "The upside-down hang under windows is gone; it now always hangs from one tentacle."),
            (
                "better",
                "Buttons at the bottom of the settings and the calendar wrap onto a second line in a narrow "
                "window instead of being cut off. The animation tester sorts every animation into a category.",
            ),
            ("better", "The click counter in the badge has a mouse icon."),
            ("fix", "Headphones no longer flicker on and off when you click the jellyfish while music plays."),
            ("fix", "Clicking a lobby message no longer opens Discord."),
        ],
    },
    {
        "version": "1.5.1",
        "date": "2026-11-06",
        "title": "Contributors and licenses",
        "items": [
            (
                "new",
                "The About window shows contributors with their GitHub profile pictures. It asks GitHub only "
                "when you open it, and the window says so.",
            ),
            (
                "new",
                "A Licenses button in the About window lists the license of Smellyfish and of the "
                "open-source libraries it uses.",
            ),
            ("better", "Pull requests are welcome now. The license explains how contributions work."),
        ],
    },
    {
        "version": "1.5.0",
        "date": "2026-11-06",
        "title": "Playing Smellyfish",
        "items": [
            (
                "new",
                'Discord Rich Presence: friends see "Playing Smellyfish" with a little jellyfish, whether it is '
                "napping, out for a walk or watching Claude or Codex work, and a button to adopt their own. "
                "Switch it off under Music, games & Discord.",
            ),
            (
                "better",
                "The presence only shares short, generic lines. No project names, prompts, calls, music or "
                "anything else personal, and nothing leaves your PC except through your Discord app.",
            ),
        ],
    },
    {
        "version": "1.4.0",
        "date": "2026-11-05",
        "title": "Lobby, chat and a zap",
        "items": [
            (
                "new",
                "LAN lobby: create or join a lobby with a password, chat, send letters and let friends visit. "
                "They step out of a door in their own colors and outfit and hand over the "
                "letter. Everything is encrypted and has cooldowns. Nothing runs until you open a lobby.",
            ),
            (
                "new",
                "Optional chat with your own Ollama or llama.cpp model: answers appear in a speech bubble or "
                "a chat window (Ctrl+Alt+F3). The model loads when needed and unloads when idle.",
            ),
            ("new", "A cartoon electric shock with an X-ray skeleton when you plug in the charger."),
            (
                "new",
                "It now and then hangs upside down under a window, either with all tentacles or from just one, "
                "and sways a little. Switch it off under Movement.",
            ),
            (
                "better",
                "Timers, the click counter and other badges are bevelled, have small icons and only show "
                "up when something changes or when you point at the jellyfish.",
            ),
            (
                "better",
                "It prefers windows over desktop icons and no longer drops off an icon when Windows is slow to answer.",
            ),
            (
                "new",
                "Dark mode (Settings > Appearance): speech bubbles, the input bubble, menus, dialogs and title "
                "bars all go dark.",
            ),
            ("new", "The colour list in the settings shows a little jellyfish in each colour."),
            (
                "new",
                "A pixel input bubble next to the jellyfish for the local chat. It starts Ollama or "
                "llama.cpp in the background when needed and shows when the model is waking up.",
            ),
            (
                "better",
                "The right-click menu is reorganized: weather, to-do, reminders, focus, lobby and go home on top, "
                "the settings in a submenu, the rest under More.",
            ),
            (
                "new",
                "About window (right-click menu) with the creator and the GitHub contributors. The exe now carries "
                "its author and version in the file properties.",
            ),
            (
                "new",
                "Weather can use your current location (Windows location service) or, if you allow it, a rough "
                "position from your IP address.",
            ),
            ("new", "Code blocks in answers are drawn as code in the speech bubble."),
            (
                "new",
                "Advanced model settings (answer length, thinking, context size, creativity, memory) are tucked "
                "into a collapsible block. The chat has an Unload model button and explains common problems.",
            ),
            ("new", "Right-click > Play > Hang from a window, to see the upside-down hang on demand."),
            (
                "better",
                "Dark mode is on by default. The signpost at home is redrawn. Short reactions play slower so you can "
                "actually see them. Mouse and key clicks are only counted now and no longer animate.",
            ),
            (
                "fix",
                "Every desktop item (shortcuts, files, folders) can be sat on, not only icons with free space above.",
            ),
            (
                "fix",
                "Speech bubbles, badges and the input bubble stay fully on screen at every edge; the bubble tail "
                "flips to the other side when the jellyfish is near the right edge.",
            ),
            (
                "fix",
                "Jumps are aimed so the jellyfish lands on the target while falling. Before, high jumps could fly "
                "past a window or icon.",
            ),
            (
                "better",
                "Hanging under windows needs less free space and no longer fails because of windows in front. "
                "Identical overlapping windows are counted once.",
            ),
            (
                "better",
                "New lamp. The input bubble has a wide text field with the buttons underneath, the chat window "
                "too. The local model settings are collapsed by default.",
            ),
            (
                "better",
                "Every window now has a proper light and dark version (settings, lobby, chat, to-do, about, "
                "notes, banners) and switches instantly with the dark mode setting.",
            ),
            (
                "better",
                "The jellyfish dangles from one tentacle as often as it hangs by all of them. The settings "
                "page fits without cutting off the right column.",
            ),
            (
                "new",
                "While you are in a lobby the right-click menu offers Send letter and Visit someone with a quick "
                "picker. The Reply button on a letter now opens a letter to the sender.",
            ),
            (
                "fix",
                "A reply (or any letter or visit) sent during the cooldown is queued and goes out by itself when "
                "the cooldown is over, instead of being dropped.",
            ),
            (
                "fix",
                "An achievement bubble no longer covers a letter or message you have not read yet. It waits until "
                "the other bubble is gone.",
            ),
            (
                "new",
                "Lobby chat messages pop up in a speech bubble like Discord ones, with a mail animation and a badge.",
            ),
            (
                "better",
                "A visitor's name sits centred right above their head, hat or umbrella included. The lobby "
                "window shows the encryption status.",
            ),
            (
                "new",
                "Lobby owners can remove people (the owner has a little crown). The password is hidden by default "
                "with Show and Copy buttons, and it is only asked when you press Join.",
            ),
            ("new", "Lobbies check the Smellyfish version so everybody is compatible; the list shows each version."),
            (
                "fix",
                "Your own lobby password is used now (it needs at least 4 characters). Before, a short one was "
                "silently replaced by a random one.",
            ),
            (
                "fix",
                "Lobbies are announced on every network card, not just one, and the Refresh button asks hosts to "
                "answer right away. Before, a virtual adapter (WSL, VPN, Hyper-V) could swallow the announcement.",
            ),
            ("better", "The lobby window is simpler once you are inside and shows the address friends can type."),
            (
                "new",
                "Right-click > Play > Show detected edges draws the edges the jellyfish stands on (green windows, "
                "yellow desktop items) for 12 seconds, handy when something looks off.",
            ),
            ("better", "The lobby list has a Refresh button."),
            ("fix", "Models that think before answering (like Qwen) now answer instead of staying silent."),
            ("better", "Music only makes it dance now; the headset stays for Discord calls."),
            ("better", "The hanging pose keeps the scarf pointing down."),
        ],
    },
    {
        "version": "1.3.2",
        "date": "2026-11-05",
        "title": "What's new",
        "items": [
            (
                "new",
                "After an update the jellyfish tells you and shows what changed. You can open this window "
                "any time from the tray menu.",
            ),
            ("new", "Every GitHub release now comes with proper release notes."),
        ],
    },
    {
        "version": "1.3.1",
        "date": "2026-11-05",
        "title": "Cleaner restarts",
        "items": [
            (
                "fix",
                "After an update the new version now starts as a fresh app. Before, restarting from the "
                'update bubble could end in "parent process has different executable".',
            ),
        ],
    },
    {
        "version": "1.3.0",
        "date": "2026-11-05",
        "title": "To-do list and desktop icons",
        "items": [
            (
                "new",
                "To-do list: add tasks, tick them off, rename, drag to reorder and set a reminder "
                "(tray menu or Ctrl+Alt+F5). Due tasks pop up in a bubble with Done and Snooze.",
            ),
            (
                "new",
                "The jellyfish checks off a task with a little clipboard animation, cheers when the list is empty "
                "and mentions open tasks when you come back to your PC.",
            ),
            ("new", "Four new achievements for finished to-dos."),
            (
                "new",
                "It can sit on desktop icons, but only on ones with free space above, so it never covers another "
                "icon. It hops away when you reach for the icon. Switch it off under Movement.",
            ),
            ("better", "New scarf, sunglasses and seasonal hats (Santa, witch, party, Valentine)."),
            ("better", "Sunglasses also work in the side view."),
            ("fix", "Update check and weather now answer while the jellyfish is asleep or in do-not-disturb."),
        ],
    },
    {
        "version": "1.2.0",
        "date": "2026-11-05",
        "title": "Global mute",
        "items": [
            ("new", "Mute all sounds with one switch (settings and tray menu)."),
        ],
    },
    {
        "version": "1.1.0",
        "date": "2026-11-05",
        "title": "More polish and safer saving",
        "items": [
            ("new", "Questions that allow several answers can be answered in the bubble."),
            ("new", "Seven new idle animations: yo-yo, juggling, tea, handheld game, paper plane, bubble gum, doodle."),
            ("new", "Optional click and key press counter (only the number) and a break reminder after 75 minutes."),
            ("new", "Critical warning at 95 % of a usage limit, and a check for updates button in the settings."),
            ("new", "Settings are saved with Save and discarded with Cancel."),
            (
                "better",
                "Headset, headphones, focus band and sweat stay on during any activity; weather clothes "
                "go with them and work in the side view.",
            ),
            ("better", "Climbing uses both sides of a window and wanders in small tours."),
            ("better", "Pending questions keep priority over other sessions finishing."),
            ("better", "The mouse wheel no longer changes dropdowns, numbers or sliders by accident."),
            ("fix", "Only one Smellyfish runs per profile, so an old process can no longer write stale settings."),
            ("fix", "Settings saves are locked across processes and never fail silently."),
            ("fix", "Updates are only installed when GitHub publishes a matching SHA-256 digest."),
            ("fix", "Codex hooks run in PowerShell and cmd."),
        ],
    },
    {
        "version": "1.0.0",
        "date": "2026-11-04",
        "title": "First release",
        "items": [
            ("new", "A pixel-art jellyfish that sits on your windows, hops, climbs and goes home to its house."),
            (
                "new",
                "Tool animations for Claude Code and Codex, with questions and permission requests answered in "
                "a speech bubble.",
            ),
            ("new", "Task timer, done summaries, usage limit warnings and a badge for everything you missed."),
            (
                "new",
                "Reacts to your PC: CPU, battery, network, music, Discord calls, recycle bin and fullscreen games.",
            ),
            ("new", "Focus timer, reminders, weather, achievements and toys."),
            ("new", "Automatic updates from GitHub releases."),
        ],
    },
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
