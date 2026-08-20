# Local AI Assistant

A fully private chatbot that runs entirely on your own machine, powered by
[Ollama](https://ollama.com). Nothing is sent to the cloud — no API keys,
no usage costs, no data leaving your device. Chat history is stored in a
local SQLite file (`chat_history.db`) next to the app.

Stack: **Python (Flask) + Ollama**, plain HTML/CSS/JS frontend with
streaming responses.

---

## 1. Install Ollama

Ollama is the engine that actually runs the LLM locally (it wraps
llama.cpp under the hood).

- **macOS / Windows**: download the installer from https://ollama.com/download
- **Linux**:
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ```

Verify it's installed:
```bash
ollama --version
```

## 2. Pull a model

Pick a model that fits your machine's RAM. Good starting points:

| Model | Pull command | Rough RAM needed |
|---|---|---|
| Llama 3.2 (3B) | `ollama pull llama3.2` | ~4 GB |
| Phi-3.5 mini | `ollama pull phi3.5` | ~4 GB |
| Mistral 7B | `ollama pull mistral` | ~8 GB |
| Llama 3.1 8B | `ollama pull llama3.1` | ~8 GB |

```bash
ollama pull llama3.2
```

Start the Ollama server (skip this if the desktop app is already running —
it starts the server automatically):
```bash
ollama serve
```
It listens on `http://localhost:11434` by default.

## 3. Set up the Python app

```bash
cd local-ai-assistant

# create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

## 4. Run it

```bash
python app.py
```

Open **http://localhost:5000** in your browser. That's it — you're
chatting with a model running entirely on your own hardware.

If the app can't reach Ollama, it'll show a banner telling you to run
`ollama serve`.

---

## Configuration

Open `app.py` and adjust the top of the file if needed:

```python
OLLAMA_URL = "http://localhost:11434"   # change if Ollama runs elsewhere
DEFAULT_MODEL = "llama3.2"              # must match a model you've pulled
```

The model dropdown in the UI is populated automatically from whatever
models you've pulled (`ollama list`), so you can switch models per
conversation without touching code.

---

## How it works

- `app.py` — Flask server. Exposes:
  - `GET /` — serves the chat UI
  - `GET /api/status` — checks if Ollama is running + lists available models
  - `GET /api/history/<session_id>` — loads saved conversation
  - `POST /api/clear/<session_id>` — wipes a conversation
  - `POST /api/chat` — sends the message + history to Ollama's
    `/api/chat` endpoint and streams the reply back token-by-token via
    Server-Sent Events
- `chat_history.db` — SQLite file created on first run, stores every
  message per browser session (identified by a random ID kept in
  `localStorage`) so refreshing the page keeps your conversation.
- `templates/`, `static/` — the frontend (no frameworks, just vanilla
  JS/CSS for a small footprint).

---

## Running it as a persistent local service (optional)

If you want the assistant always available in the background instead of
running `python app.py` manually each time:

**macOS/Linux — using a simple `systemd` service (Linux):**
```ini
# /etc/systemd/system/local-ai-assistant.service
[Unit]
Description=Local AI Assistant
After=network.target

[Service]
WorkingDirectory=/path/to/local-ai-assistant
ExecStart=/path/to/local-ai-assistant/venv/bin/python app.py
Restart=on-failure
User=your-username

[Install]
WantedBy=multi-user.target
```
Then:
```bash
sudo systemctl enable --now local-ai-assistant
```

**Any OS — using `pm2` (if you have Node.js installed):**
```bash
npm install -g pm2
pm2 start app.py --interpreter python3 --name local-ai-assistant
pm2 save
```

**Docker (optional):** since Ollama itself needs GPU/CPU access to the
host, it's simplest to keep Ollama running natively and only containerize
the Flask app if you want. A basic `Dockerfile` for the Flask side:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
```
Run with `--network host` (Linux) so it can reach Ollama on
`localhost:11434`, or point `OLLAMA_URL` at your host machine's IP.

---

## Troubleshooting

- **"Ollama isn't running"** → run `ollama serve` in a terminal, or open
  the Ollama desktop app, then refresh the page.
- **Model dropdown is empty** → you haven't pulled a model yet: run
  `ollama pull llama3.2`.
- **Slow responses** → try a smaller model (3B instead of 7B/8B), or
  close other heavy apps — everything runs on your CPU/GPU locally.
- **Port 5000 already in use** → change `port=5000` at the bottom of
  `app.py`.
