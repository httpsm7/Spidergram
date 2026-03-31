"""
ai/report_ai.py — AI-Written Report Text Generator
Generates human-quality executive summaries and remediation advice
MilkyWay Intelligence | Author: Sharlix
"""
from typing import Dict, List


REMEDIATION = {
    "IDOR":                "Implement server-side authorization checks for all object references. Never trust client-supplied IDs without verifying the requester owns the resource.",
    "JWT_NONE_ALG":        "Reject JWTs with 'none' algorithm. Use a whitelist of allowed algorithms. Verify the signature on every request.",
    "JWT_WEAK_SECRET":     "Use cryptographically random JWT secrets of at least 256 bits. Store secrets in a secrets manager, never in code.",
    "JWT_ALG_CONFUSION":   "Explicitly specify allowed algorithms. Never use the algorithm from the token header without validation.",
    "SQLI":                "Use parameterized queries / prepared statements. Never concatenate user input into SQL. Apply input validation and output encoding.",
    "XSS":                 "Encode all output in the correct context (HTML/JS/URL). Implement a strong Content Security Policy. Use modern frameworks that auto-escape.",
    "SSRF":                "Whitelist allowed destination IPs/domains. Block requests to private IP ranges. Disable unnecessary URL fetching features.",
    "LFI":                 "Never pass user input to file system functions. Use a whitelist of allowed file paths. Disable PHP allow_url_include.",
    "XXE":                 "Disable XML external entity processing in all XML parsers. Use safe XML parsing libraries.",
    "SSTI":                "Never render user input as a template. Use sandboxed template engines. Validate and escape all template variables.",
    "DEFAULT_CREDS":       "Change all default credentials immediately. Implement a strong password policy. Use MFA for all admin accounts.",
    "OTP_NO_RATELIMIT":    "Implement rate limiting on OTP endpoints (max 5 attempts). Lock account or increase delay after failed attempts. Use exponential backoff.",
    "CORS":                "Use a strict whitelist of allowed origins. Never reflect the Origin header directly. Avoid Access-Control-Allow-Credentials with wildcard origins.",
    "PAYMENT_BYPASS":      "Validate all prices server-side. Never trust client-supplied pricing. Verify payment completion before fulfilling orders.",
    "RACE_CONDITION":      "Use database-level locking (transactions/atomic operations). Implement idempotency keys for critical operations.",
    "MASS_ASSIGNMENT":     "Whitelist allowed parameters in request handlers. Never bind all request parameters to model objects.",
    "PRIV_ESC":            "Implement role-based access control (RBAC) at the server layer. Verify user role on every request to privileged endpoints.",
    "BAC_UNAUTH":          "Require authentication on all non-public endpoints. Use a middleware/decorator pattern to enforce auth globally.",
    "SESSION_FIXATION":    "Regenerate session ID after successful login. Invalidate old session ID immediately.",
    "OPEN_REDIRECT":       "Use a whitelist of allowed redirect destinations. Never redirect to user-supplied URLs without validation.",
    "SUBDOMAIN_TAKEOVER":  "Remove DNS records pointing to decommissioned services. Monitor for unclaimed CNAME targets.",
    "WP_USER_ENUM":        "Disable user enumeration via REST API. Set JSON API to require authentication.",
    "GRAPHQL_INTROSPECTION": "Disable GraphQL introspection in production. Implement query depth limiting and query cost analysis.",
    "HTTP_VERB_BYPASS":    "Implement consistent access controls across all HTTP methods. Block unused HTTP verbs at the WAF/load balancer.",
}

SEVERITY_DESCRIPTIONS = {
    "CRITICAL": "poses an immediate and critical threat — immediate remediation required",
    "HIGH":     "represents a significant security risk — remediate within 24 hours",
    "MEDIUM":   "represents a moderate risk — remediate within 30 days",
    "LOW":      "represents a low risk — remediate at next scheduled maintenance",
}


class ReportAI:
    def __init__(self, ai_brain=None):
        self.ai = ai_brain

    def executive_summary(self, findings: List[Dict], chains: List[Dict],
                          target: str, duration: float) -> str:
        total    = len(findings)
        critical = sum(1 for f in findings if f.get("severity") == "CRITICAL")
        high     = sum(1 for f in findings if f.get("severity") == "HIGH")
        medium   = sum(1 for f in findings if f.get("severity") == "MEDIUM")
        low      = sum(1 for f in findings if f.get("severity") == "LOW")

        if total == 0:
            return (f"The autonomous security assessment of {target} completed "
                    f"in {int(duration)}s with no verified vulnerabilities detected. "
                    f"The target appears to implement basic security controls, "
                    f"though a manual assessment is recommended for comprehensive coverage.")

        risk_level = ("CRITICAL" if critical > 0 else
                      "HIGH" if high > 0 else
                      "MEDIUM" if medium > 0 else "LOW")

        types = list({f.get("type","") for f in findings})[:5]

        summary = (
            f"The autonomous security assessment of {target} identified "
            f"{total} security {'vulnerability' if total == 1 else 'vulnerabilities'} "
            f"across {duration/60:.1f} minutes of testing. "
            f"The overall risk rating is {risk_level}. "
        )

        if critical:
            summary += (f"{critical} critical {'issue' if critical==1 else 'issues'} "
                        f"{'requires' if critical==1 else 'require'} immediate attention. ")
        if high:
            summary += f"{high} high-severity {'finding was' if high==1 else 'findings were'} identified. "

        if chains:
            summary += (
                f"Additionally, {len(chains)} attack chain "
                f"{'was' if len(chains)==1 else 'were'} identified — "
                f"combinations of vulnerabilities that could be chained for "
                f"greater impact including potential account takeover or data breach. "
            )

        summary += (
            f"Key vulnerability classes: {', '.join(types)}. "
            f"Immediate remediation is recommended for all critical and high findings."
        )

        # Try AI enhancement
        if self.ai and hasattr(self.ai, "_call_groq"):
            prompt = (
                f"Write a 3-sentence professional executive summary for a penetration test report. "
                f"Target: {target}. "
                f"Findings: {critical} critical, {high} high, {medium} medium, {low} low. "
                f"Vulnerability types: {', '.join(types)}. "
                f"Chains: {len(chains)}. Duration: {int(duration)}s. "
                f"Return only the summary text, no JSON."
            )
            try:
                enhanced = self.ai._call_groq(prompt)
                if enhanced and len(enhanced) > 100:
                    return enhanced
            except Exception:
                pass

        return summary

    def remediation(self, vuln_type: str) -> str:
        return REMEDIATION.get(
            vuln_type,
            f"Apply defense-in-depth principles for {vuln_type}. "
            f"Consult OWASP guidelines for specific remediation steps. "
            f"Conduct a manual code review of affected components."
        )

    def finding_narrative(self, finding: Dict) -> str:
        ftype = finding.get("type", "")
        sev   = finding.get("severity", "MEDIUM")
        ep    = finding.get("endpoint", "")
        param = finding.get("param", "")
        sev_desc = SEVERITY_DESCRIPTIONS.get(sev, "represents a security risk")

        return (
            f"A {ftype} vulnerability was identified at {ep} "
            f"that {sev_desc}. "
            f"{'The vulnerable parameter is ' + repr(param) + '. ' if param else ''}"
            f"{self.remediation(ftype)}"
        )
