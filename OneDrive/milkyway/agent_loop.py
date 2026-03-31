"""
agent_loop.py — Main AI Infinite Loop
READ → DECIDE → EXECUTE → LEARN → REPEAT
MilkyWay Intelligence | Author: Sharlix
"""
import asyncio
import time
from typing import Dict, List


class AgentLoop:
    def __init__(self, db, ai_brain, dispatcher, chain_detector,
                 logger, max_iterations: int = 300,
                 max_time_sec: int = 14400):
        self.db             = db
        self.ai             = ai_brain
        self.dispatcher     = dispatcher
        self.chain_detector = chain_detector
        self.logger         = logger
        self.max_iterations = max_iterations
        self.max_time_sec   = max_time_sec
        self.iteration      = 0
        self.start_time     = 0
        self.no_progress    = 0

    async def run(self) -> Dict:
        self.logger.section("PHASE 3: AI AGENT LOOP")
        self.start_time = time.time()
        self.iteration  = 0
        summary = {"iterations": 0, "findings": 0, "chains": 0, "duration": 0}

        while True:
            self.iteration += 1
            elapsed = time.time() - self.start_time

            # ── Safety limits ──────────────────────────────
            if self.iteration > self.max_iterations:
                self.logger.warn(f"Max iterations ({self.max_iterations}) reached")
                break
            if elapsed > self.max_time_sec:
                self.logger.warn(f"Max time ({self.max_time_sec}s) reached")
                break
            if self.no_progress >= 40:
                self.logger.warn("40 iterations with no new findings — stopping")
                break

            # ── Check if anything left to test ────────────
            untested = self.db.untested_count()
            if untested == 0 and self.iteration > 5:
                self.logger.info("All endpoints tested — generating report")
                break

            # ── Build context ──────────────────────────────
            context = self._build_context()

            # ── AI Decision ────────────────────────────────
            decision = self.ai.decide(context)

            # ── Terminal actions ───────────────────────────
            if decision["action"] in ("done", "generate_report"):
                self.logger.info(f"AI: {decision['action']} → ending loop")
                break

            # ── Dedup check ────────────────────────────────
            if self._is_duplicate(decision):
                self.logger.warn(
                    f"Skip duplicate: {decision['action']}/{decision['engine']}"
                )
                self.no_progress += 1
                continue

            # ── Execute ────────────────────────────────────
            t0     = time.time()
            result = await self.dispatcher.dispatch(decision)
            dur_ms = int((time.time() - t0) * 1000)

            # ── Log action ─────────────────────────────────
            finding_ids = [
                f.get("id") for f in result.get("findings", []) if f.get("id")
            ]
            self.db.log_action(
                action=decision["action"],
                engine=decision.get("engine", "none"),
                params=decision.get("params", {}),
                reason=decision.get("reason", ""),
                ai_model=decision.get("_model", "unknown"),
                confidence=decision.get("confidence", 0),
                result={"success": result.get("success"),
                        "count": result.get("count", 0)},
                duration_ms=dur_ms,
                success=result.get("success", False),
                finding_ids=finding_ids
            )

            # ── Progress tracking ──────────────────────────
            if finding_ids:
                self.no_progress = 0
                all_findings = self.db.get_findings("verified")
                if all_findings:
                    self.chain_detector.detect(all_findings)
            else:
                self.no_progress += 1

            # ── Terminal from result ───────────────────────
            if result.get("terminal"):
                break

            # ── Status every 10 iterations ─────────────────
            if self.iteration % 10 == 0:
                fc = len(self.db.get_all_findings())
                self.logger.info(
                    f"Iter {self.iteration} | Findings: {fc} | "
                    f"Elapsed: {int(elapsed)}s | "
                    f"Untested: {self.db.untested_count()}"
                )

        # Final chain detection
        all_findings = self.db.get_all_findings()
        chains       = self.chain_detector.detect(all_findings)
        elapsed      = time.time() - self.start_time

        summary.update({
            "iterations": self.iteration,
            "findings":   len(all_findings),
            "chains":     len(chains),
            "duration":   elapsed
        })
        self.logger.done(len(all_findings), len(chains), elapsed)
        return summary

    def _build_context(self) -> Dict:
        return {
            "iteration":      self.iteration,
            "max_iterations": self.max_iterations,
            "elapsed_sec":    int(time.time() - self.start_time),
            "untested_nodes": self.db.get_untested_nodes(limit=15),
            "findings":       self.db.get_findings("verified")[-10:],
            "recent_actions": self.db.get_recent_actions(limit=20),
            "sessions":       self.db.get_all_sessions(),
            "chains":         self.db.get_chains(),
        }

    def _is_duplicate(self, decision: Dict) -> bool:
        return self.db.action_already_done(
            decision["action"],
            decision.get("engine", "none"),
            decision.get("params", {})
        )
