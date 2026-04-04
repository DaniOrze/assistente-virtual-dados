import sqlite3
import pandas as pd

DB_PATH = "db/anexo_desafio_1.db"

def get_schema() -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    schema = []
    for (table,) in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        cols = cursor.fetchall()
        col_defs = ", ".join([f"{c[1]} ({c[2]})" for c in cols])
        schema.append(f"Tabela '{table}': {col_defs}")
    
    conn.close()
    return "\n".join(schema)

def run_query(sql: str) -> tuple[pd.DataFrame | None, str | None]:
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(sql, conn)
        conn.close()
        return df, None
    except Exception as e:
        return None, str(e)