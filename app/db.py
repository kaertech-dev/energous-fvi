import pymysql
import pymysql.cursors
from app.config import DBConfig

def get_conn():
    return pymysql.connect(
        host=DBConfig.HOST,
        user=DBConfig.USER,
        password=DBConfig.PASSWORD,
        database=DBConfig.DATABASE,
        port=DBConfig.PORT,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )

def query_one(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()
    finally:
        conn.close()

def query_all(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    finally:
        conn.close()

def execute(sql, params=None, conn=None):
    """Execute a write query. Pass conn to share a transaction."""
    own = conn is None
    if own:
        conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            lastrowid = cur.lastrowid
        if own:
            conn.commit()
        return lastrowid
    except Exception:
        if own:
            conn.rollback()
        raise
    finally:
        if own:
            conn.close()
