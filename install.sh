#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  Spidergram v3 — One-Command Install (Kali Linux / Ubuntu)
#  Run: chmod +x install.sh && bash install.sh
# ═══════════════════════════════════════════════════════════════
set -e
GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${CYAN}"
echo "  ███████╗██████╗ ██╗██████╗ ███████╗██████╗  ██████╗ ██████╗  █████╗ ███╗   ███╗"
echo "  ██╔════╝██╔══██╗██║██╔══██╗██╔════╝██╔══██╗██╔════╝ ██╔══██╗██╔══██╗████╗ ████║"
echo "  ███████╗██████╔╝██║██║  ██║█████╗  ██████╔╝██║  ███╗██████╔╝███████║██╔████╔██║"
echo "  ╚════██║██╔═══╝ ██║██║  ██║██╔══╝  ██╔══██╗██║   ██║██╔══██╗██╔══██║██║╚██╔╝██║"
echo "  ███████║██║     ██║██████╔╝███████╗██║  ██║╚██████╔╝██║  ██║██║  ██║██║ ╚═╝ ██║"
echo "  ╚══════╝╚═╝     ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝"
echo -e "  v3 — Autonomous AI News Engine${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Create virtual environment
echo -e "${GREEN}[1/7] Creating virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# 2. Upgrade pip
echo -e "${GREEN}[2/7] Upgrading pip...${NC}"
pip install --upgrade pip -q

# 3. Install Python dependencies
echo -e "${GREEN}[3/7] Installing Python dependencies...${NC}"
pip install -r requirements.txt --break-system-packages -q

# 4. Install Playwright browser
echo -e "${GREEN}[4/7] Installing Playwright Chromium...${NC}"
playwright install chromium 2>/dev/null || echo "  (Playwright install skipped — run manually: playwright install chromium)"

# 5. Create __init__.py files
echo -e "${GREEN}[5/7] Ensuring package structure...${NC}"
for pkg in ui "ui/web_dashboard" "ui/chat_interface" core database utils config agents; do
  [ ! -f "$pkg/__init__.py" ] && echo "# $pkg" > "$pkg/__init__.py"
done

# 6. Create data dirs
echo -e "${GREEN}[6/7] Creating data directories...${NC}"
mkdir -p data generated_images logs

# 7. Copy .env template
echo -e "${GREEN}[7/7] Checking .env...${NC}"
if [ ! -f ".env" ]; then
  cp .env.example .env 2>/dev/null || cat > .env << 'DOTENV'
FLASK_SECRET_KEY=spidergram_change_in_production
DASHBOARD_PORT=7111
OLLAMA_HOST=http://localhost:11434
NEWSAPI_KEY=
GNEWS_API_KEY=
PEXELS_API_KEY=
GROK_API_KEY=
ELEVENLABS_API_KEY=
CLOUDINARY_URL=
DOTENV
  echo -e "${YELLOW}  .env created — fill in your API keys!${NC}"
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ Spidergram v3 installed successfully!         ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  1. Edit .env with your API keys                  ║${NC}"
echo -e "${GREEN}║  2. Run tests:  bash test_and_fix.sh              ║${NC}"
echo -e "${GREEN}║  3. Start:      python main.py --both             ║${NC}"
echo -e "${GREEN}║  4. Dashboard:  http://localhost:7111             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
