"""
ai_brain.py — AI Decision Engine
Ollama (primary) → Groq (fallback) → YAML rules (last resort)
MilkyWay Intelligence | Author: Sharlix
"""
import json
import re
import os
from typing import Any, Dict, List, Optional
import httpx

OLLAMA_URL   = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3:8b")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.1-70b-versatile"
GROQ_KEY     = os.environ.get("GROQ_API_KEY", "")

OLLAMA_TIMEOUT = 15
MAX_RETRIES    = 3
MIN_CONFIDENCE = 50

ALLOWED_ACTIONS = {
    "run_engine", "test_endpoint", "retest_finding",
    "mark_false_positive", "switch_session", "rotate_ip",
    "crawl_deeper", "generate_report", "done"
}

ALLOWED_ENGINES = {
    "e01_recon", "e02_crawler", "e05_js_analyzer",
    "e06_api_discoverer", "e07_auth_mapper", "e08_auth_bypass",
    "e09_jwt_engine", "e10_otp_engine", "e11_session_engine",
    "e12_idor_engine", "e13_priv_esc", "e14_bac_engine",
    "e15_mass_assignment", "e16_business_logic",
    "e17_payment_engine", "e18_workflow_engine",
    "e19_race_condition", "e20_injection_engine",
    "e21_xss_engine", "e22_ssrf_engine", "e23_xxe_engine",
    "e24_ssti_engine", "e25_graphql_engine",
    "e26_websocket_engine", "e27_api_engine",
    "e28_cors_engine", "e29_rate_limit_engine",
    "e30_param_pollution", "e31_fuzzer",
    "e32_lfi_engine", "e33_redirect_engine",
    "e34_takeover_engine", "e35_wpscan_engine", "none"
}


class AIBrain:
    def __init__(self, logger, ollama_model: str = OLLAMA_MODEL,
                 groq_key: str = GROQ_KEY):
        self.logger        = logger
        self.ollama_model  = ollama_model
        self.groq_key      = groq_key
        self._ollama_fails = 0
        self._call_count   = 0

    # ── Main Decision ──────────────────────────────────────
    def decide(self, context: Dict) -> Dict:
        prompt = self._build_prompt(context)
        model_used = "unknown"

        for attempt in range(MAX_RETRIES):
            raw = None
            if self._ollama_fails < 3:
                raw = self._call_ollama(prompt)
                model_used = "ollama"
            if raw is None and self.groq_key:
                raw = self._call_groq(prompt)
                model_used = "groq"
            if raw is None:
                return self._yaml_fallback(context)

            decision = self._parse_validate(raw)
            if decision:
                decision["_model"] = model_used
                self._call_count += 1
                self.logger.ai_decision(
                    decision["action"],
                    decision.get("reason", "")[:80],
                    decision.get("confidence", 50),
                    model_used
                )
                return decision
            prompt = self._correction_prompt(prompt, raw, attempt)

        return self._yaml_fallback(context)

    # ── Endpoint Classifier ────────────────────────────────
    def classify_endpoint(self, url: str, methods: list,
                          params: list, body_snippet: str = "") -> Dict:
        prompt = f"""Classify this HTTP endpoint. JSON only, no other text.
URL: {url}
Methods: {methods}
Parameters: {params}
Response snippet: {body_snippet[:300]}

Return ONLY this JSON:
{{"type":"AUTH|PAYMENT|ADMIN|PROFILE|FILE|API|GRAPHQL|WEBSOCKET|NORMAL",
  "sensitive":true|false,"priority":1-10,"auth_required":true|false}}"""
        raw = self._call_ollama(prompt, 8) or self._call_groq(prompt)
        if raw:
            parsed = self._extract_json(raw)
            if isinstance(parsed, dict):
                return parsed
        return {"type": "NORMAL", "sensitive": False,
                "priority": 3, "auth_required": False}

    # ── Response Analyzer ─────────────────────────────────
    def analyze_response(self, request_info: Dict,
                         response_info: Dict, baseline: Dict) -> Dict:
        size_diff = abs(response_info.get("body_size", 0) -
                        baseline.get("body_size", 0)) if baseline else 0
        prompt = f"""Analyze this HTTP response for vulnerabilities. JSON only.

Request: {request_info.get('method')} {request_info.get('url')}
Modified params: {request_info.get('params_modified')}
Response status: {response_info.get('status')}
Response size: {response_info.get('body_size')} bytes
Baseline size: {baseline.get('body_size', 0) if baseline else 'N/A'} bytes
Size diff: {size_diff} bytes
Body snippet: {response_info.get('body_snippet', '')[:400]}

Return ONLY:
{{"is_vulnerability":true|false,"type":"IDOR|XSS|SQLI|AUTH_BYPASS|PRIV_ESC|CORS|SSRF|SSTI|PAYMENT_BYPASS|OTHER|NONE",
  "severity":"CRITICAL|HIGH|MEDIUM|LOW|NONE","confidence":0-100,"reason":"one sentence"}}"""
        raw = self._call_ollama(prompt, 8) or self._call_groq(prompt)
        if raw:
            parsed = self._extract_json(raw)
            if isinstance(parsed, dict) and "confidence" in parsed:
                return parsed
        return {"is_vulnerability": False, "type": "NONE",
                "severity": "NONE", "confidence": 0, "reason": ""}

    # ── Confidence Scorer ──────────────────────────────────
    def score_confidence(self, finding: Dict,
                         reproductions: int, total: int) -> int:
        base    = int((reproductions / max(total, 1)) * 60)
        bonus   = {"CRITICAL": 25, "HIGH": 20,
                   "MEDIUM": 15, "LOW": 10}.get(finding.get("severity", "LOW"), 10)
        return min(100, base + bonus)

    # ── PoC Generator ─────────────────────────────────────
    def generate_poc(self, finding: Dict) -> str:
        prompt = f"""Write a Python proof-of-concept for this vulnerability.
Use only the requests library. Add comments. Return Python code only.

Type: {finding.get('type')}
Severity: {finding.get('severity')}
Endpoint: {finding.get('endpoint')}
Method: {finding.get('method')}
Parameter: {finding.get('param')}
Description: {finding.get('description')}"""
        raw = self._call_ollama(prompt, 20) or self._call_groq(prompt)
        if raw:
            code = re.sub(r"```python\n?|```\n?", "", raw).strip()
            return code
        return f"# PoC for {finding.get('type')} at {finding.get('endpoint')}\n# Manual verification required\n"

    # ── Chain Detector ────────────────────────────────────
    def detect_chains(self, findings: List[Dict],
                      patterns: List[Dict]) -> List[Dict]:
        if not findings or not patterns:
            return []
        prompt = f"""Identify attack chains from these findings. JSON array only.

Findings:
{json.dumps([{"id": f["id"], "type": f["type"],
              "severity": f["severity"]} for f in findings[:20]], indent=2)}

Known patterns:
{json.dumps([{"id": c["id"], "name": c["name"],
              "requires": c.get("requires", [])} for c in patterns[:20]], indent=2)}

Return array: [{{"chain_id":"C001","name":"...","severity":"CRITICAL",
  "finding_ids":[1,2],"steps":["step1","step2"],"confidence":85}}]
Return [] if no chains found."""
        raw = self._call_ollama(prompt, 15) or self._call_groq(prompt)
        if raw:
            parsed = self._extract_json(raw)
            if isinstance(parsed, list):
                return parsed
        return []

    # ── Ollama ────────────────────────────────────────────
    def _call_ollama(self, prompt: str,
                     timeout: int = OLLAMA_TIMEOUT) -> Optional[str]:
        try:
            resp = httpx.post(
                OLLAMA_URL,
                json={"model": self.ollama_model, "prompt": prompt,
                      "stream": False, "format": "json",
                      "options": {"temperature": 0.1, "num_predict": 600}},
                timeout=timeout
            )
            if resp.status_code == 200:
                self._ollama_fails = max(0, self._ollama_fails - 1)
                return resp.json().get("response", "")
        except Exception:
            self._ollama_fails += 1
        return None

    # ── Groq ──────────────────────────────────────────────
    def _call_groq(self, prompt: str) -> Optional[str]:
        if not self.groq_key:
            return None
        try:
            resp = httpx.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {self.groq_key}",
                         "Content-Type": "application/json"},
                json={"model": GROQ_MODEL,
                      "messages": [
                          {"role": "system",
                           "content": "You are a security AI. Return valid JSON only. No text outside JSON."},
                          {"role": "user", "content": prompt}
                      ],
                      "temperature": 0.1, "max_tokens": 600,
                      "response_format": {"type": "json_object"}},
                timeout=20
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
        except Exception:
            pass
        return None

    # ── JSON Parser ───────────────────────────────────────
    def _extract_json(self, raw: str) -> Optional[Any]:
        if not raw:
            return None
        text = re.sub(r"```(?:json)?\n?|```", "", raw).strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        return None

    def _parse_validate(self, raw: str) -> Optional[Dict]:
        parsed = self._extract_json(raw)
        if not isinstance(parsed, dict):
            return None
        decision = {
            "action":     parsed.get("action", "done"),
            "engine":     parsed.get("engine", "none"),
            "params":     parsed.get("params", {}),
            "reason":     parsed.get("reason", "AI decision"),
            "priority":   parsed.get("priority", "MEDIUM"),
            "confidence": 50,
            "fallback_if_fails": parsed.get("fallback_if_fails", "none"),
        }
        try:
            decision["confidence"] = max(0, min(100, int(parsed.get("confidence", 50))))
        except (TypeError, ValueError):
            decision["confidence"] = 50

        if decision["action"] not in ALLOWED_ACTIONS:
            return None
        if decision["engine"] not in ALLOWED_ENGINES:
            decision["engine"] = "none"
        if decision["confidence"] < MIN_CONFIDENCE and decision["action"] != "done":
            decision["confidence"] = MIN_CONFIDENCE
        return decision

    # ── Decision Prompt ───────────────────────────────────
    def _build_prompt(self, context: Dict) -> str:
        untested  = context.get("untested_nodes", [])[:8]
        findings  = context.get("findings", [])[-5:]
        recent    = context.get("recent_actions", [])[-5:]
        sessions  = [s["role"] for s in context.get("sessions", [])]
        iteration = context.get("iteration", 0)
        max_iter  = context.get("max_iterations", 300)
        elapsed   = context.get("elapsed_sec", 0)

        return f"""You are an autonomous penetration testing AI.
Return a single JSON decision. NO text outside the JSON object.

STATE:
  Iteration: {iteration}/{max_iter}
  Elapsed: {elapsed}s
  Sessions: {sessions}
  Untested endpoints: {len(untested)}
  Verified findings: {len(findings)}

UNTESTED ENDPOINTS (attack these):
{json.dumps([{"url": n.get("url"), "type": n.get("node_type"),
              "params": n.get("params")} for n in untested[:5]], indent=2)}

RECENT FINDINGS:
{json.dumps([{"type": f.get("type"), "severity": f.get("severity"),
              "endpoint": f.get("endpoint")} for f in findings[-3:]], indent=2)}

LAST ACTIONS (DO NOT REPEAT):
{json.dumps([{"action": a.get("action"), "engine": a.get("engine"),
              "params": a.get("params")} for a in recent], indent=2)}

RULES:
1. NEVER repeat action+engine+params from last actions
2. Priority: AUTH > PAYMENT > ADMIN > GRAPHQL > PROFILE > API > NORMAL
3. No untested endpoints left? Return action:"generate_report"
4. After report? Return action:"done"
5. confidence must be 50-100

ENGINES: e08_auth_bypass, e09_jwt_engine, e10_otp_engine, e12_idor_engine,
e13_priv_esc, e14_bac_engine, e15_mass_assignment, e16_business_logic,
e17_payment_engine, e19_race_condition, e20_injection_engine,
e21_xss_engine, e22_ssrf_engine, e25_graphql_engine,
e28_cors_engine, e29_rate_limit_engine, e32_lfi_engine, e31_fuzzer

Return EXACTLY:
{{"action":"run_engine","engine":"engine_name",
  "params":{{"url":"...","method":"GET"}},
  "reason":"one sentence why",
  "priority":"HIGH","confidence":75,
  "fallback_if_fails":"none"}}"""

    def _correction_prompt(self, original: str,
                            bad: str, attempt: int) -> str:
        return f"""Previous response was invalid JSON. Attempt {attempt+2}/{MAX_RETRIES}.
Bad response: {bad[:150]}

{original}

CRITICAL: Return ONLY a valid JSON object. No text before or after."""

    # ── YAML Fallback ─────────────────────────────────────
    def _yaml_fallback(self, context: Dict) -> Dict:
        self.logger.warn("AI unavailable — rule-based fallback")
        untested = context.get("untested_nodes", [])
        if untested:
            untested_sorted = sorted(
                untested,
                key=lambda n: {
                    "AUTH": 10, "PAYMENT": 9, "ADMIN": 8,
                    "GRAPHQL": 8, "FILE": 7, "PROFILE": 6,
                    "API": 5, "NORMAL": 3
                }.get(n.get("node_type", "NORMAL"), 3),
                reverse=True
            )
            node = untested_sorted[0]
            ntype = node.get("node_type", "NORMAL")
            engine_map = {
                "AUTH":    "e08_auth_bypass",
                "PAYMENT": "e17_payment_engine",
                "ADMIN":   "e13_priv_esc",
                "GRAPHQL": "e25_graphql_engine",
                "PROFILE": "e12_idor_engine",
                "FILE":    "e32_lfi_engine",
                "API":     "e12_idor_engine",
                "NORMAL":  "e21_xss_engine",
            }
            return {
                "action":     "run_engine",
                "engine":     engine_map.get(ntype, "e12_idor_engine"),
                "params":     {"url": node.get("url"), "method": "GET"},
                "reason":     f"Fallback: testing {ntype} endpoint",
                "priority":   "MEDIUM",
                "confidence": 60,
                "fallback_if_fails": "none",
                "_model":     "yaml_fallback"
            }
        findings = context.get("findings", [])
        if findings:
            return {"action": "generate_report", "engine": "none",
                    "params": {}, "reason": "All nodes tested",
                    "priority": "LOW", "confidence": 90,
                    "_model": "yaml_fallback"}
        return {"action": "done", "engine": "none", "params": {},
                "reason": "Nothing to test", "priority": "LOW",
                "confidence": 100, "_model": "yaml_fallback"}
