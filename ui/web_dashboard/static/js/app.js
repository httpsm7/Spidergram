/* ═══════════════════════════════════════════════════════════════════
   Spidergram v3 — Dashboard JavaScript
   Features: Clock · Toast · Chat · Command Palette · Notifications ·
             Theme Toggle · Mobile Sidebar · Real-time Logs ·
             Video Modal · IG Preview · Health Widget · Export
   ═══════════════════════════════════════════════════════════════════ */

/* ── Clock ─────────────────────────────────────────────────────────── */
function updateClock() {
  const el = document.getElementById('clock');
  if (el) el.textContent = new Date().toLocaleTimeString('en-IN', { hour12: true });
}
setInterval(updateClock, 1000);
updateClock();

/* ── Toast ──────────────────────────────────────────────────────────── */
let _toastTimer = null;
function showToast(msg, dur = 3000) {
  let el = document.getElementById('toast');
  if (!el) { el = document.createElement('div'); el.id = 'toast'; document.body.appendChild(el); }
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove('show'), dur);
}

/* ── Loading Screen ─────────────────────────────────────────────────── */
(function initLoader() {
  const screen = document.getElementById('loadingScreen');
  if (!screen) return;
  const bar   = document.getElementById('loaderBar');
  const phase = document.getElementById('loaderPhase');
  const phases = [
    [0,  'Initializing CEO Brain…'],
    [25, 'Loading Agent Configurations…'],
    [55, 'Connecting to Ollama Model…'],
    [80, 'Starting Pipeline Engine…'],
    [96, 'Launching Dashboard…'],
  ];
  let prog = 0;
  const t = setInterval(() => {
    prog = Math.min(prog + Math.random() * 5 + 1.5, 100);
    if (bar) bar.style.width = prog + '%';
    const ph = phases.slice().reverse().find(([v]) => prog >= v);
    if (ph && phase) phase.textContent = ph[1];
    if (prog >= 100) {
      clearInterval(t);
      setTimeout(() => {
        screen.classList.add('done');
        setTimeout(() => screen.remove(), 500);
      }, 500);
    }
  }, 60);
})();

/* ── Theme Toggle ───────────────────────────────────────────────────── */
(function initTheme() {
  const saved = localStorage.getItem('sg_theme') || 'dark';
  if (saved === 'light') document.documentElement.setAttribute('data-theme', 'light');
})();

function toggleTheme() {
  const html  = document.documentElement;
  const icon  = document.getElementById('themeIcon');
  const isLight = html.getAttribute('data-theme') === 'light';
  html.setAttribute('data-theme', isLight ? 'dark' : 'light');
  localStorage.setItem('sg_theme', isLight ? 'dark' : 'light');
  if (icon) icon.textContent = isLight ? '☀️' : '🌙';
}

/* ── Mobile Sidebar ─────────────────────────────────────────────────── */
function toggleSidebar() {
  const sb  = document.querySelector('.sidebar');
  const ov  = document.getElementById('sidebarOverlay');
  if (!sb) return;
  const open = sb.classList.toggle('open');
  if (ov) ov.classList.toggle('show', open);
}
document.addEventListener('click', e => {
  const ov = document.getElementById('sidebarOverlay');
  if (ov && ov.contains(e.target)) toggleSidebar();
});

/* ── Chat Drawer ────────────────────────────────────────────────────── */
const chatDrawer  = document.getElementById('chatDrawer');
const chatOverlay = document.getElementById('chatOverlay');
function toggleChat() {
  chatDrawer?.classList.toggle('open');
  chatOverlay?.classList.toggle('show');
}
function appendMsg(role, text) {
  const box = document.getElementById('chatMessages');
  if (!box) return null;
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  return div;
}
async function sendChat() {
  const input = document.getElementById('chatInput');
  const msg = input?.value.trim();
  if (!msg) return;
  input.value = '';
  appendMsg('user', msg);
  const thinking = appendMsg('thinking', '⏳ CEO Brain is thinking…');
  try {
    const res  = await fetch('/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg }) });
    const data = await res.json();
    thinking?.remove();
    appendMsg('assistant', data.reply || data.error || '(no response)');
  } catch {
    thinking?.remove();
    appendMsg('assistant', '⚠️ Connection error. Is the server running?');
  }
}
document.getElementById('chatInput')?.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
});

/* ── Notifications ──────────────────────────────────────────────────── */
let _notifications = [];
let _unread = 0;

async function fetchNotifications() {
  try {
    const res  = await fetch('/api/notifications');
    const data = await res.json();
    _notifications = data.notifications || [];
    _unread = _notifications.filter(n => !n.read).length;
    renderNotifBadge();
  } catch {}
}

function renderNotifBadge() {
  const badge = document.getElementById('notifCount');
  if (!badge) return;
  badge.textContent = _unread > 9 ? '9+' : _unread;
  badge.style.display = _unread > 0 ? 'flex' : 'none';
}

function toggleNotifications() {
  const dd = document.getElementById('notifDropdown');
  if (!dd) return;
  const open = dd.classList.toggle('open');
  if (open) renderNotifList();
}

function renderNotifList() {
  const list = document.getElementById('notifList');
  if (!list) return;
  list.innerHTML = '';
  if (_notifications.length === 0) {
    list.innerHTML = '<div style="padding:16px;text-align:center;color:var(--muted);font-size:0.8rem">No notifications</div>';
    return;
  }
  _notifications.slice(0, 10).forEach(n => {
    list.innerHTML += `
      <div class="notif-item">
        <div class="notif-icon">${n.icon || '📌'}</div>
        <div class="notif-body">
          <div class="notif-text">${n.message}</div>
          <div class="notif-time">${n.time}</div>
        </div>
      </div>`;
  });
  _unread = 0;
  renderNotifBadge();
}

document.addEventListener('click', e => {
  const dd = document.getElementById('notifDropdown');
  const btn = document.getElementById('notifBtn');
  if (dd && !dd.contains(e.target) && btn && !btn.contains(e.target)) {
    dd.classList.remove('open');
  }
});

// Poll every 30s
setInterval(fetchNotifications, 30000);
fetchNotifications();

/* ── Command Palette ────────────────────────────────────────────────── */
const CMD_REGISTRY = [
  { icon:'◈', label:'Dashboard',       desc:'Go to main dashboard',         action: () => window.location.href='/'          },
  { icon:'◎', label:'Agent Manager',   desc:'Manage your AI agents',         action: () => window.location.href='/agents'    },
  { icon:'☰', label:'Activity Logs',   desc:'View all post logs',            action: () => window.location.href='/logs'      },
  { icon:'◫', label:'Analytics',       desc:'Engagement & performance data', action: () => window.location.href='/analytics' },
  { icon:'⊛', label:'API Keys',        desc:'Manage encrypted API keys',     action: () => window.location.href='/keys'      },
  { icon:'◉', label:'CEO Brain Chat',  desc:'Open AI CEO assistant',         action: () => toggleChat()                      },
  { icon:'▶', label:'Run world_news',   desc:'Trigger pipeline now',          action: () => runAgent('world_news')            },
  { icon:'▶', label:'Run business_news',desc:'Trigger pipeline now',          action: () => runAgent('business_news')         },
  { icon:'▶', label:'Run india_national',desc:'Trigger pipeline now',         action: () => runAgent('india_national')        },
  { icon:'▶', label:'Run india_politics',desc:'Trigger pipeline now',         action: () => runAgent('india_politics')        },
  { icon:'▶', label:'Run general_news', desc:'Trigger pipeline now',          action: () => runAgent('general_news')          },
  { icon:'🔑', label:'Set API Key',     desc:'Add or update an API key',      action: () => window.location.href='/keys'      },
  { icon:'📊', label:'Performance Report',desc:'CEO Brain: show report',      action: () => { toggleChat(); setTimeout(() => { const i=document.getElementById('chatInput'); if(i){i.value='Show performance report'; sendChat();} }, 300); }},
  { icon:'🌙', label:'Toggle Theme',    desc:'Switch dark / light mode',      action: () => toggleTheme()                     },
];

let _cmdIdx = 0;
let _cmdFiltered = [...CMD_REGISTRY];

function openCommandPalette() {
  const pal = document.getElementById('cmdPalette');
  const inp = document.getElementById('cmdInput');
  if (!pal) return;
  pal.classList.add('open');
  inp?.focus();
  _cmdIdx = 0;
  filterCommands('');
}
function closeCommandPalette() {
  document.getElementById('cmdPalette')?.classList.remove('open');
  const inp = document.getElementById('cmdInput');
  if (inp) inp.value = '';
}
function filterCommands(q) {
  const lower = q.toLowerCase();
  _cmdFiltered = CMD_REGISTRY.filter(c =>
    c.label.toLowerCase().includes(lower) ||
    c.desc.toLowerCase().includes(lower)
  );
  _cmdIdx = 0;
  renderCommandResults();
}
function renderCommandResults() {
  const list = document.getElementById('cmdResults');
  if (!list) return;
  list.innerHTML = '';
  if (_cmdFiltered.length === 0) {
    list.innerHTML = '<div style="padding:16px;text-align:center;color:var(--muted);font-size:0.82rem">No results found</div>';
    return;
  }
  _cmdFiltered.forEach((c, i) => {
    const el = document.createElement('div');
    el.className = 'cmd-item' + (i === _cmdIdx ? ' selected' : '');
    el.innerHTML = `
      <div class="cmd-item-icon">${c.icon}</div>
      <div class="cmd-item-main">
        <div class="cmd-item-label">${c.label}</div>
        <div class="cmd-item-desc">${c.desc}</div>
      </div>`;
    el.onclick = () => { c.action(); closeCommandPalette(); };
    list.appendChild(el);
  });
}
document.getElementById('cmdInput')?.addEventListener('input', e => filterCommands(e.target.value));
document.getElementById('cmdInput')?.addEventListener('keydown', e => {
  if (e.key === 'ArrowDown') { _cmdIdx = Math.min(_cmdIdx + 1, _cmdFiltered.length - 1); renderCommandResults(); }
  if (e.key === 'ArrowUp')   { _cmdIdx = Math.max(_cmdIdx - 1, 0); renderCommandResults(); }
  if (e.key === 'Enter')     { _cmdFiltered[_cmdIdx]?.action(); closeCommandPalette(); }
  if (e.key === 'Escape')    { closeCommandPalette(); }
});
document.getElementById('cmdPalette')?.addEventListener('click', e => {
  if (e.target === document.getElementById('cmdPalette')) closeCommandPalette();
});
document.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); openCommandPalette(); }
});

/* ── Run Agent helper ───────────────────────────────────────────────── */
function runAgent(id) {
  fetch(`/run/${id}`, { method: 'POST' })
    .then(r => r.json())
    .then(d => showToast(d.message || d.error));
}

/* ── Real-time Log Polling ──────────────────────────────────────────── */
let _logPoller = null;
let _logTimestamp = 0;

function startLogPolling() {
  const feed  = document.getElementById('liveLogFeed');
  const dot   = document.getElementById('liveDot');
  if (!feed) return;
  if (dot) dot.style.display = 'inline-block';

  _logPoller = setInterval(async () => {
    try {
      const res  = await fetch(`/api/logs?since=${_logTimestamp}`);
      const data = await res.json();
      if (data.logs && data.logs.length > 0) {
        _logTimestamp = data.timestamp;
        data.logs.forEach(log => prependLogRow(feed, log));
      }
    } catch {}
  }, 5000);
}

function stopLogPolling() {
  clearInterval(_logPoller);
  const dot = document.getElementById('liveDot');
  if (dot) dot.style.display = 'none';
}

function prependLogRow(feed, log) {
  const statusMap = {
    success:    '<span class="pill pill-green">✓ Success</span>',
    failed:     '<span class="pill pill-red">✗ Failed</span>',
    processing: '<span class="pill pill-blue">⟳ Running</span>',
    pending:    '<span class="pill pill-yellow">⏳ Pending</span>',
  };
  const row = document.createElement('tr');
  row.style.animation = 'fadeSlide 0.3s ease-out';
  row.innerHTML = `
    <td class="mono">${log.id || '—'}</td>
    <td class="mono">${log.agent_id || '—'}</td>
    <td class="truncate" onclick="openVideoModal(${JSON.stringify(log).replace(/"/g,'&quot;')})" style="cursor:pointer">${log.news_title || '—'}</td>
    <td>${statusMap[log.status] || log.status}</td>
    <td class="muted">${log.posted_at || 'just now'}</td>`;
  const tbody = feed.querySelector('tbody');
  if (tbody) { tbody.insertBefore(row, tbody.firstChild); if (tbody.children.length > 50) tbody.lastChild.remove(); }
}

/* ── Video Preview Modal ────────────────────────────────────────────── */
function openVideoModal(logData) {
  const overlay = document.getElementById('videoModal');
  if (!overlay) return;
  const log = (typeof logData === 'string') ? JSON.parse(logData) : logData;

  document.getElementById('videoModalTitle').textContent = log.news_title || 'Video Preview';
  const vid = document.getElementById('modalVideo');
  if (vid) {
    vid.src = log.video_url || '';
    vid.poster = log.thumbnail_url || '';
  }
  document.getElementById('modalAgent').textContent   = log.agent_id   || '—';
  document.getElementById('modalStatus').textContent  = log.status     || '—';
  document.getElementById('modalPostedAt').textContent= log.posted_at  || '—';
  document.getElementById('modalCaption').textContent = log.caption    || 'No caption available.';

  overlay.classList.add('open');
}
function closeVideoModal() {
  const overlay = document.getElementById('videoModal');
  overlay?.classList.remove('open');
  const vid = document.getElementById('modalVideo');
  if (vid) { vid.pause(); vid.src = ''; }
}

/* ── Instagram Preview Modal ─────────────────────────────────────────── */
function openIGPreview(agentId, agentName) {
  const overlay = document.getElementById('igModal');
  if (!overlay) return;
  document.getElementById('igModalAgentName').textContent = agentName || agentId;
  document.getElementById('igPreviewUsername').textContent = '@spidergram_' + agentId;
  overlay.classList.add('open');
}
function closeIGPreview() {
  document.getElementById('igModal')?.classList.remove('open');
}

/* ── Health Widget ──────────────────────────────────────────────────── */
const _healthHistory = { cpu: [], ram: [] };

async function updateHealthWidget() {
  try {
    const res  = await fetch('/api/health');
    const data = await res.json();

    // CPU
    const cpuEl = document.getElementById('healthCPU');
    const cpuBar = document.getElementById('healthCPUBar');
    if (cpuEl) cpuEl.textContent = data.cpu + '%';
    if (cpuBar) { cpuBar.style.width = data.cpu + '%'; cpuBar.style.background = data.cpu > 80 ? 'var(--red)' : data.cpu > 60 ? 'var(--yellow)' : 'var(--green)'; }

    // RAM
    const ramEl = document.getElementById('healthRAM');
    const ramBar = document.getElementById('healthRAMBar');
    if (ramEl) ramEl.textContent = data.ram + ' MB';
    const ramPct = Math.min((data.ram / 2048) * 100, 100);
    if (ramBar) { ramBar.style.width = ramPct + '%'; }

    // Ollama latency
    const latEl = document.getElementById('healthLatency');
    if (latEl) latEl.textContent = data.ollama_latency + ' ms';

    // Disk
    const diskEl = document.getElementById('healthDisk');
    const diskBar = document.getElementById('healthDiskBar');
    const diskPct = data.disk_total ? Math.round((data.disk_used / data.disk_total) * 100) : 0;
    if (diskEl) diskEl.textContent = Math.round(data.disk_used / 1024) + ' GB / ' + Math.round(data.disk_total / 1024) + ' GB';
    if (diskBar) diskBar.style.width = diskPct + '%';

  } catch {}
}

// Update health every 10s
if (document.getElementById('healthCPU')) {
  updateHealthWidget();
  setInterval(updateHealthWidget, 10000);
}

/* ── Stat counter animation ─────────────────────────────────────────── */
function animateCounters() {
  document.querySelectorAll('.stat-value[data-target]').forEach(el => {
    const target = parseFloat(el.dataset.target);
    const suffix = el.dataset.suffix || '';
    if (isNaN(target)) return;
    let current = 0;
    const step = Math.ceil(target / 30);
    const t = setInterval(() => {
      current += step;
      if (current >= target) { el.textContent = el.dataset.raw || (target + suffix); clearInterval(t); }
      else el.textContent = current + suffix;
    }, 28);
  });
}
document.addEventListener('DOMContentLoaded', animateCounters);

/* ── Analytics Export ───────────────────────────────────────────────── */
function exportCSV() {
  fetch('/api/analytics/export?fmt=csv')
    .then(r => {
      if (!r.ok) throw new Error('no data');
      return r.blob();
    })
    .then(blob => {
      const url = URL.createObjectURL(blob);
      const a   = document.createElement('a');
      a.href = url; a.download = 'spidergram_analytics.csv'; a.click();
      URL.revokeObjectURL(url);
      showToast('📥 CSV exported');
    })
    .catch(() => showToast('⚠️ Export failed — no data yet'));
}

function exportPDF() {
  showToast('📄 Generating PDF report…');
  window.open('/api/analytics/export?fmt=pdf', '_blank');
}

/* ── Agent toggle edit panel ─────────────────────────────────────────── */
function toggleEdit(id) {
  const el = document.getElementById(id);
  el?.classList.toggle('hidden');
}

/* ── Auto-refresh stats every 60s (dashboard) ──────────────────────── */
setInterval(() => {
  if (document.visibilityState === 'visible' && window.location.pathname === '/') {
    fetch('/api/stats').then(r => r.json()).then(data => {
      const s = data.posts;
      document.querySelectorAll('.stat-value[data-key]').forEach(el => {
        const k = el.dataset.key;
        if (k && s[k] !== undefined) { el.dataset.target = s[k]; el.textContent = s[k]; }
      });
    }).catch(() => {});
  }
}, 60000);

/* ── Bottom nav active state ────────────────────────────────────────── */
(function setBnavActive() {
  const path = window.location.pathname;
  document.querySelectorAll('.bnav-item[data-href]').forEach(btn => {
    const h = btn.dataset.href;
    if (h === '/' ? path === '/' : path.startsWith(h)) btn.classList.add('active');
  });
})();
