# MarianaOS — Multi-channel Remote OS Agent

An advanced AI agent that controls your Windows PC from Telegram using tool calling.
It can drive Cursor IDE, manage files, take screenshots with vision, and control mouse/keyboard.
The architecture is ready for future Web and WhatsApp channels.

## Features

- **Telegram control** — chat to control your PC (allowlist security)
- **30+ tools** — files, apps, Cursor IDE, windows, shell, clipboard, input
- **Screenshots + Vision** — sees the screen, acts, then sends screenshots back to you
- **Cursor IDE** — open folders, chat/composer, model select, command palette
- **Extensible channels** — stubs in `channels/whatsapp_channel.py`, `channels/web_channel.py`

## Quick start

### 1. Python venv + install

```powershell
cd C:\Users\ifois\Desktop\Windsurf\MarianaOS
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Telegram bot

1. Open Telegram [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token
2. Start your bot with `/start`, then get your numeric **user id** from [@userinfobot](https://t.me/userinfobot)

## LLM providers

| `LLM_PROVIDER` | SDK / API | Notes |
|----------------|-----------|-------|
| `gemini` | **Native** `google-genai` | AI Studio — proper tool calling + thought signatures |
| `anthropic` | **Native** `anthropic` | Claude Messages + tool_use |
| `openai` | OpenAI SDK | Official Chat Completions |
| `openrouter` | OpenAI-compatible | Many models, one key |
| `groq` / `deepseek` / `mistral` / `xai` / … | OpenAI-compatible | Per each provider's OpenAI-compat docs |
| `ollama` / `lmstudio` | OpenAI-compatible | Local |

Set `LLM_PROVIDER` + `LLM_API_KEY`. Leave `LLM_MODEL` empty to use defaults.

### 4. Configure `.env`

```powershell
copy .env.example .env
notepad .env
```

Required:

- `LLM_PROVIDER` — e.g. `gemini`, `openai`, `openrouter`
- `LLM_API_KEY` — key for that provider
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USERS` — your Telegram user id
- `AGENT_WORKSPACE` — default folder root for relative paths
- `CURSOR_PATH` — optional; leave empty for auto-detect

### 5. Run

Double-click `run.bat` — it will:
1. Create `.venv` if missing
2. Activate the venv
3. Install dependencies if needed
4. Start MarianaOS

Or manually:

```powershell
python main.py
```

### List models (get model IDs)

```powershell
python list_models.py --list
python list_models.py gemini
python list_models.py openrouter --filter claude
python list_models.py openai --key sk-...
```

Or use `list_models.bat` — copy a **Model ID** into `.env` as `LLM_MODEL=`.

Message your Telegram bot, for example:

- `open C:\Users\ifois\Desktop\Windsurf\MarianaOS in Cursor`
- `take a screenshot and tell me what is on screen`
- `select the claude sonnet model in Cursor`
- `open Notepad and type Hello World`

## Architecture

```
MarianaOS/
├── main.py                 # Entrypoint
├── config/settings.py      # .env settings
├── core/
│   ├── agent.py            # Tool-calling agent loop
│   ├── llm.py              # Provider facade
│   └── memory.py           # Per-user chat memory
├── tools/                  # PC control tools
├── channels/
│   ├── telegram_channel.py # Live
│   ├── web_channel.py      # Stub (future)
│   └── whatsapp_channel.py # Stub (future)
├── data/screenshots/       # Captured screens
└── utils/
```

## Safety

- Only user IDs in `TELEGRAM_ALLOWED_USERS` can control the PC
- Empty allowlist = everyone blocked (safe default)
- Delete / shell tools are marked destructive
- The agent uses mouse/keyboard — keep the PC unlocked while it runs

## Example prompts

- `Open the Projects folder on D: in Cursor`
- `What is on screen right now? Take a screenshot and tell me`
- `Open Cursor chat and send this prompt: refactor main.py`
- `Open github.com in Chrome`
- `Create test.txt on the Desktop with hello`

## Future channels

Implement `BaseChannel` for Web (FastAPI + WebSocket) or WhatsApp (Cloud API). The agent and tools stay the same; only the channel changes.
