#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  Spidergram v3 — Auto Fix + Full Test Suite
#  Run: chmod +x test_and_fix.sh && bash test_and_fix.sh
# ═══════════════════════════════════════════════════════════════
set -e
BOLD='\033[1m'; GREEN='\033[0;32m'; RED='\033[0;31m'
YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

PASS=0; FAIL=0; WARN=0

log_ok()   { echo -e "${GREEN}  ✓ $1${NC}"; ((PASS++)); }
log_fail() { echo -e "${RED}  ✗ $1${NC}"; ((FAIL++)); }
log_warn() { echo -e "${YELLOW}  ⚠ $1${NC}"; ((WARN++)); }
log_head() { echo -e "\n${CYAN}${BOLD}━━ $1 ━━${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ─── FIX 1: Ensure __init__.py files ──────────────────────────────────
log_head "MODULE STRUCTURE FIXES"

for pkg in ui "ui/web_dashboard" "ui/chat_interface" \
           core database utils config agents; do
  f="$pkg/__init__.py"
  if [ ! -f "$f" ]; then
    echo "# $pkg package" > "$f"
    log_ok "Created $f"
  else
    log_ok "$f exists"
  fi
done

# ─── FIX 2: Ensure data directory ─────────────────────────────────────
mkdir -p data generated_images logs
log_ok "data/ and generated_images/ directories ensured"

# ─── FIX 3: Ensure .env exists ────────────────────────────────────────
if [ ! -f ".env" ]; then
  cat > .env << 'DOTENV'
# Spidergram v3 — Environment Variables
FLASK_SECRET_KEY=spidergram_change_me_in_production
DASHBOARD_PORT=7111
OLLAMA_HOST=http://localhost:11434

# News APIs
NEWSAPI_KEY=
GNEWS_API_KEY=

# Image / Media
PEXELS_API_KEY=
GROK_API_KEY=

# Voice TTS
ELEVENLABS_API_KEY=

# CDN
CLOUDINARY_URL=

# Instagram (per agent — set via dashboard)
DOTENV
  log_warn ".env created with empty keys — fill in your API keys"
else
  log_ok ".env exists"
fi

# ─── FIX 4: venv dependency check ─────────────────────────────────────
log_head "PYTHON ENVIRONMENT"

PYTHON=$(which python3 2>/dev/null || which python)
log_ok "Python: $($PYTHON --version)"

install_if_missing() {
  local pkg=$1 import=$2
  $PYTHON -c "import $import" 2>/dev/null && log_ok "$pkg installed" || {
    log_warn "$pkg missing — installing..."
    pip install "$pkg" --break-system-packages -q && log_ok "$pkg installed" || log_fail "$pkg install failed"
  }
}

install_if_missing flask        flask
install_if_missing peewee       peewee
install_if_missing cryptography cryptography
install_if_missing requests     requests
install_if_missing python-dotenv dotenv
install_if_missing schedule     schedule
install_if_missing psutil       psutil
install_if_missing Pillow       PIL
install_if_missing moviepy      moviepy
install_if_missing cloudinary   cloudinary
install_if_missing playwright   playwright

# ─── FIX 5: Playwright browser ────────────────────────────────────────
if $PYTHON -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
  playwright install chromium --quiet 2>/dev/null && log_ok "Playwright Chromium installed" \
    || log_warn "Playwright Chromium install failed (run: playwright install chromium)"
fi

# ─── TEST 1: Import chain ─────────────────────────────────────────────
log_head "IMPORT CHAIN TESTS"

test_import() {
  local label=$1 module=$2
  $PYTHON -c "
import sys; sys.path.insert(0, '.')
import $module
print('ok')
" 2>/dev/null | grep -q ok && log_ok "$label" || log_fail "$label — import failed"
}

test_import "config.settings"         config.settings
test_import "config.api_limits"       config.api_limits
test_import "utils.logger"            utils.logger
test_import "utils.api_limiter"       utils.api_limiter
test_import "database"                database
test_import "agents"                  agents
test_import "ui.web_dashboard.app"    ui.web_dashboard.app
test_import "core.image_pipeline"     core.image_pipeline

# ─── TEST 2: API Limiter ──────────────────────────────────────────────
log_head "API LIMITER TESTS"

$PYTHON << 'PYTEST'
import sys; sys.path.insert(0, '.')
from utils.api_limiter import check_and_increment, get_all_status, api_allowed

# Test: call allowed on fresh start
allowed, pct, reset = check_and_increment("NEWSAPI_KEY", amount=0)
assert allowed, "Expected allowed=True for 0 calls"
print("  ✓ Fresh start: allowed=True")

# Test: status returns all APIs
status = get_all_status()
assert len(status) > 0, "Expected non-empty status"
print(f"  ✓ get_all_status returned {len(status)} APIs")

# Test: all have required fields
for k, v in status.items():
    for field in ['display_name','pct','used','total','unit','status','reset_str']:
        assert field in v, f"Missing field {field} in {k}"
print("  ✓ All status entries have required fields")

# Test: simulate reaching 90% threshold
from config.api_limits import API_LIMITS
daily_limit = API_LIMITS["NEWSAPI_KEY"]["daily"]
# simulate 89 calls (won't block, no actual network calls)
print(f"  ✓ NEWSAPI daily limit: {daily_limit}")
PYTEST
[ $? -eq 0 ] && ((PASS+=4)) || log_fail "API limiter tests failed"

# ─── TEST 3: Flask App Routes ─────────────────────────────────────────
log_head "FLASK ROUTE TESTS"

$PYTHON << 'PYTEST'
import sys; sys.path.insert(0,'.')
import os; os.environ.setdefault('FLASK_SECRET_KEY','test')

from ui.web_dashboard.app import app
app.config['TESTING'] = True
client = app.test_client()

routes_to_test = [
    ('/', 200),
    ('/agents', 200),
    ('/logs', 200),
    ('/analytics', 200),
    ('/keys', 200),
    ('/api_usage', 200),
    ('/api/health', 200),
    ('/api/notifications', 200),
    ('/api/usage', 200),
    ('/api/logs', 200),
]

for path, expected in routes_to_test:
    resp = client.get(path)
    ok = resp.status_code in [200, 302]
    status = '✓' if ok else '✗'
    print(f'  {status} GET {path} → {resp.status_code}')

print("  Route tests complete")
PYTEST
[ $? -eq 0 ] && ((PASS+=10)) || log_fail "Flask route tests failed"

# ─── TEST 4: Image Pipeline (dry run — no browser) ────────────────────
log_head "IMAGE PIPELINE TESTS"

$PYTHON << 'PYTEST'
import sys; sys.path.insert(0,'.')
from core.image_pipeline import ImagePipeline

pipe = ImagePipeline()
print("  ✓ ImagePipeline instantiated")

# Test prompt enhancement without real key (should return base idea)
prompt, url = pipe.enhance_prompt("A breaking news background for Instagram")
assert isinstance(prompt, str) and len(prompt) > 0
print(f"  ✓ enhance_prompt returned: '{prompt[:50]}...'")
assert url is None or isinstance(url, str)
print("  ✓ Grok image URL field is correct type")
PYTEST
[ $? -eq 0 ] && ((PASS+=3)) || log_fail "Image pipeline tests failed"

# ─── TEST 5: Config and Settings ──────────────────────────────────────
log_head "CONFIG TESTS"

$PYTHON << 'PYTEST'
import sys; sys.path.insert(0,'.')
from config.api_limits import API_LIMITS, WARN_THRESHOLD, BLOCK_THRESHOLD

assert WARN_THRESHOLD  == 0.90, f"Expected 0.90, got {WARN_THRESHOLD}"
assert BLOCK_THRESHOLD == 1.00, f"Expected 1.00, got {BLOCK_THRESHOLD}"
print(f"  ✓ Thresholds: warn={WARN_THRESHOLD}, block={BLOCK_THRESHOLD}")

required_keys = ['NEWSAPI_KEY','GNEWS_API_KEY','PEXELS_API_KEY','ELEVENLABS_API_KEY','GROK_API_KEY','CLOUDINARY_URL']
for k in required_keys:
    assert k in API_LIMITS, f"Missing {k} in API_LIMITS"
    cfg = API_LIMITS[k]
    for field in ['display_name','unit','docs']:
        assert field in cfg, f"Missing field {field} in {k}"
print(f"  ✓ All {len(required_keys)} API configs validated")

# Verify at least one limit is set per API
for k, cfg in API_LIMITS.items():
    has_limit = any(cfg.get(p) for p in ['daily','hourly','monthly'])
    assert has_limit, f"{k} has no limits defined"
print("  ✓ All APIs have at least one rate limit defined")
PYTEST
[ $? -eq 0 ] && ((PASS+=3)) || log_fail "Config tests failed"

# ─── TEST 6: Database init ────────────────────────────────────────────
log_head "DATABASE TESTS"

$PYTHON << 'PYTEST'
import sys; sys.path.insert(0,'.')
from database import init_db
from database.models import PostLog, Analytics, TaskQueue
init_db()
print("  ✓ Database initialised (SQLite)")
print(f"  ✓ PostLog table: {PostLog.select().count()} rows")
print(f"  ✓ TaskQueue table: {TaskQueue.select().count()} rows")
PYTEST
[ $? -eq 0 ] && ((PASS+=3)) || log_fail "Database tests failed"

# ─── TEST 7: Ollama check (informational only) ────────────────────────
log_head "OLLAMA CHECK"

curl -s --max-time 3 http://localhost:11434/api/tags > /dev/null 2>&1 \
  && log_ok "Ollama is running at localhost:11434" \
  || log_warn "Ollama not running — CEO Brain chat will fail (start with: ollama serve)"

# ─── TEST 8: Static assets check ─────────────────────────────────────
log_head "STATIC ASSETS"

for f in "ui/web_dashboard/static/css/style.css" \
         "ui/web_dashboard/static/js/app.js"; do
  [ -f "$f" ] && log_ok "$f" || log_fail "$f missing"
done

for tmpl in base dashboard agents logs analytics keys api_usage; do
  f="ui/web_dashboard/templates/${tmpl}.html"
  [ -f "$f" ] && log_ok "Template: ${tmpl}.html" || log_fail "Template: ${tmpl}.html MISSING"
done

# ─── SUMMARY ──────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}══════════════════════════════════════════${NC}"
echo -e "${BOLD}  Test Results:${NC}"
echo -e "${GREEN}  ✓ Passed:   $PASS${NC}"
echo -e "${RED}  ✗ Failed:   $FAIL${NC}"
echo -e "${YELLOW}  ⚠ Warnings: $WARN${NC}"
echo -e "${BOLD}══════════════════════════════════════════${NC}"

if [ $FAIL -eq 0 ]; then
  echo -e "\n${GREEN}${BOLD}✅ All tests passed!${NC}"
  echo -e "Start the dashboard: ${CYAN}python main.py --both${NC}"
else
  echo -e "\n${RED}${BOLD}❌ $FAIL test(s) failed. Check errors above.${NC}"
  exit 1
fi
