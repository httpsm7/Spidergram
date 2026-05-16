# 🕷 Spidergram v2

> **Autonomous multi-agent Instagram news automation engine** — runs locally on Ollama, manages 5+ AI agents, produces full video reels, and publishes automatically.

---

## ⚡ Quick Start

```bash
# 1. Clone
git clone https://github.com/your-org/spidergram.git && cd spidergram

# 2. One-command install (handles everything)
python install.py

# 3. Add your API keys
nano .env
# OR open http://localhost:7111/keys after starting

# 4. Start (scheduler + web dashboard)
source venv/bin/activate
python main.py --both
```

Open **http://localhost:7111** for the control panel.

---

## 🧠 Architecture

```
                    ┌─────────────────────────────┐
                    │        CEO Brain             │
                    │  (Ollama + Grok fallback)    │
                    │  • Strategy & decisions      │
                    │  • Code self-modification    │
                    │  • Agent management          │
                    └────────────┬────────────────┘
                                 │
               ┌─────────────────┼────────────────────┐
               │          Orchestrator                 │
               │   Task Queue · Scheduler · Telegram   │
               └──┬────┬────┬────┬──────────┬──────────┘
                  │    │    │    │          │
            ┌─────▼┐ ┌─▼──┐ ┌─▼──┐ ┌─────▼┐ ┌─▼─────┐
            │World │ │IND │ │POL │ │ BIZ  │ │ GEN   │
            │News  │ │News│ │News│ │ News │ │ News  │
            └──────┘ └────┘ └────┘ └──────┘ └───────┘
                           │
          ┌────────────────▼─────────────────────────┐
          │            Content Pipeline               │
          │  Fetch → Dedup → Script → Media → Voice   │
          │  → Video → Subtitles → Publish            │
          └──────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
spidergram/
├── main.py                    # Entry point — all CLI modes
├── install.py                 # One-command automated installer
├── requirements.txt
│
├── core/
│   ├── ceo_brain.py           # Master AI controller (Ollama + Grok)
│   └── orchestrator.py        # Scheduler + task queue + Telegram
│
├── agents/
│   ├── agent_template.py      # Base agent (memory, queue, pipeline)
│   └── agent_manager.py       # Create / edit / delete agents
│
├── pipeline/
│   ├── news_fetcher.py        # Step 1-3: Fetch + store
│   ├── deduplicator.py        # Hash + semantic dedup engine
│   ├── script_engine.py       # Step 4: LLM script generation
│   ├── media_fetcher.py       # Step 5: Pexels images/video
│   ├── tts_engine.py          # Step 6: ElevenLabs voice
│   ├── video_engine.py        # Step 7: MoviePy full reel
│   ├── subtitle_engine.py     # Step 8: Auto subtitles
│   └── publisher.py           # Step 10: CDN + Instagram Reels
│
├── integrations/
│   ├── newsapi.py             # NewsAPI.org
│   ├── gnews.py               # GNews fallback
│   ├── pexels.py              # Free images/video
│   ├── elevenlabs.py          # AI voice TTS
│   ├── grok.py                # xAI Grok fallback LLM
│   └── instagram.py           # Graph API publisher
│
├── ui/
│   ├── web_dashboard/
│   │   ├── app.py             # Flask app (port 7111)
│   │   ├── templates/         # Dashboard, Agents, Logs, Analytics, Keys
│   │   └── static/            # CSS + JS
│   └── chat_interface/
│       └── chat.py            # Terminal CEO Brain chat
│
├── database/
│   └── models.py              # SQLite: News, Scripts, Media, Posts, Analytics
│
├── utils/
│   ├── logger.py
│   ├── security.py            # Fernet-encrypted key storage
│   └── helpers.py
│
├── self_modify/
│   ├── code_reader.py         # Read own source modules
│   └── code_modifier.py       # Safely apply AI-suggested changes
│
├── modelfiles/                # Ollama Modelfiles (one per persona)
│   ├── CEO.Modelfile
│   ├── WorldNews.Modelfile
│   ├── IndiaNational.Modelfile
│   ├── IndianPolitics.Modelfile
│   ├── BusinessNews.Modelfile
│   └── GeneralNews.Modelfile
│
└── config/
    ├── settings.py
    └── agents.json            # Agent configurations (editable at runtime)
```

---

## 🖥 CLI Reference

| Command | Description |
|---|---|
| `python main.py` | Run all agents once right now |
| `python main.py --both` | Scheduler + dashboard (production) |
| `python main.py --scheduled` | Time-based scheduler only |
| `python main.py --dashboard` | Web dashboard only |
| `python main.py --chat` | Terminal chat with CEO Brain |
| `python main.py --agent world_news` | Run one specific agent |
| `python main.py --dry-run` | Full pipeline, skip Instagram |
| `python main.py --install-models` | Register Modelfiles with Ollama |
| `python main.py --report` | Send Telegram nightly report now |

---

## 💬 CEO Brain Commands (chat or dashboard)

```
Create a new agent for cricket news
Show all agents
Set NEWSAPI_KEY to abc123xyz
Run the business_news agent
Improve video quality in pipeline/video_engine.py
Show performance report
Edit india_politics agent prompt
Delete general_news agent
Set Instagram credentials for world_news
```

---

## 🤖 Default Agents (5)

| ID | Name | Niche |
|---|---|---|
| `world_news` | WorldNewsAgent | Global news |
| `india_national` | IndiaNationalNewsAgent | India news |
| `india_politics` | IndianPoliticsAgent | Indian politics |
| `business_news` | BusinessNewsAgent | Business & finance |
| `general_news` | GeneralNewsAgent | Trending topics |

---

## 🔌 Required API Keys

| Key | Service | Cost |
|---|---|---|
| `NEWSAPI_KEY` | newsapi.org | Free tier |
| `GNEWS_API_KEY` | gnews.io | Free tier |
| `PEXELS_API_KEY` | pexels.com/api | Free |
| `ELEVENLABS_API_KEY` | elevenlabs.io | Free tier |
| `GROK_API_KEY` | x.ai | Paid |
| `CLOUDINARY_*` | cloudinary.com | Free tier |
| `TELEGRAM_BOT_TOKEN` | t.me/BotFather | Free |

Instagram credentials go in `config/agents.json` per account.

---

## 🛡 Failsafe Logic

| Failure | Fallback |
|---|---|
| NewsAPI fails | → GNews API |
| ElevenLabs fails | → pyttsx3 offline TTS |
| Ollama fails | → Grok API |
| Video has no images | → Pexels background video |
| Background video fails | → Solid colour background |
| CDN upload fails | → Error logged, post skipped |

---

## 🔒 Security

- All API keys stored **Fernet-encrypted** in `data/db/keys.enc`
- `.env` file never committed (`.gitignore`)
- Code self-modification creates **timestamped backups** before any change
- Syntax validation runs before applying any modified code
