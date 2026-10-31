# 🛡️ ScamShield OSS

Real-time **"Digital Arrest" scam call interceptor** and **forged warrant / predatory contract scanner**,
powered entirely by open-source models. No paid API keys.

| Panel | What it does | Model |
|---|---|---|
| Live call interceptor | Transcribes speakerphone audio in 5-second chunks | `faster-whisper` large-v3-turbo |
| Coercion meter | Scores scam probability, lists manipulation tactics, maps to BNS / IT Act sections | `qwen3:8b` via Ollama |
| Document scanner | Flags forged seals and predatory clauses with bounding boxes, drafts a 1930 NCRP counter-notice | `qwen2.5vl:7b` via Ollama |

Every analysed call and scanned document is saved to a local SQLite database (`GET /history`).

## Architecture

```
Browser (frontend/index.html, served on localhost)
        │  HTTPS + header ngrok-skip-browser-warning
        ▼
   ngrok tunnel  ───►  FastAPI (backend/main.py, port 8000)  ───►  Ollama (127.0.0.1:11434)
                              │                                      ├─ qwen3:8b
                              ├─ faster-whisper (GPU)                └─ qwen2.5vl:7b
                              └─ SQLite (scamshield.db)
```

The backend runs on a free GPU notebook (Kaggle **T4 x2** recommended, Colab T4 also works).
The dashboard runs on your laptop and talks to the notebook through an ngrok tunnel.

## Repo layout

```
frontend/index.html                  single-file dashboard (Tailwind CDN, pdf.js for PDF upload)
backend/main.py                      FastAPI app
backend/database.py, models.py       SQLite via SQLModel
backend/requirements.txt
notebooks/scamshield_kaggle.ipynb    ordered setup cells for Kaggle
```

## Quick start

### 1. Backend on Kaggle
1. Create a free account at [ngrok](https://dashboard.ngrok.com) and copy your **authtoken**.
2. Push this repo to GitHub, then edit `REPO_URL` in the notebook's clone cell.
3. In Kaggle: **New Notebook → File → Import Notebook** and upload `notebooks/scamshield_kaggle.ipynb`.
4. Settings: **Accelerator = GPU T4 x2**, **Internet = On**, and verify your phone number if Kaggle asks.
5. **Add-ons → Secrets**: add `NGROK_TOKEN` with your authtoken and tick it for this notebook.
6. Run the cells **in order, one at a time**, and wait for each to finish. Model downloads take several minutes.
7. The last cell prints your public URL, e.g. `https://xxxx.ngrok-free.dev`.

> Do not stop or interrupt cells once the server is running, and keep the Kaggle tab open.

### 2. Frontend on your laptop
```bash
cd frontend
python -m http.server 5500 --bind 127.0.0.1
```
Open <http://localhost:5500>, paste the ngrok URL into the box (no `/docs`, no trailing slash), click **Save**.
Serve over `localhost` (not `file://`) so the browser allows microphone access.

### 3. Try it
- **⚡ Stage Scam Demo**: sends a simulated scam call (zero-risk fallback if the room is noisy).
- **Start Live Mic**: play a scam script from a phone speaker near the laptop.
- **Upload Document**: image or PDF (page 1) of a fake notice or contract.

Warm up each feature once before presenting; the first model call is slow.

## API

| Method | Path | Notes |
|---|---|---|
| POST | `/analyze-call` | form: `audio` (webm chunk) **or** `fallback_text` |
| POST | `/scan-document` | form: `file` (image) |
| GET | `/history?limit=10` | latest calls and scanned documents |
| GET | `/health` | Ollama reachability and installed models |

Interactive docs live at `<your-url>/docs`.

## Troubleshooting (all hit during development)

| Symptom | Cause / fix |
|---|---|
| Ollama installer says it needs **zstd** | `apt-get install zstd` first (let it finish, do not interrupt) |
| `Failed to connect to Ollama` | Python client cannot use `0.0.0.0`; use `127.0.0.1:11434` (already the default here). Also make sure `ollama serve` is running, which the notebook's watchdog cell handles |
| Ollama keeps dying | Stopping or interrupting a cell kills child processes. The notebook starts Ollama detached (`start_new_session=True`) with a watchdog |
| ngrok `endpoint already online` (ERR_NGROK_334) | Old tunnel still alive: `ngrok.kill()`, or disconnect the session at dashboard.ngrok.com → Agents |
| ngrok `Authtoken already set` | The notebook deletes the old config before setting the token |
| ngrok `ERR_NGROK_8012` / connection refused | Server is not listening on 8000, or ngrok points at an IPv6 `localhost`. Tunnel to `http://127.0.0.1:8000` |
| Browser shows `Failed to fetch` | Usually a server-side 500 without CORS headers. Check the notebook output; `GET /health` shows whether Ollama is up |
| `asyncio.run() cannot be called from a running event loop` | Do not call `uvicorn.run` inside a notebook; the notebook runs uvicorn in a background thread |
| Calls from the browser blocked by ngrok warning page | Send header `ngrok-skip-browser-warning: true` (the dashboard does) |

## Security notes

- **Never commit your ngrok authtoken.** Use Kaggle Secrets (`UserSecretsClient`). If a token leaks, reset it in the ngrok dashboard.
- The dashboard is for demos: the API has open CORS and no authentication. Do not expose it long-term.
- Output is AI-generated and can be wrong. It is an awareness tool, not legal advice. If you receive a suspected digital arrest call, hang up and report at **1930** / <https://cybercrime.gov.in>.

## License

MIT, see [LICENSE](LICENSE).
