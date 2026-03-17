# PoC Chatbox

A minimal internal chatbox powered by Claude, with an admin panel to enable or disable skills.

---

## Project structure

```
poc-chatbox/
├── main.py              # FastAPI entry point
├── config.json          # Skill on/off state (auto-managed)
├── .env                 # API key + admin password (you create this)
├── requirements.txt     # Python dependencies
├── routers/
│   ├── chat.py          # POST /chat — handles user messages
│   └── admin.py         # POST /admin/login, /admin/skills — admin auth + config
├── agent/
│   └── engine.py        # Creates the deepagent, loads skills from config.json
├── skills/
│   └── web-crawler/     # Copy your skill folder here
│       ├── SKILL.md
│       ├── scripts/
│       └── references/
└── frontend/
    ├── chat.html        # User-facing chat page
    └── admin.html       # Admin config page (password protected)
```

---

## Setup

### 1. Clone or download the project

```bash
cd poc-chatbox
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate       # macOS / Linux
venv\Scripts\activate          # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create the `.env` file

Create a file named `.env` in the project root with the following content:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
ADMIN_PASSWORD=your-admin-password-here
```

- `ANTHROPIC_API_KEY` — your Anthropic API key. Get one at https://console.anthropic.com
- `ADMIN_PASSWORD` — the password to access the admin config page

### 5. Copy your skill into the project

```bash
cp -r /path/to/web-crawler skills/
```

The `skills/` folder should contain the skill folder directly:

```
skills/
└── web-crawler/
    ├── SKILL.md
    ├── scripts/
    └── references/
```

### 6. Start the server

```bash
uvicorn main:app --reload --port 8018
```

---

## Usage

### Chat page (all users)

Open your browser at:

```
http://localhost:8018
```

Type a message and press Enter to chat with the assistant.

### Admin config page

Open your browser at:

```
http://localhost:8018/admin
```

Enter the admin password to access the config panel.
From here you can enable or disable skills for all users.
Changes take effect immediately — no server restart needed.

---

## How it works

```
User types message
  → POST /chat
  → engine.py reads config.json
  → creates deepagent (with or without skills)
  → agent processes message
  → reply returned to browser
```

```
Admin changes skill toggle
  → POST /admin/skills (requires token)
  → config.json updated
  → next chat request picks up the change automatically
```

---

## Deployment (Render.com)

1. Push the project to a GitHub repository
2. Go to https://render.com and create a new **Web Service**
3. Connect your GitHub repo
4. Set the following:
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `uvicorn main:app --host 0.0.0.0 --port 8018`
5. Add environment variables in the Render dashboard:
   - `ANTHROPIC_API_KEY`
   - `ADMIN_PASSWORD`
6. Deploy

> Note: Render's free tier spins down after inactivity. The first request after a period of inactivity may take ~30 seconds to respond.

---

## Notes

- The admin token is stored in memory — it resets if the server restarts. The admin will need to log in again after a restart.
- `config.json` persists skill state across restarts.
- The `.env` file should never be committed to Git. Add it to `.gitignore`:

```
.env
__pycache__/
venv/
```
