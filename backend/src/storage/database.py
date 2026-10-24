import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import aiosqlite

from src.config import settings
from src.models import (
    Conversation,
    Message,
    ApprovalRequest,
    ApprovalStatus,
    AuditLogEntry,
    ProposedAction
)


class DatabaseManager:
    """Enterprise SQLite database manager operating in WAL mode."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or settings.database_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def init_sync_db(self):
        """Synchronously initialize tables, indexes, and WAL pragma."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")

            # 1. Conversations
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # 2. Messages
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    content TEXT NOT NULL,
                    citations_json TEXT NOT NULL DEFAULT '[]',
                    action_json TEXT,
                    approval_json TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);")

            # 3. Approvals
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    requester_id TEXT NOT NULL,
                    requester_name TEXT NOT NULL,
                    action_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    required_role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    decision_by TEXT,
                    decision_by_name TEXT,
                    decision_at TEXT,
                    decision_reason TEXT
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_appr_status ON approvals(status);")

            # 4. Audit Logs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    actor_name TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    target_environment TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    masked_payload_json TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_corr ON audit_logs(correlation_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp);")

            # 5. Checkpoints (Durable Workflow State)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS durable_checkpoints (
                    run_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.commit()

    async def init_db(self):
        """Asynchronously initialize tables, indexes, and WAL pragma."""
        self.init_sync_db()

    @asynccontextmanager
    async def get_connection(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA synchronous=NORMAL;")
        await conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
        finally:
            await conn.close()

    # --- Conversation Operations ---
    async def create_conversation(self, conv: Conversation):
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO conversations (id, user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (conv.id, conv.user_id, conv.title, conv.created_at, conv.updated_at))
            await conn.commit()

    async def list_conversations(self, user_id: str) -> List[Conversation]:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)
            )
            rows = await cursor.fetchall()
            return [Conversation(**dict(r)) for r in rows]

    async def get_conversation(self, conv_id: str) -> Optional[Conversation]:
        async with self.get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
            row = await cursor.fetchone()
            return Conversation(**dict(row)) if row else None

    # --- Message Operations ---
    async def add_message(self, msg: Message):
        async with self.get_connection() as conn:
            citations_str = json.dumps([c.model_dump() for c in msg.policy_citations])
            action_str = json.dumps(msg.proposed_action.model_dump(mode="json")) if msg.proposed_action else None
            appr_str = json.dumps(msg.approval_request.model_dump(mode="json")) if msg.approval_request else None

            await conn.execute("""
                INSERT INTO messages (id, conversation_id, sender, content, citations_json, action_json, approval_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (msg.id, msg.conversation_id, msg.sender, msg.content, citations_str, action_str, appr_str, msg.timestamp))

            # Update conversation timestamp
            await conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (msg.timestamp, msg.conversation_id)
            )
            await conn.commit()

    async def get_messages(self, conv_id: str) -> List[Message]:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC", (conv_id,)
            )
            rows = await cursor.fetchall()
            msgs = []
            for r in rows:
                d = dict(r)
                citations = json.loads(d["citations_json"]) if d["citations_json"] else []
                action = json.loads(d["action_json"]) if d["action_json"] else None
                appr = json.loads(d["approval_json"]) if d["approval_json"] else None
                msgs.append(Message(
                    id=d["id"],
                    conversation_id=d["conversation_id"],
                    sender=d["sender"],
                    content=d["content"],
                    policy_citations=citations,
                    proposed_action=ProposedAction(**action) if action else None,
                    approval_request=ApprovalRequest(**appr) if appr else None,
                    timestamp=d["timestamp"]
                ))
            return msgs

    # --- Approval Operations ---
    async def save_approval_request(self, req: ApprovalRequest):
        async with self.get_connection() as conn:
            action_str = json.dumps(req.proposed_action.model_dump(mode="json"))
            await conn.execute("""
                INSERT OR REPLACE INTO approvals
                (id, run_id, conversation_id, requester_id, requester_name, action_json, status, required_role, created_at, decision_by, decision_by_name, decision_at, decision_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                req.id, req.run_id, req.conversation_id, req.requester_id, req.requester_name,
                action_str, req.status.value, req.required_role.value, req.created_at,
                req.decision_by, req.decision_by_name, req.decision_at, req.decision_reason
            ))
            await conn.commit()

    async def get_approval(self, appr_id: str) -> Optional[ApprovalRequest]:
        async with self.get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM approvals WHERE id = ?", (appr_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            action = json.loads(d["action_json"])
            return ApprovalRequest(
                id=d["id"],
                run_id=d["run_id"],
                conversation_id=d["conversation_id"],
                requester_id=d["requester_id"],
                requester_name=d["requester_name"],
                proposed_action=ProposedAction(**action),
                status=ApprovalStatus(d["status"]),
                required_role=d["required_role"],
                created_at=d["created_at"],
                decision_by=d["decision_by"],
                decision_by_name=d["decision_by_name"],
                decision_at=d["decision_at"],
                decision_reason=d["decision_reason"]
            )

    async def list_pending_approvals(self) -> List[ApprovalRequest]:
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM approvals WHERE status = ? ORDER BY created_at DESC", (ApprovalStatus.PENDING.value,)
            )
            rows = await cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                action = json.loads(d["action_json"])
                results.append(ApprovalRequest(
                    id=d["id"],
                    run_id=d["run_id"],
                    conversation_id=d["conversation_id"],
                    requester_id=d["requester_id"],
                    requester_name=d["requester_name"],
                    proposed_action=ProposedAction(**action),
                    status=ApprovalStatus(d["status"]),
                    required_role=d["required_role"],
                    created_at=d["created_at"],
                    decision_by=d["decision_by"],
                    decision_by_name=d["decision_by_name"],
                    decision_at=d["decision_at"],
                    decision_reason=d["decision_reason"]
                ))
            return results

    # --- Audit Operations ---
    async def record_audit(self, entry: AuditLogEntry):
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT INTO audit_logs
                (timestamp, correlation_id, actor_id, actor_name, actor_role, action_type, target_environment, status, summary, masked_payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.timestamp, entry.correlation_id, entry.actor_id, entry.actor_name, entry.actor_role,
                entry.action_type, entry.target_environment, entry.status, entry.summary, entry.masked_payload_json
            ))
            await conn.commit()

    async def get_audit_logs(self, limit: int = 50, correlation_id: Optional[str] = None) -> List[AuditLogEntry]:
        async with self.get_connection() as conn:
            if correlation_id:
                cursor = await conn.execute(
                    "SELECT * FROM audit_logs WHERE correlation_id = ? ORDER BY id DESC LIMIT ?",
                    (correlation_id, limit)
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)
                )
            rows = await cursor.fetchall()
            return [AuditLogEntry(**dict(r)) for r in rows]

    # --- Checkpoints (Durable State) ---
    async def save_checkpoint(self, run_id: str, conv_id: str, state_dict: dict, status: str = "WAITING_APPROVAL"):
        async with self.get_connection() as conn:
            now_iso = datetime.now(timezone.utc).isoformat()
            state_str = json.dumps(state_dict)
            await conn.execute("""
                INSERT OR REPLACE INTO durable_checkpoints
                (run_id, conversation_id, state_json, status, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (run_id, conv_id, state_str, status, now_iso))
            await conn.commit()

    async def get_checkpoint(self, run_id: str) -> Optional[dict]:
        async with self.get_connection() as conn:
            cursor = await conn.execute("SELECT state_json, status FROM durable_checkpoints WHERE run_id = ?", (run_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            res = json.loads(row["state_json"])
            res["status"] = row["status"]
            return res


db = DatabaseManager()
