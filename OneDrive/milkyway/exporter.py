"""
exporter.py — Multi-Format Export Module
Exports findings to JSON, CSV, Markdown
MilkyWay Intelligence | Author: Sharlix
"""
import csv
import json
import os
from datetime import datetime
from typing import Dict, List


class Exporter:
    def __init__(self, db, out_dir: str, prefix: str):
        self.db      = db
        self.out_dir = out_dir
        self.prefix  = prefix

    def export_all(self):
        findings = self.db.get_all_findings()
        chains   = self.db.get_chains()
        actions  = self.db.get_recent_actions(500)

        self._export_json(findings, chains, actions)
        self._export_csv(findings)
        self._export_markdown(findings, chains)
        self._export_ai_log(actions)

    def _export_json(self, findings, chains, actions):
        data = {
            "exported":  datetime.now().isoformat(),
            "findings":  findings,
            "chains":    chains,
            "ai_actions": actions[:200],
            "stats": {
                "total":    len(findings),
                "verified": len([f for f in findings if f.get("status") == "verified"]),
                "critical": sum(1 for f in findings if f.get("severity") == "CRITICAL"),
                "high":     sum(1 for f in findings if f.get("severity") == "HIGH"),
            }
        }
        path = os.path.join(self.out_dir, f"{self.prefix}_findings.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        path2 = os.path.join(self.out_dir, f"{self.prefix}_chains.json")
        with open(path2, "w") as f:
            json.dump(chains, f, indent=2, default=str)

        path3 = os.path.join(self.out_dir, f"{self.prefix}_ai_log.json")
        with open(path3, "w") as f:
            json.dump(actions, f, indent=2, default=str)

    def _export_csv(self, findings: List[Dict]):
        path = os.path.join(self.out_dir, f"{self.prefix}_findings.csv")
        if not findings:
            return
        fields = ["id", "type", "severity", "endpoint", "param",
                  "method", "description", "confidence", "status",
                  "found_at", "verified_at"]
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for finding in findings:
                writer.writerow(finding)

    def _export_markdown(self, findings: List[Dict], chains: List[Dict]):
        path  = os.path.join(self.out_dir, f"{self.prefix}_report.md")
        lines = [
            "# Penetration Test Report",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
            f"| Severity | Count |",
            f"|----------|-------|",
        ]
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            count = sum(1 for f in findings if f.get("severity") == sev)
            lines.append(f"| {sev} | {count} |")

        lines += ["", "## Findings", ""]
        for f in findings:
            lines += [
                f"### [{f.get('severity','')}] {f.get('type','')}",
                f"**Endpoint:** `{f.get('endpoint','')}`  ",
                f"**Parameter:** `{f.get('param','')}`  ",
                f"**Method:** `{f.get('method','')}`  ",
                f"**Status:** {f.get('status','')} ({f.get('confidence',0)}%)  ",
                "",
                f"{f.get('description','')}",
                "",
                "**Proof Request:**",
                f"```\n{f.get('proof_request','N/A')}\n```",
                "",
            ]

        if chains:
            lines += ["## Attack Chains", ""]
            for ch in chains:
                lines.append(f"### {ch.get('name','')}")
                lines.append(f"**Severity:** {ch.get('severity','')}  ")
                lines.append("")
                steps = ch.get("steps", [])
                if isinstance(steps, str):
                    try:
                        steps = json.loads(steps)
                    except Exception:
                        steps = []
                for i, step in enumerate(steps, 1):
                    lines.append(f"{i}. {step}")
                lines.append("")

        with open(path, "w") as f:
            f.write("\n".join(lines))

    def _export_ai_log(self, actions: List[Dict]):
        path  = os.path.join(self.out_dir, f"{self.prefix}_action_history.json")
        with open(path, "w") as f:
            json.dump({
                "total_actions": len(actions),
                "actions":       actions
            }, f, indent=2, default=str)
