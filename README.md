# MarianaOS

Windows desktop AI agent controlled from Telegram. Uses **UI Automation** first; screenshots only when needed. LLM via **httpx** (OpenRouter recommended).

## Setup

```powershell
cd C:\Users\ifois\Desktop\Windsurf\MarianaOS
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:

```env
LLM_PROVIDER=openrouter
LLM_API_KEY=sk-or-...
LLM_MODEL=google/gemini-2.5-flash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_USERS=your_numeric_id
AGENT_WORKSPACE=C:\Users\ifois\Desktop
```

List models: `python list_models.py openrouter`

## Run

```powershell
.\.venv\Scripts\python.exe main.py
```

Or double-click `run.bat`.

## Use

Telegram → `/start` → speak naturally, e.g.:

- `Open Notepad and type Hello`
- `Open C:\Users\…\project in Cursor`
- `What windows are open?`

While a task runs, tap **⏹ Stop** to cancel.

## Stack

`aiogram` · `httpx` · `uiautomation` · `pillow` · `python-dotenv`
