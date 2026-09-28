# PollenChat v2.8.5

A clean, harmless CLI chat client for [PollinationsAI](https://pollinations.ai/).

PollenChat is a lightweight terminal-based chat application that lets you talk to various AI models (OpenAI, Mistral, Llama, Claude, Gemini, etc.) through the PollinationsAI free API. It also supports image generation, multi-session management, code extraction, and more.

## Features

- **Multi-model chat** — Switch between models via `[model]`
- **Streaming & batch modes** — Toggle live token-by-token output or wait-for-complete display
- **System prompt editing** — Customize the assistant's behavior with `[system]`
- **Temperature / max_tokens control** — Fine-tune generation parameters with `[config]`
- **Image generation** — Generate images from text prompts inside `[image]` mode, with configurable size and seed
- **Multiline input** — Paste or type long messages with `[long]` (type `[end]` on its own line to finish; blank lines are preserved)
- **File import** — Load `.md` or `.txt` files and send them as user messages with `[import]`
- **Conversation search** — Find past messages with `[search]`
- **Markdown rendering** — Re-display the last response with formatted Markdown via `[render]`
- **Code extraction** — Save code blocks from the last response with `[savecode]`
- **Session export** — Export conversations to Markdown files with `[export]`
- **Undo** — Remove the last user-assistant exchange with `[undo]`
- **Token estimate** — Rough token count estimation for the current context with `[token]`
- **Multi-session management** — Manage multiple parallel conversations with `[sessions]`, `[switch]`, `[new]`, `[rename]`, `[delete]`
- **Auto-save / auto-load** — Every session is saved atomically after each exchange (and on `[undo]`/`[clear]`), plus once more on exit; all sessions are restored on startup

## Installation

```bash
# Clone or download pollenchat.py
git clone https://github.com/kurookuroda/PollenChat.git
cd PollenChat

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

```bash
python pollenchat.py
```

On first launch you will be asked for your name. After that, just type normally to chat. Use `[help]` to see all available commands.

## Commands

### Chat & Settings

| Command | Description |
|---------|-------------|
 `[model]` | Select AI model |
 `[system]` | Set or view the system prompt (multi-line, type `[end]` to finish, `[reset]` for default) |
 `[config]` | Set `temperature` / `max_tokens` |
 `[stream]` | Toggle streaming / batch display mode |

### Input

| Command | Description |
|---------|-------------|
 `[long]` | Enter multiline input mode |
 `[import]` | Import a `.md` / `.txt` file and send as user message |

### Output & History

| Command | Description |
|---------|-------------|
 `[search]` | Search conversation history |
 `[render]` | Re-display last response with Markdown formatting |
 `[savecode]` | Extract and save code blocks from last response |
 `[export]` | Export conversation to Markdown file |
 `[undo]` | Remove the last user-assistant exchange |
 `[token]` | Show rough token estimate for current context |

### Image Generation

| Command | Description |
|---------|-------------|
 `[image]` | Enter image generation mode |

Inside image mode:
- Type a prompt to generate an image
- `[size]` — change width/height (default 1024x1024, range 64–4096)
- `[seed]` — set/clear a fixed seed for reproducible images
- `exit` — return to chat mode

### Session Management

| Command | Description |
|---------|-------------|
 `[sessions]` | List all sessions |
 `[switch]` | Switch to another session |
 `[new]` | Create a new empty session |
 `[rename]` | Rename the current session |
 `[delete]` | Delete a session (cannot delete current) |
 `[save]` | Save current session manually (legacy) |
 `[load]` | Load a session from file manually (legacy) |
 `[clear]` | Clear current session history |
 `[history]` | Show current session history |

### Other

| Command | Description |
|---------|-------------|
 `[help]` | Show help |
 `[exit]` | Quit PollenChat (auto-saves all sessions) |

## Directories

PollenChat creates the following directories in its working folder:

- `sessions/` — Saved session JSON files
- `pollen_images/` — Generated images
- `pollen_codes/` — Extracted code blocks
- `pollen_exports/` — Exported Markdown conversations
- `config.json` — User preferences (model, system prompt, username, etc.)

## Session Management Details

PollenChat supports multiple parallel conversation sessions. Each session is an independent conversation history.

- **Auto-load**: On startup, all `.json` files in `sessions/` are automatically loaded as sessions.
- **Auto-save**: On exit (`[exit]` or Ctrl+D), all sessions are automatically saved back to `sessions/`.
- **Current session indicator**: The prompt shows the active session name: `User[work] :`
- **Session-agnostic config**: `model`, `system_prompt`, `temperature`, and `max_tokens` are global settings shared across all sessions.

## Image Generation

Inside `[image]` mode you can:

- Type a prompt to generate an image
- Use `[size]` to change width/height (default 1024x1024, range 64–4096)
- Use `[seed]` to fix a random seed for reproducible images
- Type `exit` to return to chat mode

## Importing Files

`[import]` reads `.md` or `.txt` files and sends them as a user message. You can optionally append a question after the file content. Files larger than 200 KB trigger a confirmation prompt to avoid accidentally sending huge payloads.

## Token Estimate

`[token]` provides a rough token count based on character counts:

- ASCII characters: ~4 chars per token
- Non-ASCII characters: ~1.5 chars per token

This is only an approximation. Actual token counts depend on the model's tokenizer.

## Notes

- PollinationsAI has rate limits on its free tier. If you see HTTP 429, wait a moment and retry.
- The `max_tokens` parameter is optional; if unset, the server default is used.
- Image generation parameters (width, height, seed) are session-only and not persisted to `config.json`.
- Session files store model, username, system prompt, temperature, max_tokens, and conversation history.

## License

MIT License — feel free to use, modify, and distribute.
