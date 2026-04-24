from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Generator, List, Literal

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

Role = Literal["admin", "operator", "viewer"]


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=120)
    role: Role


class PropertyCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    city: str = Field(min_length=2, max_length=80)
    district: str = Field(default="", max_length=120)
    total_rooms: int = Field(ge=1, le=1000)
    monthly_base_rent_sar: float = Field(gt=0)


class Property(PropertyCreate):
    id: int
    occupied_rooms: int = 0


class TenantCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=180)
    work_or_study: str = Field(min_length=2, max_length=140)
    interests: list[str] = Field(default_factory=list)
    sleep_schedule: Literal["early", "flexible", "late"] = "flexible"
    cleanliness_level: int = Field(ge=0, le=10)


class Tenant(TenantCreate):
    id: int


class ContractCreate(BaseModel):
    property_id: int
    tenant_id: int
    monthly_rent_sar: float = Field(gt=0)
    security_deposit_sar: float = Field(ge=0)
    start_date: date
    end_date: date


class PaymentCreate(BaseModel):
    contract_id: int
    amount_sar: float = Field(gt=0)
    due_date: date


class ExpenseCreate(BaseModel):
    property_id: int
    category: Literal["maintenance", "utilities", "cleaning", "other"]
    amount_sar: float = Field(gt=0)
    spent_on: date
    notes: str = Field(default="", max_length=240)


class TicketCreate(BaseModel):
    property_id: int
    tenant_id: int
    title: str = Field(min_length=4, max_length=160)
    priority: Literal["low", "medium", "high"] = "medium"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    city TEXT NOT NULL,
    district TEXT NOT NULL DEFAULT '',
    total_rooms INTEGER NOT NULL,
    occupied_rooms INTEGER NOT NULL DEFAULT 0,
    monthly_base_rent_sar REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    work_or_study TEXT NOT NULL,
    interests_json TEXT NOT NULL,
    sleep_schedule TEXT NOT NULL,
    cleanliness_level INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    monthly_rent_sar REAL NOT NULL,
    security_deposit_sar REAL NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    FOREIGN KEY(property_id) REFERENCES properties(id),
    FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL,
    amount_sar REAL NOT NULL,
    due_date TEXT NOT NULL,
    paid_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    FOREIGN KEY(contract_id) REFERENCES contracts(id)
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    amount_sar REAL NOT NULL,
    spent_on TEXT NOT NULL,
    notes TEXT NOT NULL,
    FOREIGN KEY(property_id) REFERENCES properties(id)
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    FOREIGN KEY(property_id) REFERENCES properties(id),
    FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id INTEGER,
    timestamp TEXT NOT NULL
);
"""


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _compatibility(a: dict, b: dict) -> float:
    interests_a, interests_b = set(json.loads(a["interests_json"])), set(json.loads(b["interests_json"]))
    interests_score = (len(interests_a & interests_b) / len(interests_a | interests_b) * 100) if (interests_a | interests_b) else 50
    schedule_score = 100 if a["sleep_schedule"] == b["sleep_schedule"] else 70 if "flexible" in {a["sleep_schedule"], b["sleep_schedule"]} else 40
    cleanliness_score = max(0, 100 - abs(a["cleanliness_level"] - b["cleanliness_level"]) * 12)
    return round(interests_score * 0.45 + schedule_score * 0.25 + cleanliness_score * 0.30, 2)


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(title="Sukan Final", version="3.0.0", description="High-end full-stack operating platform")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    app.state.db_path = db_path or os.getenv("SUKAN_DB_PATH", "sukan.db")
    app.state.sessions: dict[str, dict[str, str | datetime]] = {}

    @contextmanager
    def get_conn() -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(app.state.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def audit(conn: sqlite3.Connection, actor: dict, action: str, entity: str, entity_id: int | None = None) -> None:
        conn.execute(
            "INSERT INTO audit_logs (actor, role, action, entity, entity_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (actor["username"], actor["role"], action, entity, entity_id, datetime.utcnow().isoformat()),
        )

    def require_role(x_api_token: str | None, allowed_roles: set[str]) -> dict:
        if not x_api_token or x_api_token not in app.state.sessions:
            raise HTTPException(status_code=401, detail="Missing or invalid API token")
        session = app.state.sessions[x_api_token]
        if datetime.utcnow() > session["expires_at"]:
            del app.state.sessions[x_api_token]
            raise HTTPException(status_code=401, detail="Session expired")
        if session["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return session

    @app.on_event("startup")
    def init_db() -> None:
        Path(app.state.db_path).parent.mkdir(parents=True, exist_ok=True)
        with get_conn() as conn:
            conn.executescript(SCHEMA_SQL)
            admin_exists = conn.execute("SELECT 1 FROM users WHERE username='admin' LIMIT 1").fetchone()
            if admin_exists is None:
                conn.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    ("admin", _hash_password("admin123"), "admin"),
                )

    @app.post("/auth/login")
    def login(payload: LoginRequest) -> dict:
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE username=?", (payload.username,)).fetchone()
        if row is None or row["password_hash"] != _hash_password(payload.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=12)
        app.state.sessions[token] = {"username": row["username"], "role": row["role"], "expires_at": expires_at}
        return {"token": token, "role": row["role"], "username": row["username"], "expires_at": expires_at.isoformat()}

    @app.post("/auth/users", status_code=201)
    def create_user(payload: UserCreate, x_api_token: str | None = Header(default=None)) -> dict:
        actor = require_role(x_api_token, {"admin"})
        with get_conn() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    (payload.username, _hash_password(payload.password), payload.role),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(status_code=409, detail="Username already exists") from exc
            audit(conn, actor, "create", "user", cursor.lastrowid)
        return {"id": cursor.lastrowid, "username": payload.username, "role": payload.role}

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "sukan-final", "version": "3.0.0", "sessions": len(app.state.sessions)}

    @app.get("/properties")
    def list_properties(limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0), q: str | None = None) -> dict:
        sql = "SELECT * FROM properties WHERE 1=1"
        params: list[str | int] = []
        if q:
            sql += " AND (title LIKE ? OR city LIKE ? OR district LIKE ?)"
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        with get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return {"items": [dict(r) for r in rows], "limit": limit, "offset": offset}

    @app.post("/properties", status_code=201)
    def create_property(payload: PropertyCreate, x_api_token: str | None = Header(default=None)) -> dict:
        actor = require_role(x_api_token, {"admin", "operator"})
        with get_conn() as conn:
            c = conn.execute(
                "INSERT INTO properties (title, city, district, total_rooms, occupied_rooms, monthly_base_rent_sar) VALUES (?, ?, ?, ?, 0, ?)",
                (payload.title, payload.city, payload.district, payload.total_rooms, payload.monthly_base_rent_sar),
            )
            audit(conn, actor, "create", "property", c.lastrowid)
            row = conn.execute("SELECT * FROM properties WHERE id=?", (c.lastrowid,)).fetchone()
        return dict(row)

    @app.get("/tenants")
    def list_tenants() -> dict:
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM tenants ORDER BY id DESC").fetchall()
        items = []
        for r in rows:
            d = dict(r)
            d["interests"] = json.loads(d.pop("interests_json"))
            items.append(d)
        return {"items": items}

    @app.post("/tenants", status_code=201)
    def create_tenant(payload: TenantCreate, x_api_token: str | None = Header(default=None)) -> dict:
        actor = require_role(x_api_token, {"admin", "operator"})
        with get_conn() as conn:
            try:
                c = conn.execute(
                    "INSERT INTO tenants (full_name, email, work_or_study, interests_json, sleep_schedule, cleanliness_level) VALUES (?, ?, ?, ?, ?, ?)",
                    (payload.full_name, payload.email, payload.work_or_study, json.dumps(payload.interests), payload.sleep_schedule, payload.cleanliness_level),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(status_code=409, detail="Tenant email already exists") from exc
            audit(conn, actor, "create", "tenant", c.lastrowid)
            row = conn.execute("SELECT * FROM tenants WHERE id=?", (c.lastrowid,)).fetchone()
        out = dict(row)
        out["interests"] = json.loads(out.pop("interests_json"))
        return out

    @app.post("/contracts", status_code=201)
    def create_contract(payload: ContractCreate, x_api_token: str | None = Header(default=None)) -> dict:
        actor = require_role(x_api_token, {"admin", "operator"})
        if payload.end_date <= payload.start_date:
            raise HTTPException(status_code=400, detail="Invalid contract dates")
        with get_conn() as conn:
            p = conn.execute("SELECT * FROM properties WHERE id=?", (payload.property_id,)).fetchone()
            if p is None:
                raise HTTPException(status_code=404, detail="Property not found")
            t = conn.execute("SELECT * FROM tenants WHERE id=?", (payload.tenant_id,)).fetchone()
            if t is None:
                raise HTTPException(status_code=404, detail="Tenant not found")
            if p["occupied_rooms"] >= p["total_rooms"]:
                raise HTTPException(status_code=409, detail="No rooms available")
            c = conn.execute(
                "INSERT INTO contracts (property_id, tenant_id, monthly_rent_sar, security_deposit_sar, start_date, end_date, status) VALUES (?, ?, ?, ?, ?, ?, 'active')",
                (payload.property_id, payload.tenant_id, payload.monthly_rent_sar, payload.security_deposit_sar, payload.start_date.isoformat(), payload.end_date.isoformat()),
            )
            conn.execute("UPDATE properties SET occupied_rooms = occupied_rooms + 1 WHERE id=?", (payload.property_id,))
            audit(conn, actor, "create", "contract", c.lastrowid)
            row = conn.execute("SELECT * FROM contracts WHERE id=?", (c.lastrowid,)).fetchone()
        return dict(row)

    @app.post("/payments", status_code=201)
    def create_payment(payload: PaymentCreate, x_api_token: str | None = Header(default=None)) -> dict:
        actor = require_role(x_api_token, {"admin", "operator"})
        with get_conn() as conn:
            if conn.execute("SELECT 1 FROM contracts WHERE id=?", (payload.contract_id,)).fetchone() is None:
                raise HTTPException(status_code=404, detail="Contract not found")
            c = conn.execute("INSERT INTO payments (contract_id, amount_sar, due_date, status) VALUES (?, ?, ?, 'pending')", (payload.contract_id, payload.amount_sar, payload.due_date.isoformat()))
            audit(conn, actor, "create", "payment", c.lastrowid)
            row = conn.execute("SELECT * FROM payments WHERE id=?", (c.lastrowid,)).fetchone()
        return dict(row)

    @app.post("/payments/{payment_id}/mark-paid")
    def mark_payment_paid(payment_id: int, x_api_token: str | None = Header(default=None)) -> dict:
        actor = require_role(x_api_token, {"admin", "operator"})
        with get_conn() as conn:
            conn.execute("UPDATE payments SET status='paid', paid_at=? WHERE id=?", (date.today().isoformat(), payment_id))
            audit(conn, actor, "mark_paid", "payment", payment_id)
            row = conn.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Payment not found")
        return dict(row)

    @app.post("/expenses", status_code=201)
    def create_expense(payload: ExpenseCreate, x_api_token: str | None = Header(default=None)) -> dict:
        actor = require_role(x_api_token, {"admin", "operator"})
        with get_conn() as conn:
            c = conn.execute(
                "INSERT INTO expenses (property_id, category, amount_sar, spent_on, notes) VALUES (?, ?, ?, ?, ?)",
                (payload.property_id, payload.category, payload.amount_sar, payload.spent_on.isoformat(), payload.notes),
            )
            audit(conn, actor, "create", "expense", c.lastrowid)
            row = conn.execute("SELECT * FROM expenses WHERE id=?", (c.lastrowid,)).fetchone()
        return dict(row)

    @app.post("/tickets", status_code=201)
    def create_ticket(payload: TicketCreate, x_api_token: str | None = Header(default=None)) -> dict:
        actor = require_role(x_api_token, {"admin", "operator", "viewer"})
        with get_conn() as conn:
            c = conn.execute(
                "INSERT INTO tickets (property_id, tenant_id, title, priority, status, created_at) VALUES (?, ?, ?, ?, 'open', ?)",
                (payload.property_id, payload.tenant_id, payload.title, payload.priority, datetime.utcnow().isoformat()),
            )
            audit(conn, actor, "create", "ticket", c.lastrowid)
            row = conn.execute("SELECT * FROM tickets WHERE id=?", (c.lastrowid,)).fetchone()
        return dict(row)

    @app.post("/tickets/{ticket_id}/status")
    def update_ticket_status(ticket_id: int, status: Literal["open", "in_progress", "resolved"] = Query(...), x_api_token: str | None = Header(default=None)) -> dict:
        actor = require_role(x_api_token, {"admin", "operator"})
        with get_conn() as conn:
            conn.execute("UPDATE tickets SET status=? WHERE id=?", (status, ticket_id))
            audit(conn, actor, f"update_status_{status}", "ticket", ticket_id)
            row = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return dict(row)

    @app.get("/matching/recommendations/{tenant_id}")
    def recommendations(tenant_id: int, limit: int = Query(5, ge=1, le=20)) -> dict:
        with get_conn() as conn:
            base = conn.execute("SELECT * FROM tenants WHERE id=?", (tenant_id,)).fetchone()
            if base is None:
                raise HTTPException(status_code=404, detail="Tenant not found")
            rows = conn.execute("SELECT * FROM tenants WHERE id!=?", (tenant_id,)).fetchall()
        ranked = sorted([{"tenant_id": r["id"], "full_name": r["full_name"], "score": _compatibility(base, r)} for r in rows], key=lambda x: x["score"], reverse=True)
        return {"tenant_id": tenant_id, "recommendations": ranked[:limit]}

    @app.get("/dashboard")
    def dashboard() -> dict:
        with get_conn() as conn:
            properties = conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
            tenants = conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0]
            active_contracts = conn.execute("SELECT COUNT(*) FROM contracts WHERE status='active'").fetchone()[0]
            paid, pending, overdue = conn.execute("SELECT COALESCE(SUM(CASE WHEN status='paid' THEN amount_sar END),0), COALESCE(SUM(CASE WHEN status='pending' THEN amount_sar END),0), COALESCE(SUM(CASE WHEN status='overdue' THEN amount_sar END),0) FROM payments").fetchone()
            expenses = conn.execute("SELECT COALESCE(SUM(amount_sar),0) FROM expenses").fetchone()[0]
            open_tickets = conn.execute("SELECT COUNT(*) FROM tickets WHERE status!='resolved'").fetchone()[0]
            occupied, total = conn.execute("SELECT COALESCE(SUM(occupied_rooms),0), COALESCE(SUM(total_rooms),0) FROM properties").fetchone()
        return {
            "properties": properties,
            "tenants": tenants,
            "active_contracts": active_contracts,
            "occupancy_rate": round((occupied / total) * 100, 2) if total else 0.0,
            "paid_revenue_sar": round(float(paid), 2),
            "pending_revenue_sar": round(float(pending), 2),
            "overdue_revenue_sar": round(float(overdue), 2),
            "expenses_sar": round(float(expenses), 2),
            "net_cash_sar": round(float(paid) - float(expenses), 2),
            "open_tickets": open_tickets,
        }

    @app.get("/reports/finance.csv")
    def finance_report_csv(x_api_token: str | None = Header(default=None)) -> StreamingResponse:
        require_role(x_api_token, {"admin", "operator"})
        data = dashboard()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["metric", "value"])
        for k, v in data.items():
            writer.writerow([k, v])
        output.seek(0)
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=finance_report.csv"})

    @app.get("/audit/logs")
    def audit_logs(limit: int = Query(100, ge=1, le=500), x_api_token: str | None = Header(default=None)) -> dict:
        require_role(x_api_token, {"admin"})
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return {"items": [dict(r) for r in rows]}

    app.mount("/", StaticFiles(directory="apps/web", html=True), name="web")
    return app


app = create_app()
