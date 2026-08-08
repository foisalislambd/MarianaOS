# MROS — Multi-channel Remote OS Agent

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
cd C:\Users\ifois\Desktop\Windsurf\mros
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Telegram bot

1. Open Telegram [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token
2. Start your bot with `/start`, then get your numeric **user id** from [@userinfobot](https://t.me/userinfobot)

## LLM providers

Set `LLM_PROVIDER` + `LLM_API_KEY` in `.env` and the base URL / default models are filled automatically.

| `LLM_PROVIDER` | Service | Default model |
|----------------|---------|---------------|
| `gemini` | Google AI Studio | `gemini-2.5-flash` |
| `openai` | OpenAI | `gpt-4o` |
| `anthropic` | Anthropic Claude | `claude-sonnet-4-5` |
| `openrouter` | OpenRouter | `google/gemini-2.5-flash` |
| `groq` | Groq | `llama-3.3-70b-versatile` |
| `deepseek` | DeepSeek | `deepseek-chat` |
| `mistral` | Mistral AI | `mistral-large-latest` |
| `xai` | xAI Grok | `grok-2-latest` |
| `together` | Together AI | Llama 3.1 70B |
| `fireworks` | Fireworks AI | Llama 3.3 70B |
| `ollama` | Ollama (local) | `llama3.2` |
| `lmstudio` | LM Studio (local) | `local-model` |
| `custom` | Any OpenAI-compatible URL | set `LLM_BASE_URL` |

**Gemini (AI Studio) example:**

```env
LLM_PROVIDER=gemini
LLM_API_KEY=your_aistudio_key
# optional:
# LLM_MODEL=gemini-2.5-pro
# LLM_VISION_MODEL=gemini-2.5-flash
```

Key: [Google AI Studio](https://aistudio.google.com/apikey)

Screenshot analysis needs a vision-capable model (`gemini-2.5-flash`, `gpt-4o`, Claude, Pixtral, etc.).

Leave `LLM_BASE_URL` / `LLM_MODEL` / `LLM_VISION_MODEL` empty to use provider defaults; set them to override.

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

- `open C:\Users\ifois\Desktop\Windsurf\mros in Cursor`
- `take a screenshot and tell me what is on screen`
- `select the claude sonnet model in Cursor`
- `open Notepad and type Hello World`

## Architecture

```
mros/
├── main.py                 # Entrypoint
├── config/settings.py      # .env settings
├── core/
│   ├── agent.py            # Tool-calling agent loop
│   ├── llm.py              # OpenAI-compatible client
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
