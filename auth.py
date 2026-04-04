import hashlib
import io
import json
import os
import sqlite3
from contextlib import contextmanager

import pandas as pd

APP_DB = os.path.join(os.path.dirname(__file__), "db", "app.db")


def init_db() -> None:
    with _conn() as cx:
        cx.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    NOT NULL UNIQUE,
                password_hash TEXT    NOT NULL,
                salt          TEXT    NOT NULL,
                created_at    TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(id),
                title      TEXT    NOT NULL,
                created_at TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS history (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id              INTEGER NOT NULL REFERENCES users(id),
                conversation_id      INTEGER REFERENCES conversations(id),
                question             TEXT    NOT NULL,
                resolved_question    TEXT,
                answer               TEXT    NOT NULL,
                chart_type           TEXT,
                sql_result_json      TEXT,
                is_multi_step        INTEGER DEFAULT 0,
                step_results_json    TEXT,
                reasoning_steps_json TEXT,
                created_at           TEXT    DEFAULT (datetime('now'))
            );
        """)

    with _conn() as cx:
        cols = [r[1] for r in cx.execute("PRAGMA table_info(history)").fetchall()]
        if "conversation_id" not in cols:
            cx.execute("ALTER TABLE history ADD COLUMN conversation_id INTEGER REFERENCES conversations(id)")

    with _conn() as cx:
        orphans = cx.execute(
            "SELECT DISTINCT user_id FROM history WHERE conversation_id IS NULL"
        ).fetchall()
        for (uid,) in orphans:
            cur = cx.execute(
                "INSERT INTO conversations (user_id, title, created_at) VALUES (?, ?, datetime('now'))",
                (uid, "Histórico anterior"),
            )
            conv_id = cur.lastrowid
            cx.execute(
                "UPDATE history SET conversation_id = ? WHERE user_id = ? AND conversation_id IS NULL",
                (conv_id, uid),
            )

def _hash(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return dk.hex()


def create_user(username: str, password: str) -> tuple[bool, str]:
    salt = os.urandom(16).hex()
    pw_hash = _hash(password, salt)
    try:
        with _conn() as cx:
            cx.execute(
                "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
                (username.strip(), pw_hash, salt),
            )
        return True, "Conta criada com sucesso."
    except sqlite3.IntegrityError:
        return False, "Nome de usuário já existe."


def verify_user(username: str, password: str) -> tuple[bool, int | None]:
    with _conn() as cx:
        row = cx.execute(
            "SELECT id, password_hash, salt FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
    if row is None:
        return False, None
    user_id, pw_hash, salt = row
    if _hash(password, salt) == pw_hash:
        return True, user_id
    return False, None

def create_conversation(user_id: int, title: str) -> int:
    with _conn() as cx:
        cur = cx.execute(
            "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
            (user_id, title),
        )
        return cur.lastrowid


def load_conversations(user_id: int) -> list[dict]:
    with _conn() as cx:
        rows = cx.execute(
            """
            SELECT c.id, c.title, c.created_at,
                   COUNT(h.id) as msg_count
            FROM conversations c
            LEFT JOIN history h ON h.conversation_id = c.id
            WHERE c.user_id = ?
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """,
            (user_id,),
        ).fetchall()
    return [
        {"id": r[0], "title": r[1], "created_at": r[2], "msg_count": r[3]}
        for r in rows
    ]


def rename_conversation(conversation_id: int, title: str) -> None:
    with _conn() as cx:
        cx.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (title, conversation_id),
        )


def delete_conversation(conversation_id: int, user_id: int) -> None:
    with _conn() as cx:
        cx.execute(
            "DELETE FROM history WHERE conversation_id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        cx.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )

def save_history_entry(
    user_id: int,
    conversation_id: int,
    question: str,
    resolved_question: str,
    answer: str,
    chart_type: str | None,
    df,
    is_multi_step: bool,
    step_results: list,
    reasoning_steps: list,
) -> None:
    sql_json = df.to_json(orient="records", force_ascii=False) if df is not None else None

    step_json = None
    if step_results:
        step_json = json.dumps([
            {"desc": desc, "data": sdf.to_json(orient="records", force_ascii=False)}
            for desc, sdf in step_results
        ], ensure_ascii=False)

    with _conn() as cx:
        cx.execute(
            """INSERT INTO history
               (user_id, conversation_id, question, resolved_question, answer, chart_type,
                sql_result_json, is_multi_step, step_results_json, reasoning_steps_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                conversation_id,
                question,
                resolved_question,
                answer,
                chart_type,
                sql_json,
                int(is_multi_step),
                step_json,
                json.dumps(reasoning_steps, ensure_ascii=False),
            ),
        )


def load_history(user_id: int, conversation_id: int) -> list[dict]:
    with _conn() as cx:
        rows = cx.execute(
            """SELECT question, resolved_question, answer, chart_type,
                      sql_result_json, is_multi_step, step_results_json,
                      reasoning_steps_json
               FROM history
               WHERE user_id = ? AND conversation_id = ?
               ORDER BY created_at ASC""",
            (user_id, conversation_id),
        ).fetchall()

    entries = []
    for row in rows:
        (question, resolved, answer, chart_type,
         sql_json, is_multi, step_json, rs_json) = row

        df = pd.read_json(io.StringIO(sql_json), orient="records") if sql_json else None

        step_results = []
        if step_json:
            for item in json.loads(step_json):
                step_results.append((
                    item["desc"],
                    pd.read_json(io.StringIO(item["data"]), orient="records"),
                ))

        entries.append({
            "question": question,
            "resolved": resolved or question,
            "answer": answer,
            "chart": chart_type,
            "df": df,
            "is_multi_step": bool(is_multi),
            "step_results": step_results,
            "reasoning_steps": json.loads(rs_json) if rs_json else [],
        })
    return entries

@contextmanager
def _conn():
    cx = sqlite3.connect(APP_DB)
    try:
        yield cx
        cx.commit()
    finally:
        cx.close()
