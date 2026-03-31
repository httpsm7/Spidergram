"""
e01_recon.py — Reconnaissance Engine
subfinder → crt.sh → httpx → direct probe → tech detection
MilkyWay Intelligence | Author: Sharlix

FIX: Live hosts=0 bug resolved:
  - Target URL itself always added as node even if httpx fails
  - Direct HTTP probe fallback when httpx not found
  - Tech detection via multiple methods
"""
import asyncio
import os
import re
import subprocess
from typing import Dict, List
from core.format_fixer import FormatFixer
from protocols.http_client import HTTPClient


class ReconEngine:
    def __init__(self, db, logger, http: HTTPClient,
                 out_dir: str, prefix: str):
        self.db      = db
        self.logger  = logger
        self.http    = http
        self.out_dir = out_dir
        self.prefix  = prefix

    async def run(self, target: str) -> Dict:
        self.logger.section("PHASE 1: RECONNAISSANCE")
        domain = FormatFixer.to_domain(target)
        url    = FormatFixer.to_url(target)

        result = {"subdomains": [], "live_hosts": [],
                  "tech_stack": {}, "nodes_added": 0}

        # ── Step 1: Subdomain Enum ─────────────────────────
        subs = await self._run_subfinder(domain)
        subs = list(set(subs + [domain]))
        result["subdomains"] = subs
        self.logger.success(f"Subdomains found: {len(subs)}")
        _write(os.path.join(self.out_dir, f"{self.prefix}_subdomains.txt"),
               "\n".join(subs))

        # ── Step 2: HTTP Probe ─────────────────────────────
        live = await self._probe_hosts(subs, url)
        # CRITICAL FIX: always include target itself
        if url not in live:
            live.insert(0, url)
        result["live_hosts"] = live
        self.logger.success(f"Live hosts: {len(live)}")
        _write(os.path.join(self.out_dir, f"{self.prefix}_live_hosts.txt"),
               "\n".join(live))

        # ── Step 3: Tech Detection ─────────────────────────
        tech = await self._detect_tech(url)
        result["tech_stack"] = tech
        if tech:
            self.logger.info(f"Tech: {tech}")

        # ── Step 4: Add ALL live hosts to graph ────────────
        added = 0
        for host_url in live:
            node_type = FormatFixer.classify_url(host_url)
            priority  = FormatFixer.priority_for_type(node_type)
            self.db.add_node(
                url=host_url, method=["GET"], params=[],
                node_type=node_type, priority=priority,
                tech=tech.get("framework", "")
            )
            added += 1

        # Add common endpoint patterns for target
        await self._add_common_endpoints(url, tech)

        result["nodes_added"] = self.db.node_count()
        self.logger.success(f"Graph nodes: {result['nodes_added']}")

        FormatFixer.write_fmt_files(live, self.out_dir, self.prefix)
        self.db.set_state("recon_done", True)
        self.db.set_state("tech_stack", tech)
        self.db.set_state("live_hosts", live)
        return result

    async def _run_subfinder(self, domain: str) -> List[str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "subfinder", "-d", domain, "-silent", "-all",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            subs = [s.strip() for s in stdout.decode().splitlines() if s.strip()]
            if subs:
                return subs
        except Exception:
            pass
        self.logger.warn("subfinder not found — using crt.sh")
        return await self._crtsh(domain)

    async def _crtsh(self, domain: str) -> List[str]:
        try:
            resp = await self.http.get(
                f"https://crt.sh/?q=%.{domain}&output=json",
                retries=2
            )
            if resp and resp.status_code == 200:
                data = resp.json()
                subs = set()
                for entry in data:
                    for name in entry.get("name_value", "").splitlines():
                        name = name.strip().lstrip("*.")
                        if domain in name and name:
                            subs.add(name)
                return list(subs)
        except Exception:
            pass
        return [domain]

    async def _probe_hosts(self, hosts: List[str],
                           fallback_url: str) -> List[str]:
        """Try httpx first, then direct probe."""
        # Method 1: httpx tool
        live = await self._run_httpx(hosts)
        if live:
            return live

        # Method 2: direct HTTP probe
        self.logger.warn("httpx not found or no results — using direct probe")
        return await self._direct_probe(hosts, fallback_url)

    async def _run_httpx(self, hosts: List[str]) -> List[str]:
        if not hosts:
            return []
        tmp = "/tmp/_httpx_input.txt"
        _write(tmp, "\n".join(hosts))
        try:
            proc = await asyncio.create_subprocess_exec(
                "httpx", "-l", tmp, "-silent", "-no-color",
                "-status-code", "-follow-redirects", "-timeout", "10",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            live = []
            for line in stdout.decode().splitlines():
                line = line.strip()
                if line and line.startswith("http"):
                    live.append(line.split()[0])
            return live
        except Exception:
            return []

    async def _direct_probe(self, hosts: List[str],
                             fallback_url: str) -> List[str]:
        """Directly probe each host with HTTP requests."""
        live = set()
        # Always try the main target first
        for scheme in ["https", "http"]:
            url = f"{scheme}://{FormatFixer.to_host(fallback_url)}"
            resp = await self.http.get(url, retries=2)
            if resp and resp.status_code < 500:
                live.add(resp.url if hasattr(resp, "url") else url)
                break

        # Probe other hosts
        tasks = []
        for host in hosts[:20]:
            tasks.append(self._probe_one(FormatFixer.to_host(host)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, str) and r:
                live.add(r)

        return list(live)

    async def _probe_one(self, host: str) -> str:
        for scheme in ["https", "http"]:
            url = f"{scheme}://{host}"
            try:
                resp = await self.http.get(url, retries=1)
                if resp and resp.status_code < 500:
                    return url
            except Exception:
                continue
        return ""

    async def _detect_tech(self, url: str) -> Dict:
        resp = await self.http.get(url, retries=2)
        if not resp:
            return {}
        tech  = {}
        hdrs  = dict(resp.headers)
        body  = resp.text[:8000].lower()

        # Server / framework from headers
        for h in ("server", "x-powered-by", "x-generator",
                  "x-aspnet-version", "x-drupal-cache",
                  "x-wp-total", "cf-ray"):
            val = hdrs.get(h, hdrs.get(h.lower(), ""))
            if val:
                tech[h.lower().replace("-", "_")] = val

        # Body-based fingerprinting
        fingerprints = {
            "wordpress":  "wp-content",
            "drupal":     "drupal",
            "joomla":     "joomla",
            "laravel":    "laravel_session",
            "django":     "csrftoken",
            "rails":      "_rails_session",
            "express":    "x-powered-by: express",
            "nextjs":     "__next",
            "react":      "__react",
            "angular":    "ng-version",
            "vue":        "__vue__",
            "flask":      "werkzeug",
            "spring":     "jsessionid",
        }
        for name, pattern in fingerprints.items():
            if pattern in body:
                tech["framework"] = name
                break

        # Missing security headers
        missing = [
            h for h in ["X-Frame-Options", "Content-Security-Policy",
                         "X-XSS-Protection", "Strict-Transport-Security"]
            if h not in hdrs
        ]
        if missing:
            tech["missing_security_headers"] = missing

        return tech

    async def _add_common_endpoints(self, base_url: str,
                                     tech: Dict):
        """Add high-value endpoint patterns to graph for AI to test."""
        base = base_url.rstrip("/")
        framework = tech.get("framework", "")

        # Universal high-priority paths
        common = [
            ("/login",    "AUTH", 10),
            ("/signin",   "AUTH", 10),
            ("/register", "AUTH", 9),
            ("/api/login","AUTH", 10),
            ("/api/auth", "AUTH", 10),
            ("/admin",    "ADMIN", 8),
            ("/dashboard","ADMIN", 7),
            ("/api/user", "PROFILE", 6),
            ("/api/users","PROFILE", 6),
            ("/api/v1",   "API", 5),
            ("/api/v2",   "API", 5),
            ("/graphql",  "GRAPHQL", 8),
            ("/checkout", "PAYMENT", 9),
            ("/api/payment","PAYMENT", 9),
        ]

        # Framework-specific paths
        if framework == "wordpress":
            common += [
                ("/wp-admin",         "ADMIN", 10),
                ("/wp-login.php",     "AUTH", 10),
                ("/wp-json/wp/v2",    "API", 8),
                ("/xmlrpc.php",       "API", 7),
            ]
        elif framework == "django":
            common += [
                ("/admin/",           "ADMIN", 10),
                ("/api/",             "API", 6),
                ("/accounts/login",   "AUTH", 10),
            ]
        elif framework == "rails":
            common += [
                ("/users/sign_in",    "AUTH", 10),
                ("/admin",            "ADMIN", 9),
                ("/api/v1",           "API", 6),
            ]

        # Probe and add only those that respond
        for path, node_type, priority in common:
            url = base + path
            resp = await self.http.get(url, retries=1)
            if resp and resp.status_code not in (404, 410, 503):
                self.db.add_node(
                    url=url, method=["GET", "POST"],
                    params=[], node_type=node_type,
                    priority=priority
                )


def _write(path: str, content: str):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content + "\n")
    except Exception:
        pass
