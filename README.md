# MarianaOS — Remote OS Agent (UI Automation + Telegram)

Windows desktop AI agent controlled from Telegram. Uses **UI Automation** for reliable UI work — not junk screenshots. LLM calls go through **httpx** (OpenAI-compatible), with **OpenRouter** as the recommended provider.

## Stack

| Package | Role |
|---------|------|
| `aiogram==3.31.0` | Telegram bot |
| `httpx==0.28.1` | LLM APIs (OpenRouter, OpenAI, …) |
| `uiautomation==2.0.29` | Windows UI Automation |
| `pillow==12.3.0` | Screenshots only when needed |
| `python-dotenv==1.2.4` | `.env` config |

## Features

- **Telegram Rich Markdown** — `sendRichMessage` (native Markdown headings/lists/code), HTML fallback
- **Live progress drafts** — `sendRichMessageDraft` while tools run
- **UI Automation first** — observe → click/type named controls (not junk screenshots)
- **Human-like agent loop** — plan, act, wait, recover, verify; concise rich replies
- **Cursor IDE tools** — model/effort/chats via `state.vscdb` (Python)
- **OpenRouter** (+ other OpenAI-compatible providers) via httpx tool calling

## Quick start

### 1. Install

```powershell
cd C:\Users\ifois\Desktop\Windsurf\MarianaOS
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Telegram bot

1. [@BotFather](https://t.me/BotFather) → `/newbot` → copy token  
2. Get your user id from [@userinfobot](https://t.me/userinfobot)

### 3. OpenRouter (recommended)

1. Create a key at [openrouter.ai/keys](https://openrouter.ai/keys)  
2. Copy `.env.example` → `.env`

```env
LLM_PROVIDER=openrouter
LLM_API_KEY=sk-or-...
LLM_MODEL=google/gemini-2.5-flash
LLM_VISION_MODEL=google/gemini-2.5-flash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_USERS=your_numeric_id
AGENT_WORKSPACE=C:\Users\ifois\Desktop
```

List models:

```powershell
python list_models.py openrouter --filter gemini
```

### 4. Run

Double-click `run.bat`, or:

```powershell
python main.py
```

## How the agent works (UI-first)

1. Prefer **UI Automation**: inspect tree → find named controls → click / set value  
2. Prefer dedicated tools (files, Cursor DB, shell) over mouse pixels  
3. **Screenshots are optional** — `take_screenshot(send_to_user=true)` only when you want the image back  

Example prompts:

- `open Notepad and type Hello World`
- `open this folder in Cursor: C:\Users\ifois\Desktop\Windsurf\MarianaOS`
- `select Claude Sonnet in Cursor`
- `what windows are open?`
- `take a screenshot` (explicit)

## Architecture

```
MarianaOS/
├── main.py
├── config/           # dotenv settings + provider presets (OpenRouter first)
├── core/             # agent loop + httpx LLM client
├── tools/            # filesystem, cursor, UI automation, input, …
├── channels/         # aiogram Telegram (+ stubs)
├── utils/win_ui.py   # uiautomation helpers
└── data/screenshots/ # only when captured
```

## Safety

- Empty `TELEGRAM_ALLOWED_USERS` → everyone blocked  
- Destructive tools can require `confirm=true`  
- Keep the PC unlocked while the agent runs (it drives UI / keyboard)

## Other providers

Set `LLM_PROVIDER` to `openai`, `groq`, `deepseek`, `mistral`, `xai`, `ollama`, or `lmstudio`.  
Aliases `gemini` / `anthropic` / `claude` resolve to **OpenRouter** (use OpenRouter model ids like `google/gemini-2.5-flash` or `anthropic/claude-sonnet-4`).
