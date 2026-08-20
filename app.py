"""
Local AI Assistant
-------------------
A fully private chatbot that runs entirely on your machine using Ollama.
No API keys, no data leaving your device, no usage costs.

Run:
    python app.py

Then open http://localhost:5000 in your browser.
"""

import json
import time
import sqlite3
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, request, render_template

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"          # change to any model you've pulled with `ollama pull <name>`
DB_PATH = Path(__file__).parent / "chat_history.db"

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Storage (local SQLite - stays on disk, never leaves the machine)
# ---------------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_message(session_id, role, content):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO conversations (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (session_id, role, content, time.time()),
    )
    conn.commit()
    conn.close()


def get_history(session_id, limit=30):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY id ASC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()
    return [{"role": r, "content": c} for r, c in rows]


def clear_history(session_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Ollama helpers
# ---------------------------------------------------------------------------
def ollama_is_running():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False


def list_local_models():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except requests.exceptions.RequestException:
        return []


def stream_chat(model, messages):
    """Streams tokens from Ollama's /api/chat endpoint as they're generated."""
    payload = {"model": model, "messages": messages, "stream": True}
    with requests.post(f"{OLLAMA_URL}/api/chat", json=payload, stream=True, timeout=300) as r:
        if r.status_code != 200:
            # Ollama puts the real reason in the response body (e.g. "model not found",
            # out-of-memory, etc.) - surface that instead of a bare "500" error.
            try:
                body = r.json()
                detail = body.get("error", r.text)
            except ValueError:
                detail = r.text or f"HTTP {r.status_code}"
            raise RuntimeError(f"Ollama error: {detail}")
        for line in r.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            if "error" in chunk:
                raise RuntimeError(f"Ollama error: {chunk['error']}")
            token = chunk.get("message", {}).get("content", "")
            if token:
                yield token
            if chunk.get("done"):
                break


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", default_model=DEFAULT_MODEL)


@app.route("/api/status")
def status():
    return jsonify({
        "ollama_running": ollama_is_running(),
        "models": list_local_models(),
    })


@app.route("/api/history/<session_id>")
def history(session_id):
    return jsonify(get_history(session_id))


@app.route("/api/clear/<session_id>", methods=["POST"])
def clear(session_id):
    clear_history(session_id)
    return jsonify({"ok": True})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    session_id = data.get("session_id", "default")
    user_message = data.get("message", "").strip()
    model = data.get("model") or DEFAULT_MODEL

    if not user_message:
        return jsonify({"error": "empty message"}), 400

    if not ollama_is_running():
        return jsonify({
            "error": "Ollama isn't running. Start it with `ollama serve` (or open the Ollama app) and try again."
        }), 503

    save_message(session_id, "user", user_message)
    conversation = get_history(session_id)

    def generate():
        full_reply = ""
        try:
            for token in stream_chat(model, conversation):
                full_reply += token
                yield f"data: {json.dumps({'token': token})}\n\n"
        except (requests.exceptions.RequestException, RuntimeError) as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if full_reply:
                save_message(session_id, "assistant", full_reply)
            yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    init_db()
    print("Local AI Assistant starting at http://localhost:5000")
    print(f"Default model: {DEFAULT_MODEL}  (change with the dropdown, or edit DEFAULT_MODEL in app.py)")
    if not ollama_is_running():
        print("\n⚠️  Ollama doesn't seem to be running yet.")
        print("   Start it with: ollama serve   (or launch the Ollama desktop app)\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
