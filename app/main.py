"""
NAGP 2026 - Kubernetes, DevOps & FinOps Assignment
Service API Tier - FastAPI microservice

Fetches product records from the PostgreSQL database tier.
Demonstrates: config separation (env vars) + connection pooling.
"""

import os
import socket
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

# ---- CONFIG SEPARATION ----
# Every DB setting is read from an environment variable.
# In Kubernetes, the ConfigMap supplies host/port/name/user,
# and the Secret supplies the password. Nothing is hardcoded.
# The defaults below are only used if you run this locally.
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "productsdb")
DB_USER = os.getenv("DB_USER", "appuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")

CONN_INFO = (
    f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} "
    f"user={DB_USER} password={DB_PASSWORD}"
)

# ---- CONNECTION POOLING ----
# One pool is created at startup and reused for every request,
# instead of opening a new DB connection each time (slow + wasteful).
pool: ConnectionPool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the pool when the app starts, close it on shutdown."""
    global pool
    pool = ConnectionPool(
        conninfo=CONN_INFO,
        min_size=1,
        max_size=10,
        open=True,
    )
    yield
    if pool is not None:
        pool.close()


app = FastAPI(
    title="NAGP Products API",
    description="Service API tier that fetches product records from PostgreSQL.",
    version="1.0.0",
    lifespan=lifespan,
)

# ---- ENDPOINTS ----
@app.get("/")
def root():
    """Landing endpoint. Returns the pod's hostname so during the demo
    you can see which of the 4 pods answered (proves load-balancing)."""
    return {
        "service": "NAGP Products API",
        "status": "running",
        "pod": socket.gethostname(),
        "hint": "GET /products to see records from the database tier.",
    }


@app.get("/health")
def health():
    """Kubernetes pings this to check the pod is alive."""
    return {"status": "healthy"}


@app.get("/products")
def get_products():
    """Fetch all products from the DB tier and return them as JSON."""
    if pool is None:
        raise HTTPException(status_code=503, detail="Database pool not ready")

    try:
        with pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT id, name, category, price, stock "
                    "FROM products ORDER BY id;"
                )
                rows = cur.fetchall()
        return {
            "count": len(rows),
            "served_by_pod": socket.gethostname(),
            "products": rows,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")