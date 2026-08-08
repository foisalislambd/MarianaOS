# MROS — Multi-channel Remote OS Agent

Telegram থেকে তোমার Windows PC control করার advanced AI agent।  
Tool-calling দিয়ে Cursor IDE, files, screenshot+vision, mouse/keyboard — সব করতে পারে।  
ভবিষ্যতে Web ও WhatsApp channel যোগ করার architecture আছে।

## Features

- **Telegram control** — chat দিয়ে PC চালাও (allowlist security)
- **30+ tools** — files, apps, Cursor IDE, windows, shell, clipboard, input
- **Screenshots + Vision** — স্ক্রিন দেখে বুঝে কাজ করে, শেষে তোমাকে screenshot পাঠায়
- **Cursor IDE** — folder open, chat/composer, model select, command palette
- **Extensible channels** — `channels/whatsapp_channel.py`, `channels/web_channel.py` stubs

## Quick start

### 1. Python venv + install

```powershell
cd C:\Users\ifois\Desktop\Windsurf\mros
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Telegram bot

1. Telegram-এ [@BotFather](https://t.me/BotFather) → `/newbot` → token নাও
2. Bot-এ `/start` দাও, তারপর [@userinfobot](https://t.me/userinfobot) থেকে নিজের numeric **user id** নাও

## LLM providers

`.env` এ শুধু `LLM_PROVIDER` + `LLM_API_KEY` সেট করলেই base URL ও default model অটো সেট হয়।

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

**Gemini (AI Studio) উদাহরণ:**

```env
LLM_PROVIDER=gemini
LLM_API_KEY=your_aistudio_key
# optional:
# LLM_MODEL=gemini-2.5-pro
# LLM_VISION_MODEL=gemini-2.5-flash
```

Key: [Google AI Studio](https://aistudio.google.com/apikey)

Screenshot analyze এর জন্য vision-capable model দরকার (`gemini-2.5-flash`, `gpt-4o`, Claude, Pixtral, ইত্যাদি)।

`LLM_BASE_URL` / `LLM_MODEL` / `LLM_VISION_MODEL` খালি রাখলে provider default ব্যবহার হয়; ভরলে override হয়।

### 4. Configure `.env`

```powershell
copy .env.example .env
notepad .env
```

অবশ্যই সেট করো:

- `LLM_PROVIDER` — যেমন `gemini`, `openai`, `openrouter`
- `LLM_API_KEY` — সেই provider-এর key
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USERS` ← তোমার Telegram user id
- `AGENT_WORKSPACE` ← default folder root
- `CURSOR_PATH` ← optional, auto-detect না হলে

### 5. Run

```powershell
python main.py
```

### List models (model ID দেখতে)

```powershell
python list_models.py --list
python list_models.py gemini
python list_models.py openrouter --filter claude
python list_models.py openai --key sk-...
```

অথবা `list_models.bat` — দেখানো **Model ID** `.env`-এ `LLM_MODEL=` এ বসাও।

Telegram-এ bot-এ message পাঠাও:

- `open C:\Users\ifois\Desktop\Windsurf\mros in Cursor`
- `screenshot নাও, কি দেখা যাচ্ছে বলো`
- `Cursor এ claude sonnet model select করো`
- `Notepad খুলে Hello World লেখো`

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

- শুধু `TELEGRAM_ALLOWED_USERS`-এ থাকা id চালাতে পারবে
- Empty allowlist = সবাই block (safe default)
- Delete / shell tools marked destructive
- Agent PC-তে mouse/keyboard control করে — run করার সময় PC unlocked থাকা ভালো

## Example prompts (Bangla / English)

- `D ড্রাইভের Projects ফোল্ডার Cursor এ খোলো`
- `এখন screen এ কি আছে? screenshot নিয়ে বলো`
- `Cursor chat খুলে এই prompt দাও: refactor main.py`
- `Chrome এ github.com খোলো`
- `Desktop এ test.txt বানিয়ে লেখো hello`

## Future channels

`BaseChannel` implement করে Web (FastAPI+WS) বা WhatsApp (Cloud API) যোগ করো — agent/tools আলাদা থাকবে, শুধু channel বদলাবে।
