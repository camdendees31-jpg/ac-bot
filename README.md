# Animal Company Discord Bot — Full Setup

Two Railway services: a **FastAPI backend** (web) and a **Discord bot** (worker). Both always online.

## What the commands do

| Command | What it does |
|---|---|
| `/get-auth <pairing_code>` | Registers your AC in-game pairing code → generates and returns your personal API key |
| `/get-api` | Shows your registered pairing code, API key, and account info |

The pairing code is shown on the **in-game computer → Pair screen**. It links the companion app to your VR headset.

---

## Why we built our own backend

Animal Company uses **Heroic Cloud Nakama** as their game backend (confirmed in their privacy policy). Their Nakama server URL and server key are private — there's no public API. So we built our own backend that registers users and issues API keys instead.

---

## Project structure

```
ac-bot/
├── backend/
│   ├── main.py          ← FastAPI app
│   └── requirements.txt
├── bot/
│   ├── bot.py           ← Discord bot
│   └── requirements.txt
└── README.md
```

---

## Deploy on Railway — Step by Step

### Step 1: Push to GitHub

Push the whole `ac-bot/` folder to a GitHub repo.

### Step 2: Create the backend service

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select your repo, set the **Root Directory** to `backend`
3. Railway auto-detects Python — set the **Start Command** to:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
4. In **Variables**, add:
   ```
   INTERNAL_KEY=pick-a-long-random-secret-here
   DB_PATH=/data/ac_bot.db
   ```
5. Under **Settings → Volumes**, add a volume mounted at `/data` (keeps DB across deploys)
6. Hit **Deploy** — copy the generated `*.up.railway.app` URL

### Step 3: Create the bot service

1. In the same Railway project, click **+ New Service** → **GitHub Repo** (same repo)
2. Set **Root Directory** to `bot`
3. Set **Start Command** to:
   ```
   python bot.py
   ```
4. In **Variables**, add:
   ```
   DISCORD_TOKEN=your_discord_bot_token
   API_BASE_URL=https://your-backend.up.railway.app
   INTERNAL_KEY=same-secret-as-backend
   ```
5. Hit **Deploy**

That's it — both services run 24/7 on Railway. The bot restarts automatically if it crashes.

---

## Environment variables summary

### Backend service
| Variable | Description |
|---|---|
| `INTERNAL_KEY` | Secret shared between bot and backend |
| `DB_PATH` | Path to SQLite DB (use `/data/ac_bot.db` with a Railway volume) |

### Bot service
| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Your Discord bot token |
| `API_BASE_URL` | URL of your deployed backend service |
| `INTERNAL_KEY` | Same secret as backend |

---

## Test it locally

```bash
# Terminal 1 — backend
cd backend
pip install -r requirements.txt
INTERNAL_KEY=test uvicorn main:app --reload

# Terminal 2 — bot
cd bot
pip install -r requirements.txt
# create bot/.env with DISCORD_TOKEN, API_BASE_URL=http://localhost:8000, INTERNAL_KEY=test
python bot.py
```

---

## Future: if you ever find the real AC API endpoints

You can extend the backend (`backend/main.py`) to forward requests to Animal Company's Nakama server after validating the pairing code. The Nakama custom auth endpoint is typically:
```
POST https://<nakama-host>/v2/account/authenticate/custom
Authorization: Basic base64(serverKey:)
Body: {"id": "<pairing_code>"}
```
But you'd need their private Nakama host URL and server key (found by intercepting companion app traffic with Charles Proxy or mitmproxy).
