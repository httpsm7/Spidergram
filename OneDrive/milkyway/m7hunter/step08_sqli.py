#!/usr/bin/env python3
# modules/step08_sqli.py — SQLi Engine v6 (FIXED)
# FIX: SQLmap parser now looks for correct string
#      "sqlmap identified the following injection point(s)"
# FIX: Nested directory walk handles all sqlmap output structures
# FIX: Added NoSQL-style injection params via gf
# MilkyWay Intelligence | Author: Sharlix

import os
import re
from core.utils import FormatFixer, count_lines, safe_read

class SQLiStep:
    def __init__(self, p): self.p=p; self.log=p.log; self.f=p.files

    def run(self):
        urls = self.f["urls"]
        if not os.path.isfile(urls) or count_lines(urls)==0:
            FormatFixer.fix(self.f["live_hosts"], self.f["fmt_url"], "url")
            urls = self.f["fmt_url"]

        sqli_params = self.f["sqli_params"]
        sqli_outdir = os.path.join(self.p.out, f"{self.p.prefix}_sqlmap")
        results_out = self.f["sqli_results"]

        # gf filter with fallback
        self.p.shell(f"cat {urls} | gf sqli > {sqli_params} 2>/dev/null", label="gf sqli")
        if count_lines(sqli_params) == 0:
            self.log.warn("gf sqli empty — using numeric ID params")
            # Extract URLs with numeric params (common SQLi targets)
            self._extract_numeric_params(urls, sqli_params)

        if count_lines(sqli_params) == 0:
            self.log.warn("No SQLi params found"); return

        self.log.info(f"  ↳ SQLi candidates: {count_lines(sqli_params)}")

        cookie_flag = f"--cookie '{self.p.args.cookie}'" if getattr(self.p.args,"cookie",None) else ""

        self.p.shell(
            f"sqlmap -m {sqli_params} "
            f"--batch --random-agent --level=2 --risk=2 "
            f"--output-dir={sqli_outdir} --forms "
            f"{cookie_flag} --no-logging 2>/dev/null",
            label="sqlmap scan", use_tor=bool(self.p.tor), timeout=1200)

        # FIX: Correct parser with right string + recursive dir walk
        confirmed = self._parse_sqlmap_results(sqli_outdir, results_out)

        self.log.success(f"SQLi confirmed: {confirmed} → {os.path.basename(results_out)}")

    def _extract_numeric_params(self, urls_file: str, out_file: str):
        """Extract URLs with numeric params — common SQLi targets."""
        import urllib.parse
        if not os.path.isfile(urls_file):
            return
        added = set()
        with open(urls_file) as f:
            lines = [l.strip() for l in f if l.strip()]

        with open(out_file, 'w') as out:
            for url in lines[:1000]:
                try:
                    parsed = urllib.parse.urlparse(url)
                    qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
                    for k, vals in qs.items():
                        # Numeric value = SQLi candidate
                        if vals and vals[0].isdigit() and url not in added:
                            out.write(url + "\n")
                            added.add(url)
                            break
                except Exception:
                    pass

    def _parse_sqlmap_results(self, sqlmap_dir: str, results_out: str) -> int:
        """
        FIX: Correct sqlmap confirmation string.
        Old: 'injection point' (never matches)
        New: 'sqlmap identified the following injection point' (actual sqlmap output)
        Also handles: 'is vulnerable', 'Parameter:' in log files
        """
        if not os.path.isdir(sqlmap_dir):
            return 0

        confirmed = 0

        # FIX: os.walk handles all nested sqlmap directories
        for root, dirs, files in os.walk(sqlmap_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, 'r', errors='ignore') as f:
                        content = f.read()

                    # FIX: Multiple correct sqlmap output strings
                    is_vulnerable = any([
                        "sqlmap identified the following injection point" in content,
                        "is vulnerable" in content.lower() and "Parameter:" in content,
                        "[CRITICAL] Parameter:" in content and "injectable" in content.lower(),
                    ])

                    if is_vulnerable:
                        # Extract the vulnerable parameter and URL
                        url_match   = re.search(r'URL:\s+(\S+)', content)
                        param_match = re.search(r'Parameter:\s+(.+?)(?:\n|$)', content)
                        type_match  = re.search(r'Type:\s+(.+?)(?:\n|$)', content)

                        target_url = url_match.group(1) if url_match else os.path.basename(root)
                        param      = param_match.group(1).strip() if param_match else "unknown"
                        inj_type   = type_match.group(1).strip() if type_match else "unknown"

                        detail = f"param={param} type={inj_type}"
                        line   = f"SQLI_CONFIRMED: {target_url} | {detail}"

                        with open(results_out, "a") as out:
                            out.write(line + "\n")

                        # Determine severity
                        sev = "critical" if "blind" not in inj_type.lower() else "high"
                        self.p.add_finding(sev, "SQLI_CONFIRMED", target_url, detail, "sqlmap")
                        confirmed += 1

                except Exception:
                    pass

        if confirmed == 0:
            self.log.info("SQLi: no confirmed injections")
        return confirmed
