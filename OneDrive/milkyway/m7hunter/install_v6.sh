#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#   M7HUNTER v6.0 — Complete Installer (Upgraded)
#   All original tools + NEW: rustscan, paramspider, x8, qsreplace,
#   uro, gospider, wafw00f, cariddi, interactsh-client, meg
#   Made by MilkyWay Intelligence | Author: Sharlix
# ═══════════════════════════════════════════════════════════════════
set -e

R='\033[91m'; B='\033[34m'; G='\033[92m'
Y='\033[93m'; C='\033[96m'; W='\033[97m'; RST='\033[0m'

ok()   { echo -e "${G}[✓]${RST} $1"; }
info() { echo -e "${C}[*]${RST} $1"; }
warn() { echo -e "${Y}[!]${RST} $1"; }
err()  { echo -e "${R}[✗]${RST} $1"; }
sec()  { echo -e "\n${B}━━━ ${W}$1${RST}\n"; }

[ "$EUID" -ne 0 ] && { err "Run as root: sudo bash install_v6.sh"; exit 1; }

exists(){ command -v "$1" &>/dev/null && return 0
  for d in /usr/bin /usr/local/bin /usr/local/go/bin "$HOME/go/bin" "$HOME/.local/bin" /snap/bin; do
    [ -x "$d/$1" ] && return 0; done; return 1; }

# ── APT ──────────────────────────────────────────────────────────────
sec "APT Tools"
apt-get update -qq 2>/dev/null
APT_PKGS="nmap masscan sqlmap tor proxychains4 massdns amass jq curl git
          python3 python3-pip dnsutils ruby ruby-dev build-essential
          libcurl4-openssl-dev make gcc cargo rustc"
for pkg in $APT_PKGS; do
  exists "$pkg" && ok "$pkg" || {
    info "Installing $pkg..."
    apt-get install -y "$pkg" -qq 2>/dev/null && ok "$pkg" || warn "$pkg failed"
  }
done

# ── Go ────────────────────────────────────────────────────────────────
sec "Go Language"
if exists go; then
  ok "Go: $(go version 2>/dev/null | awk '{print $3}')"
else
  info "Installing Go..."
  apt-get install -y golang-go -qq 2>/dev/null || snap install go --classic 2>/dev/null
fi
export GOPATH="$HOME/go"
export PATH="$PATH:$GOPATH/bin:/usr/local/go/bin"
grep -q 'GOPATH' /root/.bashrc 2>/dev/null || {
  echo 'export GOPATH=$HOME/go' >> /root/.bashrc
  echo 'export PATH=$PATH:$GOPATH/bin:/usr/local/go/bin' >> /root/.bashrc
}

# ── Go Tools (original) ───────────────────────────────────────────────
sec "Go Security Tools (Core)"
declare -A GOTOOLS=(
  ["subfinder"]="github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
  ["httpx"]="github.com/projectdiscovery/httpx/cmd/httpx@latest"
  ["nuclei"]="github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
  ["naabu"]="github.com/projectdiscovery/naabu/v2/cmd/naabu@latest"
  ["dnsx"]="github.com/projectdiscovery/dnsx/cmd/dnsx@latest"
  ["katana"]="github.com/projectdiscovery/katana/cmd/katana@latest"
  ["dalfox"]="github.com/hahwul/dalfox/v2@latest"
  ["hakrawler"]="github.com/hakluke/hakrawler@latest"
  ["waybackurls"]="github.com/tomnomnom/waybackurls@latest"
  ["gau"]="github.com/lc/gau/v2/cmd/gau@latest"
  ["subzy"]="github.com/PentestPanic/subzy@latest"
  ["gf"]="github.com/tomnomnom/gf@latest"
  ["anew"]="github.com/tomnomnom/anew@latest"
  ["gowitness"]="github.com/sensepost/gowitness@latest"
  ["ffuf"]="github.com/ffuf/ffuf/v2@latest"
  ["kxss"]="github.com/Emoe/kxss@latest"
  ["trufflehog"]="github.com/trufflesecurity/trufflehog/v3@latest"
)
for tool in "${!GOTOOLS[@]}"; do
  exists "$tool" && ok "$tool" || {
    info "Installing $tool..."
    go install -v "${GOTOOLS[$tool]}" &>/dev/null \
      && ok "$tool" || warn "$tool failed"
  }
done

# ── NEW Go Tools v6 ───────────────────────────────────────────────────
sec "NEW Go Tools (v6 Additions)"
declare -A NEW_GOTOOLS=(
  # qsreplace: replaces broken sed for SSRF/XSS injection
  ["qsreplace"]="github.com/tomnomnom/qsreplace@latest"
  # gospider: backup crawler when katana fails
  ["gospider"]="github.com/jaeles-project/gospider@latest"
  # uro: URL dedup/normalization before scanning
  ["uro"]="github.com/s0md3v/uro@latest"
  # cariddi: endpoint discovery + secrets + JS analysis
  ["cariddi"]="github.com/edoardottt/cariddi/cmd/cariddi@latest"
  # interactsh-client: official OOB client (replaces unreliable polling)
  ["interactsh-client"]="github.com/projectdiscovery/interactsh/cmd/interactsh-client@latest"
  # meg: batch URL fetcher (faster than curl loop)
  ["meg"]="github.com/tomnomnom/meg@latest"
  # notify: pipe findings to Telegram/Discord/Slack
  ["notify"]="github.com/projectdiscovery/notify/cmd/notify@latest"
  # naabu already in original list
)
for tool in "${!NEW_GOTOOLS[@]}"; do
  exists "$tool" && ok "$tool (already installed)" || {
    info "Installing NEW: $tool..."
    go install -v "${NEW_GOTOOLS[$tool]}" &>/dev/null \
      && ok "$tool" || warn "$tool failed"
  }
done

# ── Rustscan (10x faster than nmap for port discovery) ───────────────
sec "RustScan — Ultra-fast Port Scanner"
if exists rustscan; then
  ok "rustscan already installed"
elif exists cargo; then
  info "Building rustscan from source..."
  cargo install rustscan --quiet 2>/dev/null && ok "rustscan" || {
    # Fallback: binary release
    LATEST=$(curl -s "https://api.github.com/repos/RustScan/RustScan/releases/latest" | jq -r '.tag_name' 2>/dev/null)
    if [ -n "$LATEST" ]; then
      ARCH=$(uname -m | sed 's/x86_64/x86_64/' | sed 's/aarch64/aarch64/')
      wget -qO /tmp/rustscan.deb \
        "https://github.com/RustScan/RustScan/releases/download/${LATEST}/rustscan_${LATEST#v}_${ARCH}.deb" 2>/dev/null \
        && dpkg -i /tmp/rustscan.deb 2>/dev/null && ok "rustscan (binary)" || warn "rustscan failed"
    fi
  }
else
  warn "cargo not found — rustscan skipped (install cargo first)"
fi

# ── wafw00f (WAF detection before scanning) ───────────────────────────
sec "wafw00f — WAF Detection"
exists wafw00f && ok "wafw00f" || {
  pip3 install wafw00f --break-system-packages -q 2>/dev/null \
    && ok "wafw00f" || warn "wafw00f failed"
}

# ── paramspider (better param discovery from Wayback) ─────────────────
sec "ParamSpider — Wayback Parameter Discovery"
exists paramspider && ok "paramspider" || {
  pip3 install paramspider --break-system-packages -q 2>/dev/null
  exists paramspider && ok "paramspider" || {
    # Git install
    git clone --quiet https://github.com/devanshbatham/ParamSpider /opt/paramspider 2>/dev/null
    [ -f /opt/paramspider/paramspider.py ] && {
      ln -sf /opt/paramspider/paramspider.py /usr/local/bin/paramspider
      chmod +x /usr/local/bin/paramspider
      ok "paramspider (git)"
    } || warn "paramspider failed"
  }
}

# ── x8 (hidden parameter discovery) ──────────────────────────────────
sec "x8 — Hidden Parameter Discovery"
exists x8 && ok "x8" || {
  cargo install x8 --quiet 2>/dev/null && ok "x8" || {
    # Binary download
    wget -qO /usr/local/bin/x8 \
      "https://github.com/Sh1Yo/x8/releases/latest/download/x86_64-linux-x8" 2>/dev/null \
      && chmod +x /usr/local/bin/x8 && ok "x8 (binary)" || warn "x8 failed"
  }
}

# ── smuggler.py (HTTP Request Smuggling) ──────────────────────────────
sec "Smuggler — HTTP Request Smuggling"
SMUGGLER_DIR="$HOME/tools/smuggler"
[ -d "$SMUGGLER_DIR" ] && ok "smuggler (exists)" || {
  mkdir -p "$HOME/tools"
  git clone --quiet https://github.com/defparam/smuggler "$SMUGGLER_DIR" 2>/dev/null \
    && ok "smuggler → $SMUGGLER_DIR" || warn "smuggler failed"
}

# ── Python packages ───────────────────────────────────────────────────
sec "Python Packages"
pip3 install --break-system-packages --quiet \
  requests stem colorama tqdm rich arjun cloud-enum wafw00f \
  pycurl dnspython 2>/dev/null || true
ok "Python packages done"

# ── WPScan ────────────────────────────────────────────────────────────
sec "WPScan"
exists wpscan && ok "WPScan installed" || {
  gem install wpscan 2>/dev/null && ok "WPScan done" || warn "WPScan failed"
}

# ── SecLists ──────────────────────────────────────────────────────────
sec "SecLists Wordlists"
[ -d "/usr/share/seclists" ] && ok "SecLists installed" || {
  apt-get install -y seclists -qq 2>/dev/null \
  || git clone --depth 1 https://github.com/danielmiessler/SecLists /usr/share/seclists 2>/dev/null
  ok "SecLists done"
}

# ── GF Patterns ───────────────────────────────────────────────────────
sec "GF Patterns"
GF_DIR="$HOME/.gf"
mkdir -p "$GF_DIR"
ls "$GF_DIR"/*.json &>/dev/null || {
  git clone --quiet https://github.com/1ndianl33t/Gf-Patterns /tmp/gfp 2>/dev/null \
    && cp /tmp/gfp/*.json "$GF_DIR/" 2>/dev/null && ok "GF patterns installed"
  git clone --quiet https://github.com/tomnomnom/gf /tmp/gfs 2>/dev/null \
    && cp /tmp/gfs/examples/*.json "$GF_DIR/" 2>/dev/null
}

# ── Nuclei Templates ──────────────────────────────────────────────────
sec "Nuclei Templates"
exists nuclei && {
  nuclei -update-templates -silent 2>/dev/null && ok "Templates updated"
} || warn "nuclei not found"

# ── M7Hunter Directories ──────────────────────────────────────────────
sec "M7Hunter Data Directories"
mkdir -p "$HOME/.m7hunter/sessions"
mkdir -p "$HOME/.m7hunter/secure"
mkdir -p "$HOME/.m7hunter/audit"
mkdir -p "$HOME/tools"
chmod 700 "$HOME/.m7hunter/secure"
ok "Directories created"

# ── Tor ───────────────────────────────────────────────────────────────
sec "Tor Configuration"
cat > /etc/tor/torrc << 'TORRC'
SocksPort 9050
ControlPort 9051
HashedControlPassword 16:E600ADC90A2E3F9D8F0A4D24BCFF62C8F6C1E9B3D2A1F0E9C8B7A6D5
DataDirectory /var/lib/tor
TORRC
systemctl enable tor 2>/dev/null && systemctl restart tor 2>/dev/null \
  || service tor start 2>/dev/null
ok "Tor configured"

# ── ProxyChains ───────────────────────────────────────────────────────
for f in /etc/proxychains4.conf /etc/proxychains.conf; do
  [ -f "$f" ] && {
    grep -q "127.0.0.1 9050" "$f" || echo "socks5 127.0.0.1 9050" >> "$f"
    sed -i 's/^#quiet_mode/quiet_mode/' "$f" 2>/dev/null
    ok "ProxyChains configured"; break
  }
done

# ── Global Command ────────────────────────────────────────────────────
sec "M7Hunter v6 Global Command"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cat > /usr/local/bin/m7hunter << WRAP
#!/usr/bin/env bash
exec python3 "${SCRIPT_DIR}/m7hunter.py" "\$@"
WRAP
chmod +x /usr/local/bin/m7hunter
mkdir -p "${SCRIPT_DIR}/results"
ok "Global command: m7hunter"

# ── Setup brain credentials prompt ───────────────────────────────────
sec "Brain Credential Setup (IMPORTANT)"
echo -e "${Y}[!] Admin credentials are no longer hardcoded in source code.${RST}"
echo -e "${Y}    Add these to your ~/.bashrc or ~/.zshrc:${RST}"
echo -e "${W}    export M7_ADMIN_USER='your_chosen_username'${RST}"
echo -e "${W}    export M7_ADMIN_PASS='your_chosen_password'${RST}"
echo -e "${C}    Or run: sudo m7hunter --setup-brain${RST}"
echo ""

# ── Summary ───────────────────────────────────────────────────────────
echo ""
echo -e "${B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo -e "${G}  ✅  M7Hunter v6.0 — Installation Complete!${RST}"
echo -e "${B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}"
echo ""
echo -e "  ${C}New in v6:${RST}"
echo -e "  ${W}rustscan${RST} — 10x faster port scan"
echo -e "  ${W}qsreplace${RST} — reliable param injection"
echo -e "  ${W}paramspider${RST} — Wayback parameter discovery"
echo -e "  ${W}x8${RST} — hidden parameter fuzzer"
echo -e "  ${W}wafw00f${RST} — WAF detection"
echo -e "  ${W}gospider${RST} — backup crawler"
echo -e "  ${W}uro${RST} — URL deduplication"
echo -e "  ${W}meg${RST} — batch URL fetcher"
echo -e "  ${W}smuggler${RST} — HTTP smuggling (${SMUGGLER_DIR})"
echo ""
echo -e "  ${C}Quick Start:${RST}"
echo -e "  ${W}sudo m7hunter -u target.com --deep${RST}"
echo -e "  ${W}sudo m7hunter -u target.com --fast${RST}"
echo ""
