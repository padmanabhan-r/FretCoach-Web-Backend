"""
Database connection pool for FretCoach Web Server
Uses psycopg2's SimpleConnectionPool for connection reuse
"""

import os
from contextlib import contextmanager
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

# Connection pool (lazy initialization)
_connection_pool = None


def get_pool():
    """Get or create the connection pool"""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            database=os.getenv("DB_NAME", "fretcoach"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            options="-c search_path=fretcoach,public"
        )
    return _connection_pool


@contextmanager
def get_db_connection():
    """
    Context manager for database connections with automatic cleanup.

    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM ...")
            results = cursor.fetchall()
            cursor.close()
    """
    conn = None
    try:
        conn = get_pool().getconn()
        yield conn
    finally:
        if conn:
            get_pool().putconn(conn)


def close_pool():
    """Close all connections in the pool (call on shutdown)"""
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
