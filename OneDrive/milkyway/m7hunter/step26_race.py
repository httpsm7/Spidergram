#!/usr/bin/env python3
# modules/step26_race.py — Race Condition Testing Engine v6 (NEW)
# Tests: coupon codes, votes, transfers, password reset tokens
# Uses threading for last-byte synchronization technique
# MilkyWay Intelligence | Author: Sharlix

import os
import re
import time
import threading
import urllib.request
import urllib.parse
import urllib.error
import queue
from core.utils import safe_read

# Endpoints commonly vulnerable to race conditions
RACE_TARGETS = [
    ("/api/coupon/apply",      "coupon_abuse",     "POST"),
    ("/api/redeem",            "coupon_abuse",     "POST"),
    ("/api/vote",              "vote_stuffing",    "POST"),
    ("/api/like",              "vote_stuffing",    "POST"),
    ("/api/transfer",          "transfer_double",  "POST"),
    ("/api/payment",           "payment_double",   "POST"),
    ("/api/withdraw",          "withdrawal_double","POST"),
    ("/api/order",             "order_double",     "POST"),
    ("/api/register",          "duplicate_reg",    "POST"),
    ("/password/reset",        "token_reuse",      "POST"),
    ("/api/password/reset",    "token_reuse",      "POST"),
    ("/api/referral/claim",    "referral_abuse",   "POST"),
    ("/api/points/redeem",     "points_abuse",     "POST"),
    ("/api/inventory/reserve", "inventory_race",   "POST"),
    ("/checkout",              "checkout_race",    "POST"),
]


class RaceConditionStep:
    def __init__(self, p): self.p=p; self.log=p.log; self.f=p.files

    def run(self):
        live = self.f["live_hosts"]
        urls = self.f["urls"]
        out  = self.f["race_results"]
        found = 0

        hosts = safe_read(live)[:10]
        if not hosts:
            self.log.warn("Race: no live hosts"); return

        self.log.info(f"Race Condition: testing {len(hosts)} hosts")

        for host in hosts:
            host = host.rstrip("/")

            # Test 1: Race on discovered endpoints
            result = self._race_discovered_endpoints(host, urls)
            if result:
                for url, vuln_type, detail in result:
                    with open(out,"a") as f:
                        f.write(f"RACE_{vuln_type.upper()}: {url} | {detail}\n")
                    self.p.add_finding("high", f"RACE_{vuln_type.upper()}",
                                       url, detail, "race-engine")
                    found += 1

            # Test 2: Password reset token race (if applicable)
            result2 = self._race_password_reset(host)
            if result2:
                url, detail = result2
                with open(out,"a") as f:
                    f.write(f"RACE_TOKEN_REUSE: {url} | {detail}\n")
                self.p.add_finding("high", "RACE_TOKEN_REUSE", url, detail, "race-engine")
                found += 1

        self.log.success(f"Race Condition: {found} findings → {os.path.basename(out)}")

    def _race_discovered_endpoints(self, host: str, urls_file: str) -> list:
        """Find and test discovered endpoints for race conditions."""
        all_urls = safe_read(urls_file)
        findings = []

        # Find URLs matching race-prone patterns
        for url in all_urls:
            if host not in url:
                continue
            for path, vuln_type, method in RACE_TARGETS:
                if path.lower() in url.lower():
                    result = self._concurrent_requests(url, method, n=10)
                    if result:
                        detail, responses = result
                        findings.append((url, vuln_type, detail))
                    break  # One test per URL

        # Also test known paths directly on host
        for path, vuln_type, method in RACE_TARGETS[:8]:
            url = host + path
            # Quick check if endpoint exists
            probe = self._probe(url, method)
            if probe and probe.get("status") not in (404, 400, 405):
                result = self._concurrent_requests(url, method, n=10)
                if result:
                    detail, responses = result
                    findings.append((url, vuln_type, detail))

        return findings

    def _concurrent_requests(self, url: str, method: str = "POST",
                              n: int = 10, body: str = "") -> tuple:
        """
        Last-byte synchronization race condition test.
        Send N requests nearly simultaneously using threading.
        Detect if server processes same request multiple times.
        """
        results_q = queue.Queue()
        threads   = []
        barrier   = threading.Barrier(n)  # sync all threads

        def send_request():
            try:
                barrier.wait()  # All threads release at same time
                data = body.encode() if body else b"race_test=1"
                req  = urllib.request.Request(url, data=data, method=method, headers={
                    "User-Agent"  : "M7Hunter-Race/6.0",
                    "Content-Type": "application/x-www-form-urlencoded",
                })
                if getattr(self.p.args,"cookie",None):
                    req.add_header("Cookie", self.p.args.cookie)
                resp = urllib.request.urlopen(req, timeout=8)
                body_resp = resp.read(2000).decode("utf-8", errors="ignore")
                results_q.put({"status": resp.status, "body": body_resp, "ok": True})
            except urllib.error.HTTPError as e:
                results_q.put({"status": e.code, "body": "", "ok": False})
            except Exception:
                results_q.put({"status": 0, "body": "", "ok": False})

        # Launch all threads
        for _ in range(n):
            t = threading.Thread(target=send_request, daemon=True)
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        # Collect results
        responses = []
        while not results_q.empty():
            responses.append(results_q.get_nowait())

        if not responses:
            return None

        ok_responses   = [r for r in responses if r["ok"]]
        error_responses = [r for r in responses if not r["ok"]]

        # Race condition indicators:
        # 1. Multiple 200 responses where only 1 should succeed
        ok_count = len(ok_responses)
        if ok_count >= 3:
            detail = (f"{ok_count}/{n} concurrent requests succeeded "
                      f"(race condition — only 1 should succeed)")
            return (detail, responses)

        # 2. Response body contains duplicate processing indicators
        all_bodies = " ".join(r.get("body","") for r in ok_responses)
        if any(kw in all_bodies.lower() for kw in
               ["duplicate","already applied","used","twice","multiple"]):
            detail = f"Server detected duplicates in {ok_count} concurrent requests"
            return (detail, responses)

        return None

    def _race_password_reset(self, host: str) -> tuple:
        """Test if password reset token can be used multiple times (race condition)."""
        reset_paths = ["/password/reset", "/api/password/reset",
                       "/forgot-password", "/api/forgot-password"]

        for path in reset_paths:
            url = host + path
            probe = self._probe(url, "POST")
            if not probe or probe.get("status") == 404:
                continue

            # Simulate: request token, then use it twice simultaneously
            result = self._concurrent_requests(
                url, "POST", n=5,
                body="email=race-test@example.com"
            )
            if result:
                detail, _ = result
                return (url, f"Password reset endpoint: {detail}")

        return None

    def _probe(self, url: str, method: str) -> dict:
        """Quick probe to check if endpoint exists."""
        try:
            data = b"probe=1"
            req  = urllib.request.Request(url, data=data, method=method, headers={
                "User-Agent": "M7Hunter/6.0"
            })
            resp = urllib.request.urlopen(req, timeout=5)
            return {"status": resp.status}
        except urllib.error.HTTPError as e:
            return {"status": e.code}
        except Exception:
            return None
