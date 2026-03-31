"""
database.py — Full SQLite Agent Memory (10 Tables)
MilkyWay Intelligence | Author: Sharlix
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS nodes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT UNIQUE,
            method      TEXT DEFAULT '["GET"]',
            params      TEXT DEFAULT '[]',
            node_type   TEXT DEFAULT 'NORMAL',
            auth_req    INTEGER DEFAULT 0,
            role_req    TEXT DEFAULT 'none',
            tech        TEXT DEFAULT '',
            sensitive   INTEGER DEFAULT 0,
            tested      INTEGER DEFAULT 0,
            priority    INTEGER DEFAULT 5,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS edges (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            from_url    TEXT,
            to_url      TEXT,
            edge_type   TEXT DEFAULT 'NAVIGATE',
            action_desc TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            role        TEXT UNIQUE,
            token       TEXT,
            cookies     TEXT DEFAULT '{}',
            user_id     TEXT,
            status      TEXT DEFAULT 'active',
            expires_at  TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS requests (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            url              TEXT,
            method           TEXT,
            req_headers      TEXT DEFAULT '{}',
            req_body         TEXT DEFAULT '',
            resp_status      INTEGER DEFAULT 0,
            resp_headers     TEXT DEFAULT '{}',
            resp_body        TEXT DEFAULT '',
            resp_time_ms     INTEGER DEFAULT 0,
            session_role     TEXT DEFAULT 'unauth',
            source_page      TEXT DEFAULT '',
            captured_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS baselines (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            url              TEXT,
            method           TEXT DEFAULT 'GET',
            status_code      INTEGER DEFAULT 0,
            body_size        INTEGER DEFAULT 0,
            resp_time_ms     INTEGER DEFAULT 0,
            structure_hash   TEXT DEFAULT '',
            content_type     TEXT DEFAULT '',
            session_role     TEXT DEFAULT 'unauth',
            created_at       TEXT DEFAULT (datetime('now')),
            UNIQUE(url, method, session_role)
        );

        CREATE TABLE IF NOT EXISTS findings (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            type             TEXT NOT NULL,
            severity         TEXT NOT NULL,
            endpoint         TEXT NOT NULL,
            param            TEXT DEFAULT '',
            method           TEXT DEFAULT 'GET',
            proof_request    TEXT DEFAULT '',
            proof_response   TEXT DEFAULT '',
            description      TEXT DEFAULT '',
            confidence       INTEGER DEFAULT 0,
            status           TEXT DEFAULT 'unverified',
            poc_file         TEXT DEFAULT '',
            found_at         TEXT DEFAULT (datetime('now')),
            verified_at      TEXT
        );

        CREATE TABLE IF NOT EXISTS chains (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            chain_id     TEXT UNIQUE,
            name         TEXT,
            severity     TEXT DEFAULT 'HIGH',
            finding_ids  TEXT DEFAULT '[]',
            steps        TEXT DEFAULT '[]',
            poc_steps    TEXT DEFAULT '[]',
            confidence   INTEGER DEFAULT 0,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ai_actions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            action      TEXT NOT NULL,
            engine      TEXT DEFAULT 'none',
            params      TEXT DEFAULT '{}',
            reason      TEXT DEFAULT '',
            ai_model    TEXT DEFAULT 'unknown',
            confidence  INTEGER DEFAULT 0,
            result      TEXT DEFAULT '{}',
            finding_ids TEXT DEFAULT '[]',
            duration_ms INTEGER DEFAULT 0,
            success     INTEGER DEFAULT 1,
            timestamp   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS js_secrets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT,
            secret_type TEXT,
            value       TEXT,
            found_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS scan_state (
            key         TEXT PRIMARY KEY,
            value       TEXT,
            updated_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tech_stack (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT,
            tech_name   TEXT,
            tech_value  TEXT,
            detected_at TEXT DEFAULT (datetime('now'))
        );
        """)
        self.conn.commit()

    # ── Nodes ──────────────────────────────────────────────
    def add_node(self, url: str, method: list = None, params: list = None,
                 node_type: str = "NORMAL", auth_req: bool = False,
                 role_req: str = "none", tech: str = "",
                 sensitive: bool = False, priority: int = 5) -> int:
        try:
            cur = self.conn.execute(
                """INSERT OR IGNORE INTO nodes
                   (url,method,params,node_type,auth_req,role_req,tech,sensitive,priority)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (url, json.dumps(method or ["GET"]), json.dumps(params or []),
                 node_type, int(auth_req), role_req, tech, int(sensitive), priority)
            )
            self.conn.commit()
            return cur.lastrowid or 0
        except Exception:
            return 0

    def get_untested_nodes(self, limit: int = 20) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE tested=0 ORDER BY priority DESC, id ASC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_nodes(self) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM nodes ORDER BY priority DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_nodes_by_type(self, node_type: str) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE node_type=? ORDER BY priority DESC",
            (node_type,)
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_tested(self, url: str):
        self.conn.execute("UPDATE nodes SET tested=1 WHERE url=?", (url,))
        self.conn.commit()

    def node_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()
        return row["c"] if row else 0

    def untested_count(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) as c FROM nodes WHERE tested=0"
        ).fetchone()
        return row["c"] if row else 0

    # ── Edges ──────────────────────────────────────────────
    def add_edge(self, from_url: str, to_url: str,
                 edge_type: str = "NAVIGATE", action_desc: str = ""):
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO edges (from_url,to_url,edge_type,action_desc) VALUES (?,?,?,?)",
                (from_url, to_url, edge_type, action_desc)
            )
            self.conn.commit()
        except Exception:
            pass

    # ── Sessions ───────────────────────────────────────────
    def upsert_session(self, role: str, token: str = None,
                       cookies: dict = None, user_id: str = None,
                       expires_at: str = None):
        self.conn.execute(
            "INSERT OR REPLACE INTO sessions (role,token,cookies,user_id,expires_at) VALUES (?,?,?,?,?)",
            (role, token, json.dumps(cookies or {}), user_id, expires_at)
        )
        self.conn.commit()

    def get_session(self, role: str) -> Optional[Dict]:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE role=? AND status='active'", (role,)
        ).fetchone()
        return dict(row) if row else None

    def get_all_sessions(self) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM sessions WHERE status='active'"
        ).fetchall()
        return [dict(r) for r in rows]

    def invalidate_session(self, role: str):
        self.conn.execute(
            "UPDATE sessions SET status='expired' WHERE role=?", (role,)
        )
        self.conn.commit()

    # ── Baselines ──────────────────────────────────────────
    def save_baseline(self, url: str, method: str = "GET",
                      status_code: int = 0, body_size: int = 0,
                      resp_time_ms: int = 0, structure_hash: str = "",
                      content_type: str = "", session_role: str = "unauth"):
        self.conn.execute(
            """INSERT OR REPLACE INTO baselines
               (url,method,status_code,body_size,resp_time_ms,structure_hash,content_type,session_role)
               VALUES (?,?,?,?,?,?,?,?)""",
            (url, method, status_code, body_size, resp_time_ms,
             structure_hash, content_type, session_role)
        )
        self.conn.commit()

    def get_baseline(self, url: str, method: str = "GET",
                     session_role: str = "unauth") -> Optional[Dict]:
        row = self.conn.execute(
            "SELECT * FROM baselines WHERE url=? AND method=? AND session_role=?",
            (url, method, session_role)
        ).fetchone()
        return dict(row) if row else None

    # ── Findings ───────────────────────────────────────────
    def add_finding(self, type: str, severity: str, endpoint: str,
                    description: str = "", confidence: int = 70,
                    param: str = "", method: str = "GET",
                    proof_request: str = "", proof_response: str = "") -> int:
        existing = self.conn.execute(
            "SELECT id FROM findings WHERE type=? AND endpoint=? AND param=?",
            (type, endpoint, param)
        ).fetchone()
        if existing:
            return existing["id"]
        cur = self.conn.execute(
            """INSERT INTO findings
               (type,severity,endpoint,param,method,proof_request,proof_response,description,confidence)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (type, severity, endpoint, param, method,
             proof_request[:2000], proof_response[:2000], description, confidence)
        )
        self.conn.commit()
        return cur.lastrowid

    def verify_finding(self, finding_id: int, confidence: int):
        self.conn.execute(
            "UPDATE findings SET status='verified',confidence=?,verified_at=datetime('now') WHERE id=?",
            (confidence, finding_id)
        )
        self.conn.commit()

    def mark_false_positive(self, finding_id: int):
        self.conn.execute(
            "UPDATE findings SET status='false_positive' WHERE id=?", (finding_id,)
        )
        self.conn.commit()

    def get_findings(self, status: str = "verified") -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM findings WHERE status=? ORDER BY confidence DESC",
            (status,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_all_findings(self) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM findings ORDER BY confidence DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Chains ─────────────────────────────────────────────
    def add_chain(self, chain_id: str, name: str, severity: str,
                  finding_ids: list, steps: list,
                  poc_steps: list = None, confidence: int = 80) -> int:
        existing = self.conn.execute(
            "SELECT id FROM chains WHERE chain_id=?", (chain_id,)
        ).fetchone()
        if existing:
            return existing["id"]
        cur = self.conn.execute(
            "INSERT INTO chains (chain_id,name,severity,finding_ids,steps,poc_steps,confidence) VALUES (?,?,?,?,?,?,?)",
            (chain_id, name, severity, json.dumps(finding_ids),
             json.dumps(steps), json.dumps(poc_steps or []), confidence)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_chains(self) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM chains ORDER BY confidence DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # ── AI Actions ─────────────────────────────────────────
    def log_action(self, action: str, engine: str = "none",
                   params: dict = None, reason: str = "",
                   ai_model: str = "unknown", confidence: int = 0,
                   result: dict = None, duration_ms: int = 0,
                   success: bool = True, finding_ids: list = None) -> int:
        cur = self.conn.execute(
            """INSERT INTO ai_actions
               (action,engine,params,reason,ai_model,confidence,result,finding_ids,duration_ms,success)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (action, engine, json.dumps(params or {}), reason, ai_model,
             confidence, json.dumps(result or {}),
             json.dumps(finding_ids or []), duration_ms, int(success))
        )
        self.conn.commit()
        return cur.lastrowid

    def get_recent_actions(self, limit: int = 20) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM ai_actions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def action_already_done(self, action: str, engine: str,
                            params: dict) -> bool:
        params_str = json.dumps(params, sort_keys=True)
        row = self.conn.execute(
            "SELECT id FROM ai_actions WHERE action=? AND engine=? AND params=? AND success=1",
            (action, engine, params_str)
        ).fetchone()
        return row is not None

    # ── JS Secrets ─────────────────────────────────────────
    def add_js_secret(self, url: str, secret_type: str, value: str):
        self.conn.execute(
            "INSERT INTO js_secrets (url,secret_type,value) VALUES (?,?,?)",
            (url, secret_type, value[:500])
        )
        self.conn.commit()

    def get_js_secrets(self) -> List[Dict]:
        rows = self.conn.execute("SELECT * FROM js_secrets").fetchall()
        return [dict(r) for r in rows]

    # ── State ──────────────────────────────────────────────
    def set_state(self, key: str, value: Any):
        self.conn.execute(
            "INSERT OR REPLACE INTO scan_state (key,value,updated_at) VALUES (?,?,datetime('now'))",
            (key, json.dumps(value))
        )
        self.conn.commit()

    def get_state(self, key: str, default=None) -> Any:
        row = self.conn.execute(
            "SELECT value FROM scan_state WHERE key=?", (key,)
        ).fetchone()
        return json.loads(row["value"]) if row else default

    def close(self):
        try:
            self.conn.commit()
            self.conn.close()
        except Exception:
            pass
