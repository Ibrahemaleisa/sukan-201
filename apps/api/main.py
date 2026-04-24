from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Generator, List, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


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


class Contract(BaseModel):
    id: int
    property_id: int
    tenant_id: int
    monthly_rent_sar: float
    security_deposit_sar: float
    start_date: date
    end_date: date
    status: Literal["draft", "active", "ended"] = "active"


class PaymentCreate(BaseModel):
    contract_id: int
    amount_sar: float = Field(gt=0)
    due_date: date


class Payment(BaseModel):
    id: int
    contract_id: int
    amount_sar: float
    due_date: date
    paid_at: date | None = None
    status: Literal["pending", "paid", "overdue"]


SCHEMA_SQL = """
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
"""


def _row_to_property(row: sqlite3.Row) -> Property:
    return Property(
        id=row["id"],
        title=row["title"],
        city=row["city"],
        district=row["district"],
        total_rooms=row["total_rooms"],
        occupied_rooms=row["occupied_rooms"],
        monthly_base_rent_sar=row["monthly_base_rent_sar"],
    )


def _row_to_tenant(row: sqlite3.Row) -> Tenant:
    return Tenant(
        id=row["id"],
        full_name=row["full_name"],
        email=row["email"],
        work_or_study=row["work_or_study"],
        interests=json.loads(row["interests_json"]),
        sleep_schedule=row["sleep_schedule"],
        cleanliness_level=row["cleanliness_level"],
    )


def _row_to_contract(row: sqlite3.Row) -> Contract:
    return Contract(
        id=row["id"],
        property_id=row["property_id"],
        tenant_id=row["tenant_id"],
        monthly_rent_sar=row["monthly_rent_sar"],
        security_deposit_sar=row["security_deposit_sar"],
        start_date=date.fromisoformat(row["start_date"]),
        end_date=date.fromisoformat(row["end_date"]),
        status=row["status"],
    )


def _row_to_payment(row: sqlite3.Row) -> Payment:
    return Payment(
        id=row["id"],
        contract_id=row["contract_id"],
        amount_sar=row["amount_sar"],
        due_date=date.fromisoformat(row["due_date"]),
        paid_at=date.fromisoformat(row["paid_at"]) if row["paid_at"] else None,
        status=row["status"],
    )


def _compatibility(a: Tenant, b: Tenant) -> float:
    interests_a, interests_b = set(a.interests), set(b.interests)
    interests_score = (len(interests_a & interests_b) / len(interests_a | interests_b) * 100) if (interests_a | interests_b) else 50
    schedule_score = 100 if a.sleep_schedule == b.sleep_schedule else 70 if "flexible" in {a.sleep_schedule, b.sleep_schedule} else 40
    cleanliness_gap = abs(a.cleanliness_level - b.cleanliness_level)
    cleanliness_score = max(0, 100 - cleanliness_gap * 12)
    return round(interests_score * 0.45 + schedule_score * 0.25 + cleanliness_score * 0.30, 2)


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(
        title="Sukan API",
        version="1.0.0",
        description="Advanced full-stack MVP for Sukan (سكان): property, contracts, tenants, payments, analytics.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.db_path = db_path or os.getenv("SUKAN_DB_PATH", "sukan.db")

    @contextmanager
    def get_conn() -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(app.state.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @app.on_event("startup")
    def init_db() -> None:
        db_parent = Path(app.state.db_path).parent
        db_parent.mkdir(parents=True, exist_ok=True)
        with get_conn() as conn:
            conn.executescript(SCHEMA_SQL)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "sukan-api", "db": app.state.db_path}

    @app.get("/properties", response_model=List[Property])
    def list_properties(city: str | None = None) -> List[Property]:
        with get_conn() as conn:
            if city:
                rows = conn.execute("SELECT * FROM properties WHERE city = ? ORDER BY id DESC", (city,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM properties ORDER BY id DESC").fetchall()
        return [_row_to_property(r) for r in rows]

    @app.post("/properties", response_model=Property, status_code=201)
    def create_property(payload: PropertyCreate) -> Property:
        with get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO properties (title, city, district, total_rooms, occupied_rooms, monthly_base_rent_sar)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (payload.title, payload.city, payload.district, payload.total_rooms, payload.monthly_base_rent_sar),
            )
            row = conn.execute("SELECT * FROM properties WHERE id = ?", (cursor.lastrowid,)).fetchone()
        if row is None:
            raise HTTPException(status_code=500, detail="Property creation failed")
        return _row_to_property(row)

    @app.get("/tenants", response_model=List[Tenant])
    def list_tenants() -> List[Tenant]:
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM tenants ORDER BY id DESC").fetchall()
        return [_row_to_tenant(r) for r in rows]

    @app.post("/tenants", response_model=Tenant, status_code=201)
    def create_tenant(payload: TenantCreate) -> Tenant:
        with get_conn() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO tenants (full_name, email, work_or_study, interests_json, sleep_schedule, cleanliness_level)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload.full_name,
                        payload.email,
                        payload.work_or_study,
                        json.dumps(payload.interests),
                        payload.sleep_schedule,
                        payload.cleanliness_level,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(status_code=409, detail="Tenant email already exists") from exc
            row = conn.execute("SELECT * FROM tenants WHERE id = ?", (cursor.lastrowid,)).fetchone()
        if row is None:
            raise HTTPException(status_code=500, detail="Tenant creation failed")
        return _row_to_tenant(row)

    @app.get("/contracts", response_model=List[Contract])
    def list_contracts() -> List[Contract]:
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM contracts ORDER BY id DESC").fetchall()
        return [_row_to_contract(r) for r in rows]

    @app.post("/contracts", response_model=Contract, status_code=201)
    def create_contract(payload: ContractCreate) -> Contract:
        if payload.end_date <= payload.start_date:
            raise HTTPException(status_code=400, detail="Invalid contract dates")

        with get_conn() as conn:
            prop = conn.execute("SELECT * FROM properties WHERE id = ?", (payload.property_id,)).fetchone()
            if prop is None:
                raise HTTPException(status_code=404, detail="Property not found")
            if conn.execute("SELECT 1 FROM tenants WHERE id = ?", (payload.tenant_id,)).fetchone() is None:
                raise HTTPException(status_code=404, detail="Tenant not found")
            if prop["occupied_rooms"] >= prop["total_rooms"]:
                raise HTTPException(status_code=409, detail="No rooms available")

            cursor = conn.execute(
                """
                INSERT INTO contracts
                    (property_id, tenant_id, monthly_rent_sar, security_deposit_sar, start_date, end_date, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
                """,
                (
                    payload.property_id,
                    payload.tenant_id,
                    payload.monthly_rent_sar,
                    payload.security_deposit_sar,
                    payload.start_date.isoformat(),
                    payload.end_date.isoformat(),
                ),
            )
            conn.execute("UPDATE properties SET occupied_rooms = occupied_rooms + 1 WHERE id = ?", (payload.property_id,))
            row = conn.execute("SELECT * FROM contracts WHERE id = ?", (cursor.lastrowid,)).fetchone()
        if row is None:
            raise HTTPException(status_code=500, detail="Contract creation failed")
        return _row_to_contract(row)

    @app.get("/payments", response_model=List[Payment])
    def list_payments(status: str | None = None) -> List[Payment]:
        with get_conn() as conn:
            if status:
                rows = conn.execute("SELECT * FROM payments WHERE status = ? ORDER BY id DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchall()
        return [_row_to_payment(r) for r in rows]

    @app.post("/payments", response_model=Payment, status_code=201)
    def create_payment(payload: PaymentCreate) -> Payment:
        with get_conn() as conn:
            if conn.execute("SELECT 1 FROM contracts WHERE id = ?", (payload.contract_id,)).fetchone() is None:
                raise HTTPException(status_code=404, detail="Contract not found")
            cursor = conn.execute(
                "INSERT INTO payments (contract_id, amount_sar, due_date, status) VALUES (?, ?, ?, 'pending')",
                (payload.contract_id, payload.amount_sar, payload.due_date.isoformat()),
            )
            row = conn.execute("SELECT * FROM payments WHERE id = ?", (cursor.lastrowid,)).fetchone()
        if row is None:
            raise HTTPException(status_code=500, detail="Payment creation failed")
        return _row_to_payment(row)

    @app.post("/payments/{payment_id}/mark-paid", response_model=Payment)
    def mark_payment_paid(payment_id: int) -> Payment:
        paid_at = date.today().isoformat()
        with get_conn() as conn:
            conn.execute("UPDATE payments SET status = 'paid', paid_at = ? WHERE id = ?", (paid_at, payment_id))
            row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Payment not found")
        return _row_to_payment(row)

    @app.post("/payments/refresh-overdue")
    def refresh_overdue() -> dict:
        today_iso = date.today().isoformat()
        with get_conn() as conn:
            cursor = conn.execute(
                """
                UPDATE payments
                SET status = 'overdue'
                WHERE status = 'pending' AND due_date < ?
                """,
                (today_iso,),
            )
        return {"updated_rows": cursor.rowcount}

    @app.get("/dashboard")
    def dashboard() -> dict:
        with get_conn() as conn:
            property_count = conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
            tenant_count = conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0]
            contract_count = conn.execute("SELECT COUNT(*) FROM contracts WHERE status='active'").fetchone()[0]
            payment_stats = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN status='paid' THEN amount_sar END), 0),
                    COALESCE(SUM(CASE WHEN status='pending' THEN amount_sar END), 0),
                    COALESCE(SUM(CASE WHEN status='overdue' THEN amount_sar END), 0)
                FROM payments
                """
            ).fetchone()
            occupancy_row = conn.execute("SELECT COALESCE(SUM(occupied_rooms),0), COALESCE(SUM(total_rooms),0) FROM properties").fetchone()

        occupied, total = occupancy_row[0], occupancy_row[1]
        occupancy_rate = round((occupied / total) * 100, 2) if total else 0.0
        return {
            "properties": property_count,
            "tenants": tenant_count,
            "active_contracts": contract_count,
            "occupied_rooms": occupied,
            "total_rooms": total,
            "occupancy_rate": occupancy_rate,
            "paid_revenue_sar": round(payment_stats[0], 2),
            "pending_revenue_sar": round(payment_stats[1], 2),
            "overdue_revenue_sar": round(payment_stats[2], 2),
        }

    @app.get("/matching/recommendations/{tenant_id}")
    def matching_recommendations(tenant_id: int, limit: int = Query(default=5, ge=1, le=20)) -> dict:
        with get_conn() as conn:
            current_row = conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
            if current_row is None:
                raise HTTPException(status_code=404, detail="Tenant not found")
            rows = conn.execute("SELECT * FROM tenants WHERE id != ?", (tenant_id,)).fetchall()

        current = _row_to_tenant(current_row)
        candidates = [_row_to_tenant(r) for r in rows]
        ranked = sorted(
            (
                {
                    "tenant_id": c.id,
                    "full_name": c.full_name,
                    "score": _compatibility(current, c),
                    "sleep_schedule": c.sleep_schedule,
                    "cleanliness_level": c.cleanliness_level,
                }
                for c in candidates
            ),
            key=lambda x: x["score"],
            reverse=True,
        )
        return {"tenant_id": tenant_id, "recommendations": ranked[:limit]}

    @app.post("/matching/score")
    def matching_score(
        interests_overlap: int = Query(ge=0, le=10),
        schedule_alignment: int = Query(ge=0, le=10),
        cleanliness_alignment: int = Query(ge=0, le=10),
    ) -> dict:
        score = round((interests_overlap * 0.45 + schedule_alignment * 0.35 + cleanliness_alignment * 0.20) * 10, 2)
        return {"compatibility_score": score, "scale": "0-100"}

    app.mount("/", StaticFiles(directory="apps/web", html=True), name="web")
    return app


app = create_app()
