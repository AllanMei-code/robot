# -*- coding: utf-8 -*-
import re
import os
import sqlite3
import threading
import hashlib
from datetime import datetime

def _fts_make_query(text: str, max_terms: int = 8) -> str | None:
    """
    把原始文本转换为安全的 FTS5 MATCH 查询：
    - 仅保留“单词字符”（支持 Unicode）
    - 每个词用 "..." 包住
    - 用 AND 连接，避免引号/斜杠等导致语法错误
    """
    text = (text or "").replace('"', " ")
    terms = re.findall(r"\w+", text, flags=re.UNICODE)
    terms = [t for t in terms if t.strip()]
    if not terms:
        return None
    terms = terms[:max_terms]
    return " AND ".join(f'"{t}"' for t in terms)


_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_DB_PATH = os.path.join(_DB_DIR, "bot.db")

_lock = threading.RLock()
_conn = None

def _connect():
    global _conn
    if _conn is None:
        os.makedirs(_DB_DIR, exist_ok=True)
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn

def init_db():
    conn = _connect()
    with _lock, conn:
        # 会话日志
        conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            conv_id TEXT,
            role TEXT,           -- 'client' / 'agent' / 'bot'
            lang TEXT,           -- 'fr' / 'zh' / ...
            text TEXT
        );
        """)
        # 知识库
        conn.execute("""
        CREATE TABLE IF NOT EXISTS knowledge(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q_fr TEXT,
            q_zh TEXT,
            a_zh TEXT,
            q_hash TEXT UNIQUE,
            hits INTEGER DEFAULT 0,
            upvotes INTEGER DEFAULT 0,
            source TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        """)
        # 设置表（持久化手动开关）
        conn.execute("""
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            val TEXT
        );
        """)
        # FTS5
        conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
        USING fts5(question_all, answer_zh, content='');
        """)
        conn.commit()

def _norm(s: str) -> str:
    return (s or "").strip()

def _hash(s: str) -> str:
    import hashlib as _h
    return _h.sha1((_norm(s)).encode("utf-8")).hexdigest()

def log_message(role: str, lang: str, text: str, conv_id: str = None):
    conn = _connect()
    with _lock, conn:
        conn.execute(
            "INSERT INTO conversations(ts, conv_id, role, lang, text) VALUES(?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), conv_id, role, lang, text)
        )
        conn.commit()

def upsert_qa(q_fr: str, q_zh: str, a_zh: str, source: str = "agent"):
    q_fr = _norm(q_fr); q_zh = _norm(q_zh); a_zh = _norm(a_zh)
    if not q_zh or not a_zh:
        return None

    qh = _hash(q_zh)
    now = datetime.now().isoformat(timespec="seconds")
    conn = _connect()
    with _lock, conn:
        cur = conn.execute("SELECT id FROM knowledge WHERE q_hash=?", (qh,))
        row = cur.fetchone()
        if row:
            kid = row["id"]
            conn.execute("""
                UPDATE knowledge
                   SET q_fr=COALESCE(NULLIF(?, ''), q_fr),
                       a_zh=?,
                       updated_at=?,
                       upvotes=upvotes+1
                 WHERE id=?;
            """, (q_fr, a_zh, now, kid))
        else:
            cur2 = conn.execute("""
                INSERT INTO knowledge(q_fr, q_zh, a_zh, q_hash, hits, upvotes, source, created_at, updated_at)
                VALUES(?,?,?,?,0,1,?,?,?)
            """, (q_fr, q_zh, a_zh, qh, source, now, now))
            kid = cur2.lastrowid

        question_all = (q_fr + " " + q_zh).strip()
        conn.execute("DELETE FROM knowledge_fts WHERE rowid=?", (kid,))
        conn.execute(
            "INSERT INTO knowledge_fts(rowid, question_all, answer_zh) VALUES(?,?,?)",
            (kid, question_all, a_zh)
        )
        conn.commit()
        return kid

def retrieve_best(query_fr: str = "", query_zh: str = "", k: int = 3):
    """用 FTS5 检索最相关答案；失败则回退 LIKE。返回 dict 或 None"""
    conn = _connect()

    def _search_like(qraw: str):
        pat = f"%{(qraw or '')[:50]}%"
        sql = """
        SELECT id, (COALESCE(q_fr,'') || ' ' || COALESCE(q_zh,'')) AS question_all,
               a_zh AS answer_zh, 1.0 AS score
          FROM knowledge
         WHERE q_fr LIKE ? OR q_zh LIKE ?
         LIMIT ?;
        """
        return conn.execute(sql, (pat, pat, k)).fetchall()

    def _search_fts(qraw: str):
        q = _fts_make_query(qraw)
        if not q:
            return []
        sql = """
        SELECT rowid AS id, question_all, answer_zh, bm25(knowledge_fts) AS score
          FROM knowledge_fts
         WHERE knowledge_fts MATCH ?
         ORDER BY score LIMIT ?;
        """
        try:
            return conn.execute(sql, (q, k)).fetchall()
        except sqlite3.OperationalError:
            # FTS 解析失败 -> 回退 LIKE，避免报错中断
            return _search_like(qraw)

    with _lock:
        rows = _search_fts(query_fr) + _search_fts(query_zh)
        if not rows:
            return None

        cand = [{"id": r["id"], "answer_zh": r["answer_zh"], "score": r["score"]} for r in rows]
        cand.sort(key=lambda x: x["score"])   # bm25 越小越相关；LIKE 回退统一给 1.0
        best = cand[0]

        conn.execute("UPDATE knowledge SET hits=hits+1, updated_at=? WHERE id=?",
                     (datetime.now().isoformat(timespec='seconds'), best["id"]))
        conn.commit()
        return best

# ===== 持久化设置（手动开关）=====
def get_setting(key: str, default=None):
    conn = _connect()
    with _lock:
        cur = conn.execute("SELECT val FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        return (row["val"] if row else default)

def set_setting(key: str, val: str):
    conn = _connect()
    with _lock, conn:
        conn.execute("""INSERT INTO settings(key,val) VALUES(?,?)
                        ON CONFLICT(key) DO UPDATE SET val=excluded.val""",
                     (key, str(val)))
        conn.commit()
