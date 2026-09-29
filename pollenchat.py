#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PollenChat v2.8.12 — Clean CLI chat client for PollinationsAI

Fixes in v2.8.12:
  - New [name] command to change your display name (it used to be asked only
    once, at first start). Names are NFC-normalised, limited to 24 display
    columns (CJK and emoji count as 2) and must not contain control,
    zero-width or combining characters (they break readline's cursor math).
  - Each user message now stores the name it was sent under (a "name" field
    in the session file). Older logs are filled from the "username" saved in
    the session file. [history], [search], [sessions] and [export] show these
    names, so a rename does not rewrite the past. [sessions] lists the name
    flow, e.g. "A → B". The "name" field is never sent to the API.
  - [load] no longer overwrites the current name with the one stored in the
    session file (the name is a user setting, not session data).
  - The first-start name prompt uses the same validation.

Fixes in v2.8.11:
  - [export] by exchange (question + answer): [export list], [export -1],
    [export -3:], [export 2:5], [export ::-1] with rev / bare / full flags.
    Indexes and slices follow Python (0 = oldest, -1 = latest, stop excluded).
    Long questions are shortened to head + tail with a note.
  - send_chat: HTTP errors now show the server's reason. New helper
    _server_error_text() reads the JSON "error" field (or the response body).
    5xx are reported as server-side problems, 429 keeps its rate-limit
    message, and other codes (402, 404, ...) get the reason appended.
  - Input prompt: the "user[session] :" prompt is now passed to input() via
    _read_input(prompt) so readline knows about it. It used to be printed
    separately, and line editing (Backspace to line start, Home, history
    redraw) erased it. On GNU readline the colour codes are marked as
    zero-width with 0x01/0x02 (_rl_safe) so long lines keep the correct
    cursor position. _ask() prompts ([model], [import], ...) go through
    _rl_safe() as well. Paste merging in _pending_lines() is unchanged.

Fixes in v2.8.10:
  - _truncate_at_turn now requires 2+ turn markers (outside ``` blocks)
    before truncating. This reduces false positives: a single role label
    like "AI:" or "User:" in definitions / examples / translation tables
    is no longer cut.  Note that text with 2+ labels (e.g. a translation
    table with both "User:" and "AI:") is still truncated — use batch mode
    or turn guard OFF for such content.
  - stream_response: when exactly one marker is seen during streaming,
    display is held back from that point onward until either (a) a second
    marker confirms a fake turn (truncate) or (b) the stream ends with only
    one marker (legitimate content — flush the held-back tail). This prevents
    the first fake "User:" line from appearing on screen before truncation.
  - Fixed: _find_turn_markers() now checks _turn_guard_enabled so guard OFF
    no longer truncates or holds back display in stream mode.
  - Turn guard now also ignores markers inside ``` code blocks.
  - Improved [guard] help text and toggle message to warn about false
    positives.

Fixes in v2.8.9:
  - Added _read_input() with multi-line paste detection (POSIX only).
    Pasted text with newlines is merged into a single message instead of
    being processed line-by-line, which caused unstoppable AI response loops.
  - Pasted multi-line text is never interpreted as commands (prevents pasted
    text containing bracketed words like [exit] from triggering commands).

Fixes in v2.8.8:
  - Default _stream_mode changed to False (batch) to avoid phantom input loops
    on browser-based terminals (Colab xterm.js, etc.)
  - Added sys.stdout.flush() guards around stream output and prompt input
  - HELP_TEXT warns that streaming may misbehave on web terminals

Fixes in v2.8.7:
  - Turn guard: truncate AI responses at fake User:/Assistant:/AI: markers
    to prevent free-tier models from generating phantom conversation turns
  - [guard] command to toggle turn guard (default: ON)

Fixes in v2.8.6:
  - Removed \001/\002 ANSI wrapping in _rl_prompt() to prevent readline/libedit
    from mis-handling prompts and causing phantom auto-input on some terminals

Fixes in v2.8.5:
  - [save]: assign _sessions[name] BEFORE _save_session_atomic() so the new file
    is no longer written with an empty (or stale) history
  - main prompt now goes through _ask() like every other prompt

Fixes in v2.8.4:
  - _rl_prompt() is now conditional: only wraps ANSI codes when readline is present
  - All colored input() prompts go through _rl_prompt() for consistent readline safety
  - [size] validates dimensions before assigning to _img_width/_img_height
  - [rename] skips os.remove() when old and new resolve to the same file
  - _sanitize_session_name strips trailing .json so keys stay consistent
  - [save] now uses _save_session_atomic() for crash-safe writes
  - stream_response hardened against non-list choices / non-dict delta

Fixes in v2.8.3:
  - _auto_load_all_sessions() moved after banner so broken-JSON warnings are visible
  - rename_session: save new session before removing old file (crash safety)
  - undo_last / clear_history: auto-save current session immediately
  - readline-safe ANSI prompt wrapper to prevent display glitches
  - stream_response: guard against non-dict JSON payloads
  - [save]: sanitize session name with _sanitize_session_name
  - [system]: empty-input guard with .strip()
  - [size]: validate dimensions at input time
  - HELP_TEXT: add missing em-dash for [model]

Fixes in v2.8.2:
  - [long] / [system] now use [end] terminator (empty lines are preserved)
  - [save] copy-on-write to avoid shared list references
  - [clear] resets _last_assistant_text so [render]/[savecode] don't see stale data
  - generate_image: quote(prompt, safe="") to handle slashes in prompts
  - Atomic per-session auto-save after every successful chat_once
  - _auto_load_all_sessions warns about broken JSON instead of silently skipping
  - batch_response / stream_response guard against malformed choices
  - Image size validation (64–4096)
  - Seed=0 is now handled correctly (0 is falsy but valid)
  - import_file: expand ~ and strip surrounding quotes from path
  - readline support on Unix for arrow-key editing
  - rename_session early-return when name is unchanged
  - estimate_tokens notes MAX_HISTORY limit
  - _prompt_float unused "current" argument removed

New features in v2.8:
  - Multi-session management: [sessions] [switch] [new] [rename] [delete]
  - Auto-load all sessions on startup, auto-save all on exit
  - Session name shown in the prompt

API Docs: https://github.com/pollinations/pollinations/blob/master/APIDOCS.md
"""

from __future__ import annotations

import os
import sys
import json
import re
import random
import unicodedata
import datetime
import requests
from typing import Optional
from urllib.parse import quote

from colorama import init, Fore, Style

init(autoreset=True)

# Enable line editing / history on Unix terminals
# (no effect on Windows without pyreadline, but harmless)
try:
    import readline  # noqa: F401
    # libedit (macOS) treats prompt markers differently: only GNU readline gets them
    _READLINE_GNU = "libedit" not in (readline.__doc__ or "")
except ImportError:
    _READLINE_GNU = False

# ============ CONFIG ============
API_BASE = "https://text.pollinations.ai/openai"
IMAGE_BASE = "https://image.pollinations.ai/prompt"
MODELS_URL = "https://text.pollinations.ai/models"

SESSION_DIR = "sessions"
IMAGE_DIR = "pollen_images"
CODE_DIR = "pollen_codes"
EXPORT_DIR = "pollen_exports"
CONFIG_FILE = "config.json"
MAX_HISTORY = 20
IMPORT_MAX_BYTES = 200_000

# Extension map for code block languages
LANG_EXT = {
    "python": ".py", "py": ".py",
    "javascript": ".js", "js": ".js",
    "typescript": ".ts", "ts": ".ts",
    "jsx": ".jsx", "tsx": ".tsx",
    "html": ".html", "css": ".css", "json": ".json",
    "bash": ".sh", "sh": ".sh", "shell": ".sh", "zsh": ".zsh",
    "cpp": ".cpp", "c++": ".cpp", "c": ".c",
    "go": ".go", "rust": ".rs", "rs": ".rs",
    "java": ".java", "kotlin": ".kt", "swift": ".swift",
    "ruby": ".rb", "rb": ".rb", "php": ".php",
    "sql": ".sql", "yaml": ".yaml", "yml": ".yml",
    "toml": ".toml", "xml": ".xml",
    "dockerfile": ".dockerfile", "docker": ".dockerfile",
    "makefile": ".mk", "cmake": ".cmake",
    "lua": ".lua", "r": ".r",
    "perl": ".pl", "pl": ".pl",
    "haskell": ".hs", "hs": ".hs",
    "scala": ".scala", "dart": ".dart",
    "julia": ".jl", "matlab": ".m",
    "vim": ".vim", "ini": ".ini", "cfg": ".cfg",
    "csv": ".csv", "markdown": ".md", "md": ".md",
    "tex": ".tex", "latex": ".tex",
}

# ============ BANNER ============
BANNER = r"""
    ____       __           ________          __
   / __ \_____/ /_____     / ____/ /_  ____ _/ /_
  / /_/ / ___/ //_/ _ \   / /   / __ \/ __ `/ __/
 / ____/ /__/ ,< /  __/  / /___/ / / / /_/ / /_
/_/    \___/_/|_|\___/   \____/_/ /_/\__,_/\__/
                                         v2.8.12
         Clean & Harmless — Powered by PollinationsAI
"""

# ============ STATE ============
_sessions: dict[str, list[dict[str, str]]] = {"default": []}
_current_session: str = "default"
_session_last_text: dict[str, str] = {}

current_model: str = "openai"
_system_prompt: str = "You are a helpful assistant."
_temperature: float = 0.7
_max_tokens: Optional[int] = None
_stream_mode: bool = False  # default batch mode: safer on browser terminals
_last_assistant_text: str = ""
_turn_guard_enabled: bool = False  # opt-in: stops AI from generating fake user/assistant turns

# Image mode defaults (not persisted in config)
_img_width: int = 1024
_img_height: int = 1024
_img_seed: Optional[int] = None

available_models: list[str] = []
username: str = "User"

# ============ UTILS ============
def clear() -> None:
    os.system("clear" if os.name == "posix" else "cls")

def ensure_dirs() -> None:
    os.makedirs(SESSION_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)
    os.makedirs(CODE_DIR, exist_ok=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)

def _safe_session_name(name: str) -> str:
    name = os.path.basename(name.strip())
    if not name:
        name = "session"
    return name if name.endswith(".json") else name + ".json"

def _safe_filename(name: str) -> str:
    name = os.path.basename(name.strip())
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name or "snippet"

def _sanitize_session_name(name: str) -> str:
    name = name.strip()
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    # Strip trailing .json so "foo.json" becomes "foo" and stays consistent
    if name.lower().endswith(".json"):
        name = name[:-5]
    return name or "untitled"

# Turn guard (opt-in via [guard]): some free-tier models keep generating fake
# User:/Assistant: turns. We truncate the response at the first marker when
# *two or more* such markers are found outside ``` code blocks. A single
# marker is treated as legitimate content (definitions, examples, etc.).
_TURN_RE = re.compile(
    r"\n[ \t]*(?:User|Assistant|AI)[ \t]*[:：]",
    re.IGNORECASE,
)
_TURN_WORDS = ("user", "assistant", "ai")


def _truncate_at_turn(text: str) -> str:
    """Truncate text at the first turn-marker if turn guard is enabled.

    To reduce false positives (e.g. definitions like "AI: artificial
    intelligence" or "User: 利用者"), we only truncate when *two or more*
    turn markers are found outside ``` code blocks. A single marker is
    treated as intentional content (definitions, examples, etc.).
    """
    if not _turn_guard_enabled:
        return text

    # Collect markers that are NOT inside ``` code blocks
    matches = []
    for m in _TURN_RE.finditer(text):
        backticks_before = text[: m.start()].count("```")
        if backticks_before % 2 == 0:  # outside code block
            matches.append(m)

    # Need 2+ markers to be confident it is a fake conversation turn sequence.
    # A lone marker is usually a definition, translation table, or example.
    if len(matches) < 2:
        return text

    first = matches[0]
    return text[: first.start()]


def _find_turn_markers(text: str) -> list[int]:
    """Return start positions of turn markers that are outside ``` blocks."""
    if not _turn_guard_enabled:
        return []
    positions = []
    for m in _TURN_RE.finditer(text):
        if text[: m.start()].count("```") % 2 == 0:
            positions.append(m.start())
    return positions


def _held_back_len(text: str) -> int:
    """Length of the tail that may be the start of a turn marker split across
    stream chunks (e.g. "\nUs" + "er:"). Streaming holds these back until the
    next chunk shows whether they really are a marker."""
    if not _turn_guard_enabled:
        return 0
    nl = text.rfind("\n")
    if nl == -1:
        return 0
    tail = text[nl + 1:].lstrip(" \t").lower()
    word = tail.rstrip(" \t")
    if word == "" or any(w.startswith(word) for w in _TURN_WORDS):
        return len(text) - nl
    return 0


def _pending_lines() -> list[str]:
    """Return extra lines already waiting on stdin (i.e. pasted text).

    Terminal paste is far faster than typing, so if more input arrives within
    0.1s of the previous line it is treated as part of the same paste.
    POSIX only: Windows select() does not support stdin, so nothing is
    detected there (Windows paste behaviour is less prone to this issue).
    """
    extra: list[str] = []
    if os.name != "posix":
        return extra
    import select
    try:
        while True:
            readable, _, _ = select.select([sys.stdin], [], [], 0.1)
            if sys.stdin not in readable:
                break
            try:
                extra.append(input())
            except EOFError:
                break
    except (OSError, ValueError):
        pass
    return extra


def _ask(prompt_text: str, multiline: bool = False) -> str:
    """Wrapper around input().

    Extra pasted lines are not left in the buffer (they would otherwise leak
    into the next prompt and be sent to the AI as separate messages). With
    multiline=True they are joined into the answer; otherwise they are
    discarded with a notice.
    """
    first = input(_rl_safe(prompt_text))
    extra = _pending_lines()
    if extra:
        if multiline:
            return "\n".join([first] + extra).strip()
        print(
            f"{Fore.YELLOW}[~] Ignored {len(extra)} extra pasted line(s); "
            f"only the first line was used.{Style.RESET_ALL}"
        )
    return first.strip()


def _rl_safe(prompt: str) -> str:
    """Mark ANSI colour codes in a prompt as zero-width for GNU readline.

    Without the 0x01 ... 0x02 markers readline counts the escape bytes as
    visible columns and mis-places the cursor on long lines.
    """
    if not _READLINE_GNU:
        return prompt
    return re.sub(r"(\x1b\[[0-9;]*m)", "\x01\\1\x02", prompt)


def _read_input(prompt: str = "") -> tuple[str, bool]:
    """Read input, detecting multi-line paste and merging into a single message.

    The prompt is passed to input() so that readline manages it (redraws keep it).

    When a user pastes multi-line text into a terminal, each line is fed to
    stdin separately. We detect this by checking if more lines arrive within a
    short timeout (0.1s) after the first line. Human typing is too slow to
    trigger this; only pasted text does.

    Returns:
        (text, is_paste): text is the merged input, is_paste is True if
        multiple lines were detected and merged.
    """
    lines = [input(prompt)] + _pending_lines()

    is_paste = len(lines) > 1
    if is_paste:
        print(
            f"{Fore.CYAN}[~] Detected {len(lines)} pasted lines; "
            f"merged into one message.{Style.RESET_ALL}"
        )

    return "\n".join(lines), is_paste

# ============ CONFIG ============
def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

def save_config(cfg: dict) -> None:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"{Fore.RED}[!] Config save failed: {e}{Style.RESET_ALL}")

def apply_config(cfg: dict) -> None:
    global current_model, _system_prompt, username, _stream_mode, _temperature, _max_tokens
    if "model" in cfg and isinstance(cfg["model"], str):
        current_model = cfg["model"]
    if "system_prompt" in cfg and isinstance(cfg["system_prompt"], str):
        _system_prompt = cfg["system_prompt"]
    if "username" in cfg and isinstance(cfg["username"], str):
        username = cfg["username"]
    if "stream_mode" in cfg and isinstance(cfg["stream_mode"], bool):
        _stream_mode = cfg["stream_mode"]
    if "temperature" in cfg and isinstance(cfg["temperature"], (int, float)):
        _temperature = float(cfg["temperature"])
    if "max_tokens" in cfg:
        if cfg["max_tokens"] is None:
            _max_tokens = None
        elif isinstance(cfg["max_tokens"], int) and not isinstance(cfg["max_tokens"], bool):
            _max_tokens = cfg["max_tokens"]

def build_config() -> dict:
    return {
        "model": current_model,
        "system_prompt": _system_prompt,
        "username": username,
        "stream_mode": _stream_mode,
        "temperature": _temperature,
        "max_tokens": _max_tokens,
    }

# ============ MARKDOWN RENDERER ============
def render_markdown(text: str) -> str:
    result = []
    in_code_block = False

    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\n\r")

        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            if in_code_block:
                lang = line.strip()[3:].strip()
                result.append(f"{Fore.CYAN}▶ {lang if lang else 'code'}{Style.RESET_ALL}\n")
            else:
                result.append(f"{Fore.CYAN}◀{Style.RESET_ALL}\n")
            continue

        if in_code_block:
            result.append(f"{Fore.LIGHTBLACK_EX}{line}{Style.RESET_ALL}\n")
            continue

        header_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if header_match:
            level = len(header_match.group(1))
            colors = [Fore.RED, Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.MAGENTA, Fore.WHITE]
            color = colors[level - 1] if level <= len(colors) else Fore.WHITE
            result.append(f"{color}{Style.BRIGHT}{line}{Style.RESET_ALL}\n")
            continue

        formatted = line
        formatted = re.sub(
            r"\*\*(.+?)\*\*",
            lambda m: f"{Style.BRIGHT}{Fore.WHITE}{m.group(1)}{Style.RESET_ALL}",
            formatted,
        )
        formatted = re.sub(
            r"`([^`]+)`",
            lambda m: f"{Fore.LIGHTBLACK_EX}{m.group(1)}{Style.RESET_ALL}",
            formatted,
        )
        result.append(f"{formatted}\n")

    return "".join(result).rstrip("\n")

# ============ MODELS ============
def _extract_model_name(item: str | dict) -> Optional[str]:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("name", "id", "model"):
            val = item.get(key)
            if isinstance(val, str):
                return val
    return None

def fetch_models() -> None:
    global available_models
    try:
        r = requests.get(MODELS_URL, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                names = [_extract_model_name(m) for m in data]
                available_models = [n for n in names if n is not None]
            else:
                available_models = []
        else:
            available_models = []
    except Exception as e:
        print(f"{Fore.YELLOW}[!] Could not fetch models ({e}); using defaults.{Style.RESET_ALL}")
        available_models = []

    if not available_models:
        available_models = [
            "openai", "mistral", "llama", "claude",
            "gemini", "deepseek", "qwen",
        ]

def select_model() -> None:
    global current_model
    print(f"\n{Fore.YELLOW}Available models:{Style.RESET_ALL}")
    for i, m in enumerate(available_models, 1):
        marker = f"{Fore.GREEN}*{Style.RESET_ALL}" if m == current_model else " "
        print(f"  [{marker}] {i}. {m}")

    choice = _ask(
        f"\n{Fore.CYAN}[+] Select model (number or name, Enter to keep {current_model}): {Style.RESET_ALL}"
    )
    if not choice:
        return

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(available_models):
            current_model = available_models[idx]
        else:
            print(f"{Fore.RED}[!] Invalid number.{Style.RESET_ALL}")
            return
    else:
        current_model = choice

    print(f"{Fore.GREEN}[OK] Model set to: {current_model}{Style.RESET_ALL}")
    save_config(build_config())

# ============ SYSTEM PROMPT ============
def set_system_prompt() -> None:
    global _system_prompt
    print(f"\n{Fore.YELLOW}Current system prompt:{Style.RESET_ALL}")
    print(f"  {_system_prompt}\n")
    print(
        f"{Fore.CYAN}Enter new prompt. "
        f"Type [end] to finish, [reset] for default:{Style.RESET_ALL}"
    )
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "[reset]":
            _system_prompt = "You are a helpful assistant."
            print(f"{Fore.GREEN}[OK] System prompt reset to default.{Style.RESET_ALL}")
            save_config(build_config())
            return
        if line.strip() == "[end]":
            break
        lines.append(line)
    joined = "\n".join(lines).strip()
    if joined:
        _system_prompt = joined
        print(f"{Fore.GREEN}[OK] System prompt updated.{Style.RESET_ALL}")
        save_config(build_config())
    else:
        print(f"{Fore.YELLOW}[~] Kept current prompt.{Style.RESET_ALL}")

# ============ CONFIG (temperature / max_tokens) ============
def _prompt_float(prompt_text: str, min_val: float, max_val: float) -> Optional[float]:
    while True:
        raw = _ask(prompt_text)
        if raw == "":
            return None
        try:
            val = float(raw)
        except ValueError:
            print(f"{Fore.RED}[!] Please enter a number.{Style.RESET_ALL}")
            continue
        if not (min_val <= val <= max_val):
            print(f"{Fore.RED}[!] Value must be between {min_val} and {max_val}.{Style.RESET_ALL}")
            continue
        return val

def _prompt_optional_int(prompt_text: str) -> Optional[int]:
    while True:
        raw = _ask(prompt_text).lower()
        if raw == "":
            return None
        if raw == "none":
            return -1
        try:
            val = int(raw)
        except ValueError:
            print(f"{Fore.RED}[!] Please enter a positive integer or 'none'.{Style.RESET_ALL}")
            continue
        if val < 1:
            print(f"{Fore.RED}[!] Must be at least 1.{Style.RESET_ALL}")
            continue
        return val

def edit_config() -> None:
    global _temperature, _max_tokens
    print(f"\n{Fore.YELLOW}Current configuration:{Style.RESET_ALL}")
    print(f"  temperature : {_temperature}")
    mt = str(_max_tokens) if _max_tokens is not None else "(unset / server default)"
    print(f"  max_tokens  : {mt}\n")

    new_temp = _prompt_float(
        f"{Fore.CYAN}[+] temperature (current: {_temperature}, Enter=keep, 0.0-2.0): {Style.RESET_ALL}",
        0.0, 2.0,
    )
    if new_temp is not None:
        _temperature = round(new_temp, 2)
        print(f"{Fore.GREEN}[OK] temperature set to {_temperature}{Style.RESET_ALL}")

    new_mt = _prompt_optional_int(
        f"{Fore.CYAN}[+] max_tokens (current: {mt}, Enter=keep, 'none'=unset): {Style.RESET_ALL}"
    )
    if new_mt == -1:
        _max_tokens = None
        print(f"{Fore.GREEN}[OK] max_tokens unset (server default){Style.RESET_ALL}")
    elif new_mt is not None:
        _max_tokens = new_mt
        print(f"{Fore.GREEN}[OK] max_tokens set to {_max_tokens}{Style.RESET_ALL}")

    save_config(build_config())

# ============ STREAM / TURN GUARD TOGGLE ============
def toggle_stream() -> None:
    global _stream_mode
    _stream_mode = not _stream_mode
    status = "ON (streaming)" if _stream_mode else "OFF (batch)"
    print(f"{Fore.GREEN}[OK] Streaming mode: {status}{Style.RESET_ALL}")
    save_config(build_config())


def toggle_turn_guard() -> None:
    global _turn_guard_enabled
    _turn_guard_enabled = not _turn_guard_enabled
    status = "ON" if _turn_guard_enabled else "OFF"
    print(f"{Fore.GREEN}[OK] Turn guard: {status}{Style.RESET_ALL}")
    if _turn_guard_enabled:
        print(
            f"{Fore.YELLOW}    Note: May still cut legitimate text that contains "
            f"multiple User:/Assistant:/AI: labels (e.g. definitions, "
            f"translation tables). Use with care.{Style.RESET_ALL}"
        )

# ============ USER NAME ============
NAME_MAX_WIDTH = 24  # display columns (CJK and emoji count as 2)


def _display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _validate_username(raw: str) -> tuple[Optional[str], Optional[str]]:
    """Normalise and check a display name. Returns (name, error)."""
    name = " ".join(unicodedata.normalize("NFC", raw).split())
    if not name:
        return None, "Name cannot be empty."
    for ch in name:
        cat = unicodedata.category(ch)
        if cat[0] == "C" or cat in ("Mn", "Me"):
            return None, (
                f"Unsupported character U+{ord(ch):04X} "
                "(control, zero-width and combining characters are not allowed)."
            )
    if _display_width(name) > NAME_MAX_WIDTH:
        return None, (
            f"Name is too long (max {NAME_MAX_WIDTH} columns; CJK and emoji count as 2)."
        )
    return name, None


def _msg_name(msg: dict) -> str:
    """Name a user message was sent under (falls back to the current name)."""
    n = msg.get("name")
    return n if isinstance(n, str) and n else username


def _stamp_names(history: list[dict], fallback: object) -> None:
    """Give user messages without a stored name the name saved in the session file."""
    fb = fallback if isinstance(fallback, str) and fallback else ""
    for msg in history:
        if msg["role"] != "user":
            continue
        n = msg.get("name")
        if isinstance(n, str) and n:
            continue
        if fb:
            msg["name"] = fb
        else:
            msg.pop("name", None)


def _name_flow(history: list[dict]) -> list[str]:
    """Names used by user messages in order, consecutive duplicates merged."""
    flow: list[str] = []
    for msg in history:
        if msg["role"] == "user":
            n = _msg_name(msg)
            if not flow or flow[-1] != n:
                flow.append(n)
    return flow


def _past_names() -> list[str]:
    seen: list[str] = []
    for sname in sorted(_sessions):
        for n in _name_flow(_sessions[sname]):
            if n not in seen:
                seen.append(n)
    return seen


def set_username() -> None:
    global username
    print(f"\n{Fore.YELLOW}Current name:{Style.RESET_ALL} {username}")
    others = [n for n in _past_names() if n != username]
    if others:
        print(f"{Fore.YELLOW}Also found in saved logs:{Style.RESET_ALL} {', '.join(others)}")
    print("  (Past messages keep the name they were sent with.)")
    raw = _ask(f"{Fore.CYAN}[+] New name (Enter to keep '{username}'): {Style.RESET_ALL}")
    if not raw:
        print(f"{Fore.YELLOW}[~] Kept current name.{Style.RESET_ALL}")
        return
    name, err = _validate_username(raw)
    if err or name is None:
        print(f"{Fore.RED}[!] {err}{Style.RESET_ALL}")
        return
    if name == username:
        print(f"{Fore.YELLOW}[~] Same name. No change.{Style.RESET_ALL}")
        return
    old, username = username, name
    save_config(build_config())
    print(f"{Fore.GREEN}[OK] Name changed: '{old}' → '{name}'{Style.RESET_ALL}")

# ============ SESSION MANAGEMENT (multi-session) ============
def _valid_history(history: object) -> bool:
    if not isinstance(history, list):
        return False
    for msg in history:
        if not isinstance(msg, dict):
            return False
        if msg.get("role") not in ("user", "assistant"):
            return False
        if not isinstance(msg.get("content"), str):
            return False
    return True

def _save_session_atomic(name: str) -> None:
    """Save a single session atomically (write to temp, then rename)."""
    history = _sessions.get(name, [])
    fname = _safe_session_name(name)
    tmp_path = os.path.join(SESSION_DIR, f".{fname}.tmp")
    path = os.path.join(SESSION_DIR, fname)
    data = {
        "model": current_model,
        "username": username,
        "system_prompt": _system_prompt,
        "temperature": _temperature,
        "max_tokens": _max_tokens,
        "history": history,
        "saved_at": datetime.datetime.now().isoformat(),
    }
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except OSError as e:
        print(f"{Fore.RED}[!] Failed to save '{name}': {e}{Style.RESET_ALL}")

def _auto_load_all_sessions() -> None:
    global _sessions, _current_session
    _sessions = {}
    files = sorted(f for f in os.listdir(SESSION_DIR) if f.endswith(".json"))
    loaded_any = False
    for fname in files:
        path = os.path.join(SESSION_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            history = data.get("history", []) if isinstance(data, dict) else []
            if _valid_history(history):
                _stamp_names(history, data.get("username") if isinstance(data, dict) else None)
                name = fname[:-5]
                _sessions[name] = history
                loaded_any = True
            else:
                print(
                    f"{Fore.YELLOW}[!] Skipped '{fname}': invalid history format.{Style.RESET_ALL}"
                )
        except json.JSONDecodeError as e:
            print(
                f"{Fore.YELLOW}[!] Skipped '{fname}': JSON error ({e}).{Style.RESET_ALL}"
            )
        except Exception as e:
            print(f"{Fore.YELLOW}[!] Skipped '{fname}': {e}.{Style.RESET_ALL}")
    if not loaded_any:
        _sessions = {"default": []}
        _current_session = "default"
    else:
        if "default" in _sessions:
            _current_session = "default"
        else:
            _current_session = sorted(_sessions.keys())[0]

def _auto_save_all_sessions() -> None:
    for name in _sessions:
        _save_session_atomic(name)

def list_sessions() -> None:
    print(f"\n{Fore.YELLOW}Sessions:{Style.RESET_ALL}")
    for i, name in enumerate(sorted(_sessions.keys()), 1):
        marker = f"{Fore.GREEN}*{Style.RESET_ALL}" if name == _current_session else " "
        count = len(_sessions[name])
        flow = _name_flow(_sessions[name])
        if len(flow) > 4:
            flow = ["…"] + flow[-4:]
        who = f"  {Fore.CYAN}{' → '.join(flow)}{Style.RESET_ALL}" if flow else ""
        print(f"  [{marker}] {i}. {name} ({count} messages){who}")
    print()

def switch_session() -> None:
    global _current_session, _last_assistant_text
    list_sessions()
    choice = _ask(f"{Fore.CYAN}[+] Switch to (number or name): {Style.RESET_ALL}")
    if not choice:
        return
    names = sorted(_sessions.keys())
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(names):
            name = names[idx]
        else:
            print(f"{Fore.RED}[!] Invalid number.{Style.RESET_ALL}")
            return
    else:
        if choice not in _sessions:
            print(
                f"{Fore.RED}[!] Session '{choice}' not found. Use [new] to create.{Style.RESET_ALL}"
            )
            return
        name = choice

    _current_session = name
    _last_assistant_text = _session_last_text.get(name, "")
    print(
        f"{Fore.GREEN}[OK] Switched to '{_current_session}' "
        f"({len(_sessions[_current_session])} messages){Style.RESET_ALL}"
    )

def new_session() -> None:
    global _current_session, _last_assistant_text
    name = _ask(f"{Fore.CYAN}[+] New session name: {Style.RESET_ALL}")
    if not name:
        print(f"{Fore.RED}[!] Name cannot be empty.{Style.RESET_ALL}")
        return
    name = _sanitize_session_name(name)
    if name in _sessions:
        print(
            f"{Fore.YELLOW}[!] Session '{name}' already exists. Switched to it.{Style.RESET_ALL}"
        )
        _current_session = name
        _last_assistant_text = _session_last_text.get(name, "")
        return
    _sessions[name] = []
    _current_session = name
    _last_assistant_text = ""
    print(f"{Fore.GREEN}[OK] Created and switched to '{name}'{Style.RESET_ALL}")

def rename_session() -> None:
    global _current_session
    old = _current_session
    new = _ask(f"{Fore.CYAN}[+] Rename '{old}' to: {Style.RESET_ALL}")
    if not new:
        return
    new = _sanitize_session_name(new)
    if new == old:
        print(f"{Fore.YELLOW}[~] Same name. No change.{Style.RESET_ALL}")
        return
    if new in _sessions:
        print(f"{Fore.RED}[!] Name '{new}' already exists.{Style.RESET_ALL}")
        return
    _sessions[new] = _sessions.pop(old)
    _session_last_text[new] = _session_last_text.pop(old, "")
    _current_session = new

    # Save new session BEFORE removing old file so a crash won't lose data
    _save_session_atomic(new)

    # Remove old session file to avoid orphan files
    old_path = os.path.join(SESSION_DIR, _safe_session_name(old))
    new_path = os.path.join(SESSION_DIR, _safe_session_name(new))
    try:
        if os.path.exists(old_path):
            # On case-insensitive filesystems (Windows/macOS) renaming "work" → "Work"
            # resolves to the same physical file.  Skip deletion so we don't nuke the
            # newly-written session.
            try:
                same = os.path.samefile(old_path, new_path)
            except (OSError, ValueError):
                same = False
            if not same:
                os.remove(old_path)
    except OSError as e:
        print(f"{Fore.YELLOW}[!] Could not remove old file: {e}{Style.RESET_ALL}")

    print(f"{Fore.GREEN}[OK] Renamed '{old}' → '{new}'{Style.RESET_ALL}")

def delete_session() -> None:
    name = _ask(f"{Fore.CYAN}[+] Delete session (name, Enter=cancel): {Style.RESET_ALL}")
    if not name or name not in _sessions:
        print(f"{Fore.YELLOW}[~] Cancelled or not found.{Style.RESET_ALL}")
        return
    if name == _current_session:
        print(f"{Fore.RED}[!] Cannot delete the current session.{Style.RESET_ALL}")
        return
    confirm = _ask(f"{Fore.RED}[!] Really delete '{name}'? type 'yes': {Style.RESET_ALL}")
    if confirm != "yes":
        print(f"{Fore.YELLOW}[~] Cancelled.{Style.RESET_ALL}")
        return
    del _sessions[name]
    _session_last_text.pop(name, None)
    # Also delete the file
    fname = _safe_session_name(name)
    path = os.path.join(SESSION_DIR, fname)
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError as e:
        print(f"{Fore.YELLOW}[!] Could not remove file: {e}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}[OK] Deleted '{name}'{Style.RESET_ALL}")

# ============ CHAT ============
def _server_error_text(resp: Optional[requests.Response]) -> str:
    """Short reason taken from an error response body (JSON "error" field if present)."""
    if resp is None:
        return ""
    try:
        data = resp.json()
        if isinstance(data, dict) and data.get("error"):
            return str(data["error"])[:200]
    except ValueError:
        pass
    text = (resp.text or "").strip()
    return "" if text in ("", "{}") else text[:200]

def send_chat(
    messages: list[dict[str, str]], stream: bool = True
) -> Optional[requests.Response]:
    payload: dict[str, object] = {
        "model": current_model,
        "messages": messages,
        "stream": stream,
        "temperature": _temperature,
    }
    if _max_tokens is not None:
        payload["max_tokens"] = _max_tokens

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "PollenChat/2.8.12",
    }

    try:
        response = requests.post(
            API_BASE, headers=headers, json=payload, stream=stream,
            timeout=(10, 60) if stream else (10, 180),  # (connect, read)
        )
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response is not None else None
        reason = _server_error_text(e.response)
        if code == 429:
            print(
                f"{Fore.RED}[!] Rate limited (429). "
                f"PollinationsAI free tier has limits. Wait a moment and retry.{Style.RESET_ALL}"
            )
        elif code is not None and code >= 500:
            print(f"{Fore.RED}[!] HTTP {code} from server: {reason or '(no details)'}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}    Server-side problem, not a PollenChat bug. Retry later.{Style.RESET_ALL}")
        else:
            detail = f" — {reason}" if reason else ""
            print(f"{Fore.RED}[!] HTTP Error: {e}{detail}{Style.RESET_ALL}")
        return None
    except Exception as e:
        print(f"{Fore.RED}[!] Request failed: {e}{Style.RESET_ALL}")
        return None

def stream_response(response: requests.Response) -> tuple[str, bool]:
    full_text = ""   # accepted text (after turn-guard truncation)
    shown = 0        # how many chars of full_text are already on screen
    completed = False
    stopped = False
    finished = False  # saw [DONE] or a finish_reason

    def _emit(s: str) -> None:
        if s:
            sys.stdout.write(Fore.MAGENTA + s + Style.RESET_ALL)
            sys.stdout.flush()

    try:
        for line in response.iter_lines(decode_unicode=False):
            if not line:
                continue
            text_line = line.decode("utf-8", errors="replace").strip()
            if not text_line.startswith("data:"):
                continue
            data_str = text_line[5:].strip()
            if data_str == "[DONE]":
                finished = True
                break
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            choices = data.get("choices")
            if not isinstance(choices, list) or not choices:
                continue
            first = choices[0]
            if not isinstance(first, dict):
                continue
            if first.get("finish_reason"):
                finished = True
            delta = first.get("delta")
            if not isinstance(delta, dict):
                continue
            content = delta.get("content") or ""
            if not content:
                continue

            candidate = full_text + content
            marker_positions = _find_turn_markers(candidate)

            if len(marker_positions) >= 2:
                # Two or more markers: definitely a fake turn sequence.
                # Truncate at the first marker and stop reading.
                full_text = candidate[: marker_positions[0]]
                stopped = True
                _emit(full_text[shown:])
                shown = len(full_text)
                break
            elif len(marker_positions) == 1:
                # Exactly one marker: hold back everything from the marker onward.
                # If a second marker arrives later we will truncate here;
                # if the stream ends with only one marker it was legitimate content
                # (definition, example, etc.) and we flush the held-back tail at the end.
                full_text = candidate
                pos = marker_positions[0]
                if pos > shown:
                    _emit(full_text[shown:pos])
                    shown = pos
            else:
                # No markers yet: normal streaming with held-back tail
                full_text = candidate
                safe = len(full_text) - _held_back_len(full_text)
                if safe > shown:
                    _emit(full_text[shown:safe])
                    shown = safe

        if not stopped:
            _emit(full_text[shown:])  # flush any held-back tail
        completed = True
        print()
        if stopped:
            print(f"{Fore.YELLOW}[~] Turn guard stopped fake turn generation.{Style.RESET_ALL}")
        elif not finished:
            print(
                f"{Fore.YELLOW}[~] Stream ended without [DONE]; "
                f"the response may be cut off.{Style.RESET_ALL}"
            )
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[!] Interrupted by user.{Style.RESET_ALL}")
    except requests.exceptions.RequestException as e:
        print(f"\n{Fore.RED}[!] Stream error: {e}{Style.RESET_ALL}")
    finally:
        response.close()
        # Defensive flush: on some terminal emulators (e.g. Colab xterm.js)
        # streamed output can leak into the next input() buffer.
        sys.stdout.flush()
    return full_text, completed

def batch_response(response: requests.Response) -> tuple[str, bool]:
    try:
        data = response.json()
        choices = data.get("choices") or []
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message") or {}
            if isinstance(message, dict):
                content = message.get("content", "")
                if content:
                    truncated = _truncate_at_turn(content)
                    if truncated != content:
                        print(
                            f"\n{Fore.YELLOW}[~] Turn guard stopped fake turn generation.{Style.RESET_ALL}"
                        )
                    print(Fore.MAGENTA + truncated + Style.RESET_ALL)
                    return truncated, True
        return "", True
    except (json.JSONDecodeError, KeyError, AttributeError, requests.exceptions.RequestException) as e:
        print(f"{Fore.RED}[!] Batch response error: {e}{Style.RESET_ALL}")
        return "", False

def _trim_history(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    system_msgs = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]

    trimmed = rest[-MAX_HISTORY:] if len(rest) > MAX_HISTORY else rest[:]
    while trimmed and trimmed[0].get("role") != "user":
        trimmed = trimmed[1:]

    return system_msgs + trimmed

def _build_messages_for_api(user_input: str) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = []
    if _system_prompt:
        msgs.append({"role": "system", "content": _system_prompt})
    # Only role/content go to the API; the local "name" field stays in the log
    msgs.extend(
        {"role": m["role"], "content": m["content"]} for m in _sessions[_current_session]
    )
    msgs.append({"role": "user", "content": user_input})
    return _trim_history(msgs)

def chat_once(user_input: str) -> bool:
    global _last_assistant_text

    api_messages = _build_messages_for_api(user_input)
    response = send_chat(api_messages, stream=_stream_mode)
    if not response:
        return False

    _sessions[_current_session].append(
        {"role": "user", "content": user_input, "name": username}
    )

    print(f"\n{Fore.YELLOW}PollenChat ({current_model}):{Style.RESET_ALL} ", end="", flush=True)

    if _stream_mode:
        assistant_text, completed = stream_response(response)
    else:
        assistant_text, completed = batch_response(response)

    if not completed or not assistant_text:
        _sessions[_current_session].pop()
        print(f"{Fore.YELLOW}[~] この応答は履歴に追加しませんでした。{Style.RESET_ALL}")
        _last_assistant_text = ""
        _session_last_text[_current_session] = ""
        return False

    _sessions[_current_session].append({"role": "assistant", "content": assistant_text})
    _last_assistant_text = assistant_text
    _session_last_text[_current_session] = assistant_text
    _save_session_atomic(_current_session)  # auto-save after every exchange
    return True

# ============ RENDER LAST RESPONSE ============
def render_last() -> None:
    if not _last_assistant_text:
        print(f"{Fore.YELLOW}[~] No assistant response to render yet.{Style.RESET_ALL}")
        return
    print(f"\n{Fore.YELLOW}--- Rendered (Markdown) ---{Style.RESET_ALL}\n")
    print(render_markdown(_last_assistant_text))
    print(f"\n{Fore.YELLOW}---------------------------{Style.RESET_ALL}\n")

# ============ SAVE CODE ============
def _extract_code_blocks(text: str) -> list[tuple[str, str]]:
    pattern = r"```([\w+\-#]*)\n(.*?)\n```"
    return re.findall(pattern, text, re.DOTALL)

def _guess_extension(lang: str) -> str:
    return LANG_EXT.get(lang.lower(), ".txt")

def save_code() -> None:
    if not _last_assistant_text:
        print(f"{Fore.YELLOW}[~] No assistant response to extract code from.{Style.RESET_ALL}")
        return

    blocks = _extract_code_blocks(_last_assistant_text)
    if not blocks:
        print(
            f"{Fore.YELLOW}[~] No code blocks (```...```) found in last response.{Style.RESET_ALL}"
        )
        return

    print(f"\n{Fore.YELLOW}Code blocks found: {len(blocks)}{Style.RESET_ALL}")
    for i, (lang, code_text) in enumerate(blocks, 1):
        lang_display = lang if lang else "(no language)"
        line_count = code_text.count("\n") + 1
        preview = code_text[:80].replace("\n", " ")
        suffix = "..." if len(code_text) > 80 else ""
        print(f"  {i}. [{lang_display}] {line_count} lines — {preview}{suffix}")

    choice = _ask(
        f"\n{Fore.CYAN}[+] Select block number (Enter = 1, [all] = save each): {Style.RESET_ALL}"
    )

    if choice.lower() == "all":
        saved = []
        for idx, (lang, code_text) in enumerate(blocks, 1):
            ext = _guess_extension(lang)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = os.path.join(CODE_DIR, f"snippet_{ts}_{idx}{ext}")
            with open(fname, "w", encoding="utf-8") as f:
                f.write(code_text)
            saved.append(fname)
        print(f"{Fore.GREEN}[OK] Saved {len(saved)} file(s) to {CODE_DIR}/{Style.RESET_ALL}")
        for s in saved:
            print(f"  - {os.path.basename(s)}")
        return

    if not choice:
        choice = "1"
    if not choice.isdigit():
        print(f"{Fore.RED}[!] Invalid selection.{Style.RESET_ALL}")
        return

    idx = int(choice) - 1
    if not (0 <= idx < len(blocks)):
        print(f"{Fore.RED}[!] Invalid selection.{Style.RESET_ALL}")
        return

    lang, code_text = blocks[idx]
    ext = _guess_extension(lang)
    default_name = f"snippet{ext}"
    raw_name = _ask(f"{Fore.CYAN}[+] Filename (Enter for '{default_name}'): {Style.RESET_ALL}")
    fname = _safe_filename(raw_name) if raw_name else default_name
    if not os.path.splitext(fname)[1]:
        fname += ext

    path = os.path.join(CODE_DIR, fname)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(code_text)
        print(f"{Fore.GREEN}[OK] Code saved: {path}{Style.RESET_ALL}")
    except OSError as e:
        print(f"{Fore.RED}[!] Save failed: {e}{Style.RESET_ALL}")

# ============ EXPORT ============
def export_session() -> None:
    if not _sessions[_current_session]:
        print(f"{Fore.YELLOW}[~] No conversation to export.{Style.RESET_ALL}")
        return

    raw = _ask(f"{Fore.CYAN}[+] Export filename (Enter for auto): {Style.RESET_ALL}")
    if raw:
        fname = _safe_filename(raw)
        if not fname.endswith(".md"):
            fname += ".md"
    else:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"export_{ts}.md"

    include_system = False
    if _system_prompt:
        sp_choice = _ask(
            f"{Fore.CYAN}[+] Include system prompt in export? y/N: {Style.RESET_ALL}"
        ).lower()
        include_system = sp_choice == "y"

    lines = []
    lines.append("# PollenChat Session Export\n")
    lines.append(f"- **Model:** {current_model}\n")
    lines.append(f"- **Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    if include_system:
        lines.append(f"- **System Prompt:** {_system_prompt}\n")
    lines.append("\n---\n")

    for msg in _sessions[_current_session]:
        role = f"User ({_msg_name(msg)})" if msg["role"] == "user" else "Assistant"
        lines.append(f"\n## {role}\n\n{msg['content']}\n")

    lines.append("\n---\n\n*Exported by PollenChat*\n")

    path = os.path.join(EXPORT_DIR, fname)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(lines))
        print(f"{Fore.GREEN}[OK] Exported to: {path}{Style.RESET_ALL}")
    except OSError as e:
        print(f"{Fore.RED}[!] Export failed: {e}{Style.RESET_ALL}")

# ============ EXPORT (exchange range) ============
# One "exchange" = an assistant message plus the user message right before it.
# Indexes follow Python lists: 0 = oldest, -1 = latest. Ranges are slices
# (start:stop:step, stop excluded), e.g. [export -3:] [export 2:5] [export ::-1].
EXPORT_Q_LIMIT = 500   # longer questions are shortened unless "full" is given
EXPORT_Q_HEAD = 350
EXPORT_Q_TAIL = 150

_EXPORT_CMD_RE = re.compile(r"^\[export\s+(.*?)\s*\]$", re.IGNORECASE)
_EXPORT_INDEX_RE = re.compile(r"^-?\d+$")
_EXPORT_SLICE_RE = re.compile(r"^(-?\d*):(-?\d*)(?::(-?\d*))?$")
_EXPORT_FLAGS = ("rev", "bare", "full")

EXPORT_USAGE = (
    "Usage: [export] | [export list] | [export <index|slice> [rev] [bare] [full]]\n"
    "  index : 0 = oldest, -1 = latest          e.g. [export -1]\n"
    "  slice : start:stop:step (stop excluded)  e.g. [export -3:]  [export 2:5]  [export ::-1]\n"
    "  rev   : reverse the selected order       bare : answers only\n"
    "  full  : do not shorten long questions"
)


def _exchanges() -> list[tuple[str, str, str]]:
    """(question, answer, asker name) of the current session, oldest first."""
    history = _sessions[_current_session]
    result: list[tuple[str, str, str]] = []
    for i, msg in enumerate(history):
        if msg["role"] != "assistant":
            continue
        question = ""
        asker = ""
        if i > 0 and history[i - 1]["role"] == "user":
            question = history[i - 1]["content"]
            asker = _msg_name(history[i - 1])
        result.append((question, msg["content"], asker))
    return result


def _parse_export_args(raw: str, n: int) -> tuple[Optional[dict], Optional[str]]:
    """Parse the text inside [export ...]. Returns (parsed, error)."""
    tokens = raw.lower().split()
    if "list" in tokens:
        if len(tokens) > 1:
            return None, "'list' cannot be combined with other arguments."
        return {"list": True}, None

    flags: set[str] = set()
    sel: Optional[str] = None
    for tok in tokens:
        if tok in _EXPORT_FLAGS:
            flags.add(tok)
        elif _EXPORT_INDEX_RE.match(tok) or _EXPORT_SLICE_RE.match(tok):
            if sel is not None:
                return None, "Only one index or slice is allowed."
            sel = tok
        else:
            return None, f"Unknown argument: {tok}"

    if sel is None:
        picked = list(range(n))
        sel_text = ":"
    elif _EXPORT_INDEX_RE.match(sel):
        k = int(sel)
        if not (-n <= k < n):
            return None, f"Index {k} out of range (valid: {-n} to {n - 1})."
        picked = [k % n]
        sel_text = sel
    else:
        parts = [int(x) if x else None for x in _EXPORT_SLICE_RE.match(sel).groups()]
        if parts[2] == 0:
            return None, "Slice step cannot be zero."
        picked = list(range(n))[slice(*parts)]
        sel_text = sel

    if "rev" in flags:
        picked.reverse()
    return {"picked": picked, "flags": flags, "sel": sel_text}, None


def _balance_fences(text: str, inside: bool = False) -> str:
    """Make sure ``` fences in a cut-out piece are paired."""
    if inside:
        text = "```\n" + text
    if text.count("```") % 2 == 1:
        text += "\n```"
    return text


def _shorten_question(q: str) -> str:
    """Keep head + tail of a long question (imported files put the real
    question at the END of the message)."""
    if len(q) <= EXPORT_Q_LIMIT:
        return q
    head = q[:EXPORT_Q_HEAD]
    tail = q[-EXPORT_Q_TAIL:]
    tail_inside = q[: len(q) - EXPORT_Q_TAIL].count("```") % 2 == 1
    note = (
        f"…（全 {len(q):,} 文字のうち先頭 {EXPORT_Q_HEAD} 文字と"
        f"末尾 {EXPORT_Q_TAIL} 文字を表示）…"
    )
    short = f"{_balance_fences(head)}\n\n{note}\n\n{_balance_fences(tail, tail_inside)}"
    return short if len(short) < len(q) else q  # never make it longer


def _quote(text: str) -> str:
    lines = text.splitlines() or [""]
    return "\n".join(f"> {ln}" if ln else ">" for ln in lines)


def _build_exchange_md(
    exs: list[tuple[str, str, str]], picked: list[int], flags: set[str], sel_text: str
) -> str:
    n = len(exs)

    def heading(i: int) -> str:
        return f"## #{i} ({i - n})"

    if "bare" in flags:
        if len(picked) == 1:
            return exs[picked[0]][1].rstrip("\n") + "\n"
        blocks = [f"{heading(i)}\n\n{exs[i][1].rstrip()}" for i in picked]
        return "\n\n---\n\n".join(blocks) + "\n"

    if len(picked) == 1:
        order = "1 exchange"
    else:
        if picked == sorted(picked):
            how = "oldest first"
        elif picked == sorted(picked, reverse=True):
            how = "newest first"
        else:
            how = "custom order"
        order = f"{len(picked)} exchanges, {how}"

    lines = [
        "# PollenChat Export\n",
        f"- **Session:** {_current_session}\n",
        f"- **Selection:** {sel_text} ({order})\n",
        f"- **Model:** {current_model} (at export)\n",
        f"- **Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        "\n---\n",
    ]
    for i in picked:
        question, answer, asker = exs[i]
        lines.append(f"\n{heading(i)}\n")
        if question:
            q = question if "full" in flags else _shorten_question(question)
            label = f"User ({asker})" if asker else "User"
            lines.append(f"\n### {label}\n\n{_quote(q)}\n")
        lines.append(f"\n### Assistant\n\n{answer.rstrip()}\n")
        lines.append("\n---\n")
    lines.append("\n*Exported by PollenChat*\n")
    return "".join(lines)


def _export_filename(picked: list[int], flags: set[str]) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    lo, hi = min(picked), max(picked)
    span = f"{lo:04d}" if lo == hi else f"{lo:04d}-{hi:04d}"
    if len(picked) > 1 and sorted(picked) != list(range(lo, hi + 1)):
        span += "_sparse"
    suffix = "".join(f"_{f}" for f in _EXPORT_FLAGS if f in flags)
    base = f"export_{ts}_{_safe_filename(_current_session)}_{span}{suffix}"
    name = f"{base}.md"
    k = 2
    while os.path.exists(os.path.join(EXPORT_DIR, name)):
        name = f"{base}_{k}.md"
        k += 1
    return name


def _one_line(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit] + "…"


def _print_exchange_list(exs: list[tuple[str, str, str]]) -> None:
    n = len(exs)
    w = len(str(n - 1))
    print(
        f"\n{Fore.YELLOW}Exchanges in '{_current_session}' "
        f"(oldest first, {n} total):{Style.RESET_ALL}"
    )
    for i, (q, a, who) in enumerate(exs):
        print(
            f"  [{i:>{w}}] ({i - n:>{w + 1}}) "
            f"{who or 'Q'}: {_one_line(q, 40) or '-'} | A: {_one_line(a, 40)}"
        )
    print()


def export_exchanges(raw: str) -> None:
    """[export <index|slice> [rev] [bare] [full]] and [export list]."""
    exs = _exchanges()
    if not exs:
        print(f"{Fore.YELLOW}[~] No conversation to export.{Style.RESET_ALL}")
        return

    parsed, err = _parse_export_args(raw, len(exs))
    if err or parsed is None:
        print(f"{Fore.RED}[!] {err}{Style.RESET_ALL}\n{EXPORT_USAGE}")
        return
    if parsed.get("list"):
        _print_exchange_list(exs)
        return

    picked = parsed["picked"]
    if not picked:
        print(f"{Fore.YELLOW}[~] Nothing matches that selection.{Style.RESET_ALL}")
        return

    md = _build_exchange_md(exs, picked, parsed["flags"], parsed["sel"])
    path = os.path.join(EXPORT_DIR, _export_filename(picked, parsed["flags"]))
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        print(
            f"{Fore.GREEN}[OK] Exported {len(picked)} exchange(s) to: {path}{Style.RESET_ALL}"
        )
    except OSError as e:
        print(f"{Fore.RED}[!] Export failed: {e}{Style.RESET_ALL}")

# ============ IMPORT ============
def import_file() -> None:
    raw_path = _ask(f"{Fore.CYAN}[+] File path: {Style.RESET_ALL}")
    # Strip surrounding quotes that shell or copy-paste may add
    raw_path = raw_path.strip("'\"")
    path = os.path.expanduser(raw_path)
    if not path or not os.path.isfile(path):
        print(f"{Fore.RED}[!] File not found.{Style.RESET_ALL}")
        return

    ext = os.path.splitext(path)[1].lower()
    if ext not in (".md", ".txt"):
        print(f"{Fore.YELLOW}[!] Only .md and .txt files are supported.{Style.RESET_ALL}")
        return

    size = os.path.getsize(path)
    if size > IMPORT_MAX_BYTES:
        confirm = _ask(
            f"{Fore.YELLOW}[!] {size:,} bytes. Continue? y/N: {Style.RESET_ALL}"
        ).lower()
        if confirm != "y":
            return

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError as e:
        print(f"{Fore.RED}[!] Read failed: {e}{Style.RESET_ALL}")
        return

    print(f"{Fore.GREEN}[OK] Loaded {len(content):,} characters.{Style.RESET_ALL}")
    preview = content[:200].replace("\n", " ")
    suffix = "..." if len(content) > 200 else ""
    print(f"{Fore.CYAN}[Preview]:{Style.RESET_ALL} {preview}{suffix}\n")

    extra = _ask(
        f"{Fore.CYAN}[+] Question about this file (Enter to send file content only): {Style.RESET_ALL}",
        multiline=True,
    )

    full_input = f"{content}\n\n{extra}" if extra else content
    chat_once(full_input)

# ============ UNDO ============
def undo_last() -> None:
    global _last_assistant_text
    history = _sessions[_current_session]
    if len(history) < 2:
        print(f"{Fore.YELLOW}[~] No exchange to undo.{Style.RESET_ALL}")
        return

    removed = []
    if history[-1]["role"] == "assistant":
        removed.append(history.pop())
    if history and history[-1]["role"] == "user":
        removed.append(history.pop())

    _last_assistant_text = ""
    _session_last_text[_current_session] = ""
    _save_session_atomic(_current_session)  # persist immediately
    print(
        f"{Fore.GREEN}[OK] Undid last exchange ({len(removed)} message(s)). "
        f"History now: {len(history)} messages.{Style.RESET_ALL}"
    )

# ============ TOKEN ESTIMATE ============
def estimate_tokens() -> None:
    all_text = _system_prompt + "".join(m["content"] for m in _sessions[_current_session])
    total_chars = len(all_text)
    ascii_chars = sum(1 for c in all_text if ord(c) < 128)
    non_ascii_chars = total_chars - ascii_chars
    est = ascii_chars / 4 + non_ascii_chars / 1.5

    print(f"\n{Fore.YELLOW}Token estimate ({_current_session}):{Style.RESET_ALL}")
    print(f"  Approximate tokens : {int(est):,}")
    print(f"  Total characters   : {total_chars:,}")
    print(f"  ASCII chars        : {ascii_chars:,}")
    print(f"  Non-ASCII chars    : {non_ascii_chars:,}")
    print(
        f"{Fore.YELLOW}  ※ Rough estimate. "
        f"Actual API sends only last {MAX_HISTORY} messages (plus system).{Style.RESET_ALL}\n"
    )

# ============ IMAGE GENERATION ============
def _ext_from_content_type(content_type: str) -> str:
    ct = content_type.lower()
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    if "webp" in ct:
        return ".webp"
    return ".png"

def generate_image(
    prompt: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    seed: Optional[int] = None,
    nologo: bool = True,
) -> Optional[str]:
    w = width if width is not None else _img_width
    h = height if height is not None else _img_height
    s = seed if seed is not None else (_img_seed if _img_seed is not None else random.randint(1, 999999))

    if w < 64 or h < 64 or w > 4096 or h > 4096:
        print(f"{Fore.RED}[!] Image size must be between 64 and 4096.{Style.RESET_ALL}")
        return None

    encoded_prompt = quote(prompt, safe="")
    url = (
        f"{IMAGE_BASE}/{encoded_prompt}"
        f"?width={w}&height={h}&seed={s}"
        f"&nologo={str(nologo).lower()}"
    )

    print(
        f"{Fore.CYAN}[~] Generating image... "
        f"prompt: {prompt[:50]}... | size: {w}x{h} | seed: {s}{Style.RESET_ALL}"
    )

    try:
        r = requests.get(url, timeout=60)
        if r.status_code != 200:
            print(
                f"{Fore.RED}[!] Failed to generate image: HTTP {r.status_code}{Style.RESET_ALL}"
            )
            return None

        content_type = r.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            print(
                f"{Fore.RED}[!] Unexpected Content-Type: {content_type} "
                f"(expected image/*){Style.RESET_ALL}"
            )
            return None

        ext = _ext_from_content_type(content_type)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_prompt = "".join(c if c.isalnum() else "_" for c in prompt[:30])
        filename = os.path.join(IMAGE_DIR, f"img_{ts}_{safe_prompt}{ext}")
        with open(filename, "wb") as f:
            f.write(r.content)
        print(f"{Fore.GREEN}[OK] Image saved: {filename}{Style.RESET_ALL}")
        return filename
    except Exception as e:
        print(f"{Fore.RED}[!] Image generation error: {e}{Style.RESET_ALL}")
        return None

def image_mode() -> None:
    global _img_width, _img_height, _img_seed

    print(f"\n{Fore.YELLOW}Image Generation Mode{Style.RESET_ALL}")
    print(
        f"  Current: {_img_width}x{_img_height}, "
        f"seed={_img_seed if _img_seed is not None else 'random'}\n"
    )
    print("  Type your prompt, 'exit' to leave, or:")
    print("  [size] — change width/height")
    print("  [seed] — set/clear a fixed seed\n")

    while True:
        prompt = _ask(f"{Fore.CYAN}[image] {username}: {Style.RESET_ALL}")
        if not prompt:
            continue

        cmd = prompt.lower()
        if cmd in ("exit", "quit", "back"):
            print(f"{Fore.YELLOW}[~] Returning to chat mode.{Style.RESET_ALL}\n")
            break
        elif cmd in ("[size]", "size"):
            w_input = _ask(
                f"{Fore.CYAN}[+] width (current: {_img_width}): {Style.RESET_ALL}"
            )
            h_input = _ask(
                f"{Fore.CYAN}[+] height (current: {_img_height}): {Style.RESET_ALL}"
            )
            # Validate in temporary variables before mutating state
            try:
                w_tmp = int(w_input) if w_input else _img_width
                h_tmp = int(h_input) if h_input else _img_height
            except ValueError:
                print(f"{Fore.RED}[!] Width and height must be integers.{Style.RESET_ALL}")
                continue
            if w_tmp < 64 or h_tmp < 64 or w_tmp > 4096 or h_tmp > 4096:
                print(
                    f"{Fore.RED}[!] Size must be between 64 and 4096. "
                    f"Tried: {w_tmp}x{h_tmp}{Style.RESET_ALL}"
                )
                continue
            _img_width, _img_height = w_tmp, h_tmp
            print(f"{Fore.GREEN}[OK] Size set to {_img_width}x{_img_height}{Style.RESET_ALL}")
            continue
        elif cmd in ("[seed]", "seed"):
            s_input = _ask(
                f"{Fore.CYAN}[+] seed (current: "
                f"{_img_seed if _img_seed is not None else 'random'}, 'none'=random): {Style.RESET_ALL}"
            )
            if s_input.lower() == "none":
                _img_seed = None
                print(f"{Fore.GREEN}[OK] Seed set to random{Style.RESET_ALL}")
            elif s_input.isdigit():
                _img_seed = int(s_input)
                print(f"{Fore.GREEN}[OK] Seed fixed to {_img_seed}{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}[~] Kept current seed.{Style.RESET_ALL}")
            continue

        generate_image(prompt)

# ============ MULTILINE INPUT ============
def read_multiline() -> str:
    print(
        f"{Fore.CYAN}[+] Multiline mode. "
        f"Type [end] on its own line to finish:{Style.RESET_ALL}"
    )
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "[end]":
            break
        lines.append(line)
    return "\n".join(lines)

# ============ SEARCH ============
def search_history() -> None:
    query = _ask(f"{Fore.CYAN}[+] Search keyword: {Style.RESET_ALL}").lower()
    if not query:
        print(f"{Fore.YELLOW}[~] Empty query.{Style.RESET_ALL}")
        return

    matches = []
    for i, msg in enumerate(_sessions[_current_session]):
        if query in msg["content"].lower():
            role_label = _msg_name(msg) if msg["role"] == "user" else "AI"
            snippet = msg["content"][:120]
            suffix = "..." if len(msg["content"]) > 120 else ""
            matches.append((i, msg["role"], role_label, snippet + suffix))

    if not matches:
        print(f"{Fore.YELLOW}[~] No matches found.{Style.RESET_ALL}")
        return

    print(f"\n{Fore.GREEN}{len(matches)} match(es):{Style.RESET_ALL}")
    for idx, role, role_label, snippet in matches:
        color = Fore.GREEN if role == "user" else Fore.MAGENTA
        print(f"  {color}[{idx}]{role_label}:{Style.RESET_ALL} {snippet}")
    print()

# ============ LEGACY SESSION SAVE/LOAD ============
def save_session() -> None:
    raw = _ask(
        f"{Fore.CYAN}[+] Save current session as (Enter='{_current_session}'): {Style.RESET_ALL}"
    )
    name = _sanitize_session_name(raw) if raw else _current_session
    fname = _safe_session_name(name)
    path = os.path.join(SESSION_DIR, fname)

    if name != _current_session and name in _sessions:
        confirm = _ask(
            f"{Fore.YELLOW}[!] '{name}' already exists. Overwrite? y/N: {Style.RESET_ALL}"
        ).lower()
        if confirm != "y":
            print(f"{Fore.YELLOW}[~] Cancelled.{Style.RESET_ALL}")
            return

    # Assign first: _save_session_atomic() reads _sessions[name]
    if name != _current_session:
        _sessions[name] = list(_sessions[_current_session])
    _save_session_atomic(name)  # atomic write for crash safety
    print(f"{Fore.GREEN}[OK] Session saved: {path}{Style.RESET_ALL}")

def load_session() -> None:
    global _last_assistant_text, _current_session
    global current_model, _system_prompt, _temperature, _max_tokens

    files = sorted(f for f in os.listdir(SESSION_DIR) if f.endswith(".json"))
    if not files:
        print(f"{Fore.YELLOW}[!] No saved sessions found.{Style.RESET_ALL}")
        return

    print(f"\n{Fore.YELLOW}Saved sessions:{Style.RESET_ALL}")
    for i, f in enumerate(files, 1):
        print(f"  {i}. {f}")

    choice = _ask(
        f"\n{Fore.CYAN}[+] Select session (number or name): {Style.RESET_ALL}"
    )
    if not choice:
        return
    if choice.isdigit():
        idx = int(choice) - 1
        if not (0 <= idx < len(files)):
            print(f"{Fore.RED}[!] Invalid number.{Style.RESET_ALL}")
            return
        fname = files[idx]
    else:
        fname = _safe_session_name(choice)

    path = os.path.join(SESSION_DIR, fname)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"{Fore.RED}[!] Load failed: {e}{Style.RESET_ALL}")
        return

    history = data.get("history", []) if isinstance(data, dict) else None
    if not _valid_history(history):
        print(f"{Fore.RED}[!] Load failed: invalid session format.{Style.RESET_ALL}")
        return

    _stamp_names(history, data.get("username"))
    name = fname[:-5]
    _sessions[name] = history
    _current_session = name
    _last_assistant_text = _session_last_text.get(name, "")

    model = data.get("model")
    if isinstance(model, str) and model:
        current_model = model
    sp = data.get("system_prompt")
    if isinstance(sp, str):
        _system_prompt = sp
    temp = data.get("temperature")
    if isinstance(temp, (int, float)):
        _temperature = float(temp)
    mt = data.get("max_tokens")
    if mt is None:
        _max_tokens = None
    elif isinstance(mt, int) and not isinstance(mt, bool):
        _max_tokens = mt

    print(
        f"{Fore.GREEN}[OK] Loaded session: {fname} "
        f"({len(history)} messages){Style.RESET_ALL}"
    )

def clear_history() -> None:
    global _last_assistant_text
    _sessions[_current_session] = []
    _last_assistant_text = ""
    _session_last_text[_current_session] = ""
    _save_session_atomic(_current_session)  # persist immediately
    print(f"{Fore.GREEN}[OK] Conversation history cleared.{Style.RESET_ALL}")

# ============ HELP ============
HELP_TEXT = r"""
PollenChat Commands:

  [model]       — Select AI model
  [system]      — Set or view the system prompt
  [name]        — Change your display name (past messages keep the name they were sent with)
  [config]      — Set temperature / max_tokens
  [stream]      — Toggle streaming / batch display mode (batch recommended on web terminals)
  [guard]       — Toggle turn guard (default OFF). Stops models that spontaneously
                  generate fake User:/Assistant: turns. Requires 2+ role labels
                  outside code blocks before cutting (reduces false positives).
  [image]       — Enter image generation mode
  [long]        — Enter multiline input mode (type [end] to finish)
  [import]      — Import a .md/.txt file and send as user message
  [search]      — Search conversation history
  [render]      — Re-display last response with Markdown formatting
  [savecode]    — Extract and save code blocks from last response
  [export]      — Export conversation to Markdown file
  [export list] — List Q&A exchanges with indexes (0 = oldest, -1 = latest)
  [export -1]   — Export exchange(s) by index or slice (stop excluded):
                  [export -3:]  [export 2:5]  [export ::-1]
                  flags: rev (reverse order) / bare (answers only) / full (keep long questions)
  [undo]        — Remove the last user-assistant exchange
  [token]       — Show rough token estimate for current context

  --- Sessions ---
  [sessions]    — List all sessions
  [switch]      — Switch to another session
  [new]         — Create a new empty session
  [rename]      — Rename the current session
  [delete]      — Delete a session (not current)
  [save]        — Save current session (legacy)
  [load]        — Load a session from file (legacy)

  [clear]       — Clear current session history
  [history]     — Show current session history
  [help]        — Show this help
  [exit]        — Quit PollenChat

Just type normally to chat with the AI!
"""

# ============ MAIN ============
def main() -> None:
    global username

    ensure_dirs()

    cfg = load_config()
    apply_config(cfg)

    clear()
    print(Fore.MAGENTA + BANNER + Style.RESET_ALL)

    # Load sessions AFTER clearing screen so broken-JSON warnings are visible
    _auto_load_all_sessions()

    print(f"{Fore.CYAN}[~] Fetching available models from PollinationsAI...{Style.RESET_ALL}")
    fetch_models()
    print(f"{Fore.GREEN}[OK] {len(available_models)} models available.{Style.RESET_ALL}\n")

    if not cfg.get("username"):
        default_name = os.environ.get("USER", os.environ.get("USERNAME", "User"))
        default_name = _validate_username(default_name)[0] or "User"
        while True:
            name_input = _ask(
                f"{Fore.CYAN}[+] Your name (Enter for '{default_name}'): {Style.RESET_ALL}"
            )
            if not name_input:
                username = default_name
                break
            name, err = _validate_username(name_input)
            if err or name is None:
                print(f"{Fore.RED}[!] {err}{Style.RESET_ALL}")
                continue
            username = name
            break
        save_config(build_config())

    print(f"{Fore.GREEN}[OK] Welcome, {username}! Type [help] for commands.{Style.RESET_ALL}")
    print(
        f"{Fore.GREEN}[OK] Current session: '{_current_session}' "
        f"({len(_sessions[_current_session])} messages){Style.RESET_ALL}\n"
    )

    try:
        while True:
            try:
                # Defensive flush before prompt: ensure no stray output
                # leaks into input() on browser-based terminals (xterm.js, etc.)
                sys.stdout.flush()
                prompt_str = (
                    f"{Fore.GREEN}{username}{Style.RESET_ALL}"
                    f"{Fore.CYAN}[{_current_session}]{Style.RESET_ALL} : "
                )
                user_input, is_paste = _read_input(_rl_safe(prompt_str))
                user_input = user_input.strip()
                if not user_input:
                    continue

                # Pasted multi-line text is always treated as a chat message,
                # never as commands. This prevents pasted text containing
                # bracketed words like [exit] from being interpreted as commands.
                if is_paste:
                    chat_once(user_input)
                    continue

                cmd = user_input.lower()

                m_exp = _EXPORT_CMD_RE.match(user_input)
                if m_exp:
                    export_exchanges(m_exp.group(1))
                    continue
                if cmd.startswith("[name "):
                    print(f"{Fore.YELLOW}[~] [name] takes no arguments; just type [name].{Style.RESET_ALL}")
                    continue
                if cmd.startswith("[export "):
                    print(f"{Fore.RED}[!] Malformed export command.{Style.RESET_ALL}\n{EXPORT_USAGE}")
                    continue

                if cmd in ("[exit]", "exit"):
                    print(f"{Fore.YELLOW}Bye bye, {username}!{Style.RESET_ALL}")
                    break
                elif cmd in ("[help]", "help"):
                    print(HELP_TEXT)
                elif cmd in ("[model]", "model"):
                    select_model()
                elif cmd in ("[system]", "system"):
                    set_system_prompt()
                elif cmd == "[name]":
                    set_username()
                elif cmd in ("[config]", "config"):
                    edit_config()
                elif cmd in ("[stream]", "stream"):
                    toggle_stream()
                elif cmd in ("[guard]", "guard"):
                    toggle_turn_guard()
                elif cmd in ("[image]", "image"):
                    image_mode()
                elif cmd in ("[long]", "long"):
                    long_text = read_multiline()
                    if long_text.strip():
                        preview = long_text[:300]
                        suffix = "..." if len(long_text) > 300 else ""
                        print(f"\n{Fore.GREEN}[Input preview]:{Style.RESET_ALL}")
                        print(f"{preview}{suffix}\n")
                        chat_once(long_text)
                elif cmd in ("[import]", "import"):
                    import_file()
                elif cmd in ("[search]", "search"):
                    search_history()
                elif cmd in ("[render]", "render"):
                    render_last()
                elif cmd in ("[savecode]", "savecode"):
                    save_code()
                elif cmd in ("[export]", "export"):
                    export_session()
                elif cmd in ("[undo]", "undo"):
                    undo_last()
                elif cmd in ("[token]", "token"):
                    estimate_tokens()
                elif cmd in ("[sessions]", "sessions"):
                    list_sessions()
                elif cmd in ("[switch]", "switch"):
                    switch_session()
                elif cmd in ("[new]", "new"):
                    new_session()
                elif cmd in ("[rename]", "rename"):
                    rename_session()
                elif cmd in ("[delete]", "delete"):
                    delete_session()
                elif cmd in ("[save]", "save"):
                    save_session()
                elif cmd in ("[load]", "load"):
                    load_session()
                elif cmd in ("[clear]", "clear"):
                    clear_history()
                elif cmd in ("[history]", "history"):
                    print(
                        f"\n{Fore.YELLOW}Conversation History [{_current_session}] "
                        f"({len(_sessions[_current_session])} messages):{Style.RESET_ALL}"
                    )
                    for msg in _sessions[_current_session]:
                        role_color = Fore.GREEN if msg["role"] == "user" else Fore.MAGENTA
                        role_label = _msg_name(msg) if msg["role"] == "user" else "AI"
                        truncated = msg["content"][:100]
                        suffix = "..." if len(msg["content"]) > 100 else ""
                        print(f"  {role_color}{role_label}:{Style.RESET_ALL} {truncated}{suffix}")
                    print()
                else:
                    chat_once(user_input)

            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}[!] Use [exit] to quit.{Style.RESET_ALL}")
            except EOFError:
                break
    finally:
        _auto_save_all_sessions()
        print(f"{Fore.GREEN}[OK] All sessions saved.{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
