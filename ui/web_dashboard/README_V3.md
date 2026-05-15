# Spidergram v3 — Dashboard Upgrade Notes

## What's New in v3

### 1. Loading Screen Animation
Spider-web SVG that draws itself on page load with Fernet-encrypted progress bar.

### 2. Water Jelly Glassmorphism UI
- `backdrop-filter: blur(24px)` on all cards
- CSS variables for full dark/light theme switching
- White border jelly buttons with spring-physics hover (cubic-bezier)

### 3. Real-time Log Polling  (`/api/logs`)
- Polls `/api/logs?since=<ts>` every 5 seconds
- New entries slide in with animation, auto-scroll
- Blinking green dot indicator when live

### 4. Video Preview Modal
- Click any log row → glassmorphism modal with HTML5 `<video>` player
- Shows agent, status, timestamp, caption
- Share / Copy Link buttons

### 5. Mobile Responsive
- Hamburger button toggles sidebar on < 768px
- Bottom nav bar with 5 tabs (Home, Agents, Logs, Stats, CEO)
- Sidebar overlay/backdrop on mobile

### 6. Notification Bell  (`/api/notifications`)
- Red badge count (unread)
- Glass dropdown with last 10 system events
- Polls every 30 seconds

### 7. Command Palette  (Cmd/Ctrl + K)
- Fuzzy search across pages, agents, commands
- Arrow key navigation, Enter to execute
- Commands: go to page, run agent, toggle theme, open CEO chat

### 8. Agent Scheduler Timeline
- Horizontal 00:00–24:00 time axis
- Each agent row shows colored blocks at scheduled post times
- Read from `agent.post_times` field

### 9. Instagram Reel Preview Modal
- Phone frame mockup with screen content
- Estimated engagement stats (likes, comments, saves, reach)
- Caption editor + Post Now / Copy Caption buttons

### 10. Theme Toggle (Dark/Light)
- Sun/moon icon in topbar
- CSS variables swap instantly with 0.4s transitions
- Preference saved to `localStorage`

### 11. System Health Widget  (`/api/health`)
- CPU %, RAM MB, Ollama latency ms, Disk GB
- Color-coded progress bars (green/yellow/red)
- Auto-updates every 10 seconds
- Uses `psutil` when installed, mock data otherwise

### 12. Analytics Export  (`/api/analytics/export`)
- `?fmt=csv` → downloads `spidergram_analytics.csv`
- `?fmt=pdf` → opens print-ready HTML report (auto-triggers print dialog)
- Canvas bar/line charts (no library dependency)

## New API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/logs?since=<ts>` | GET | New logs since unix timestamp |
| `/api/health` | GET | CPU / RAM / latency / disk |
| `/api/notifications` | GET | System event feed |
| `/api/analytics/export?fmt=csv` | GET | CSV download |
| `/api/analytics/export?fmt=pdf` | GET | PDF report |

## Install psutil (optional, for real health data)
```bash
pip install psutil --break-system-packages
```

## Run
```bash
python run.py
# Dashboard: http://localhost:7111
```
