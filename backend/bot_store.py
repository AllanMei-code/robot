# bot_store.py
import os, sqlite3, threading
from datetime import datetime

_DB_PATH = os.getenv("BOT_DB_PATH", "bot_store.db")
_lock = threading.Lock()

def _connect():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _connect() as conn:
        c = conn.cursor()
        c.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conv_id TEXT,
            role TEXT,     -- client/agent/bot
            lang TEXT,     -- zh/en/fr/...
            content TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            q_fr TEXT DEFAULT '',
            q_zh TEXT DEFAULT '',
            a_zh TEXT DEFAULT '',
            source TEXT DEFAULT 'agent_auto',
            hits INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        );
        """)
        # FTS5 视项目 SQLite 构建情况决定是否启用
        try:
            c.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
            USING fts5(question_all, answer_zh, content='knowledge', content_rowid='id');
            """)
            # 全量同步（首次）
            rows = c.execute("SELECT id, COALESCE(q_fr,'')||' '||COALESCE(q_zh,'') AS q, a_zh FROM knowledge").fetchall()
            for r in rows:
                c.execute("INSERT OR REPLACE INTO knowledge_fts(rowid, question_all, answer_zh) VALUES(?,?,?)",
                          (r["id"], r["q"], r["a_zh"]))
        except sqlite3.Error:
            pass
        conn.commit()

def log_message(role: str, lang: str, content: str, conv_id: str):
    with _connect() as conn, _lock:
        conn.execute(
            "INSERT INTO messages(conv_id, role, lang, content, created_at) VALUES (?,?,?,?,?)",
            (conv_id, role, lang, content, datetime.now().isoformat(timespec="seconds"))
        )
        conn.commit()

def upsert_qa(q_fr: str, q_zh: str, a_zh: str, source: str = "agent_auto"):
    q_fr = (q_fr or "").strip()[:500]
    q_zh = (q_zh or "").strip()[:500]
    a_zh = (a_zh or "").strip()[:2000]
    now = datetime.now().isoformat(timespec="seconds")

    with _connect() as conn, _lock:
        # 去重策略：同 q_zh 且答案相似（这里简化为完全相同）则 hits+1
        row = conn.execute("SELECT id, a_zh FROM knowledge WHERE q_zh=? LIMIT 1", (q_zh,)).fetchone()
        if row:
            if row["a_zh"] == a_zh:
                conn.execute("UPDATE knowledge SET hits=hits+1, updated_at=? WHERE id=?", (now, row["id"]))
            else:
                conn.execute("UPDATE knowledge SET a_zh=?, updated_at=? WHERE id=?", (a_zh, now, row["id"]))
            kid = row["id"]
        else:
            conn.execute(
                "INSERT INTO knowledge(q_fr, q_zh, a_zh, source, hits, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (q_fr, q_zh, a_zh, source, 1, now, now)
            )
            kid = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        # 同步 FTS
        try:
            conn.execute(
                "INSERT OR REPLACE INTO knowledge_fts(rowid, question_all, answer_zh) VALUES(?,?,?)",
                (kid, f"{q_fr} {q_zh}", a_zh)
            )
        except sqlite3.Error:
            pass
        conn.commit()

def retrieve_best(query_fr: str = "", query_zh: str = "", k: int = 3):
    """
    用 FTS5 检索最相关答案；失败则回退 LIKE。返回 dict 或 None
    """
    with _connect() as conn, _lock:
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
            except sqlite3.Error:
                return _search_like(qraw)

        def _search_like(qraw: str):
            pat = f"%{(qraw or '')[:50]}%"
            sql = """
            SELECT id, (COALESCE(q_fr,'') || ' ' || COALESCE(q_zh,'')) AS question_all,
                   a_zh AS answer_zh, 1.0 AS score
              FROM knowledge
             WHERE q_fr LIKE ? OR q_zh LIKE ?
             ORDER BY hits DESC, id DESC
             LIMIT ?;
            """
            return conn.execute(sql, (pat, pat, k)).fetchall()

        rows = _search_fts(query_fr) + _search_fts(query_zh)
        if not rows:
            return None
        cand = [{"id": r["id"], "answer_zh": r["answer_zh"], "score": r["score"]} for r in rows]
        cand.sort(key=lambda x: x["score"])
        best = cand[0]
        # 命中一次 +1 hits
        conn.execute("UPDATE knowledge SET hits=hits+1, updated_at=? WHERE id=?",
                     (datetime.now().isoformat(timespec="seconds"), best["id"]))
        conn.commit()
        return best

def _fts_make_query(qraw: str) -> str:
    """
    简化版：把文本切词后用 AND 连接，避开引号/特殊字符的 FTS 语法报错
    """
    qraw = (qraw or "").strip()
    if not qraw:
        return ""
    # 去引号及特殊字符
    cleaned = re.sub(r'["\'`]+', " ", qraw)
    toks = re.findall(r"[\w\u4e00-\u9fff]+", cleaned)
    toks = [t for t in toks if len(t) > 1]
    return " AND ".join(toks[:6])
