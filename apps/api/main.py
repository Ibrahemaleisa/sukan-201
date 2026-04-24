from __future__ import annotations

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
    total_rooms: int = Field(ge=1, le=1000)


class Property(PropertyCreate):
    id: int
    occupied_rooms: int = 0


class ContractCreate(BaseModel):
    property_id: int
    tenant_name: str = Field(min_length=2, max_length=120)
    monthly_rent_sar: float = Field(gt=0)
    start_date: date
    end_date: date


class Contract(ContractCreate):
    id: int
    status: Literal["draft", "active", "ended"] = "active"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    city TEXT NOT NULL,
    total_rooms INTEGER NOT NULL,
    occupied_rooms INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    tenant_name TEXT NOT NULL,
    monthly_rent_sar REAL NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    FOREIGN KEY(property_id) REFERENCES properties(id)
);
"""


def _row_to_property(row: sqlite3.Row) -> Property:
    return Property(
        id=row["id"],
        title=row["title"],
        city=row["city"],
        total_rooms=row["total_rooms"],
        occupied_rooms=row["occupied_rooms"],
    )


def _row_to_contract(row: sqlite3.Row) -> Contract:
    return Contract(
        id=row["id"],
        property_id=row["property_id"],
        tenant_name=row["tenant_name"],
        monthly_rent_sar=row["monthly_rent_sar"],
        start_date=date.fromisoformat(row["start_date"]),
        end_date=date.fromisoformat(row["end_date"]),
        status=row["status"],
    )


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(
        title="Sukan API",
        version="0.2.0",
        description="Full-stack MVP for Sukan (سكان): API + UI.",
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
    def list_properties() -> List[Property]:
        with get_conn() as conn:
            rows = conn.execute("SELECT * FROM properties ORDER BY id DESC").fetchall()
        return [_row_to_property(r) for r in rows]

    @app.post("/properties", response_model=Property, status_code=201)
    def create_property(payload: PropertyCreate) -> Property:
        with get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO properties (title, city, total_rooms, occupied_rooms)
                VALUES (?, ?, ?, 0)
                """,
                (payload.title, payload.city, payload.total_rooms),
            )
            row = conn.execute("SELECT * FROM properties WHERE id = ?", (cursor.lastrowid,)).fetchone()
        if row is None:
            raise HTTPException(status_code=500, detail="Property creation failed")
        return _row_to_property(row)

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
            if prop["occupied_rooms"] >= prop["total_rooms"]:
                raise HTTPException(status_code=409, detail="No rooms available")

            cursor = conn.execute(
                """
                INSERT INTO contracts
                    (property_id, tenant_name, monthly_rent_sar, start_date, end_date, status)
                VALUES (?, ?, ?, ?, ?, 'active')
                """,
                (
                    payload.property_id,
                    payload.tenant_name,
                    payload.monthly_rent_sar,
                    payload.start_date.isoformat(),
                    payload.end_date.isoformat(),
                ),
            )
            conn.execute(
                "UPDATE properties SET occupied_rooms = occupied_rooms + 1 WHERE id = ?",
                (payload.property_id,),
            )
            row = conn.execute("SELECT * FROM contracts WHERE id = ?", (cursor.lastrowid,)).fetchone()

        if row is None:
            raise HTTPException(status_code=500, detail="Contract creation failed")
        return _row_to_contract(row)

    @app.get("/dashboard")
    def dashboard() -> dict:
        with get_conn() as conn:
            property_count = conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
            contract_count = conn.execute("SELECT COUNT(*) FROM contracts").fetchone()[0]
            occupancy_row = conn.execute(
                "SELECT COALESCE(SUM(occupied_rooms),0), COALESCE(SUM(total_rooms),0) FROM properties"
            ).fetchone()

        occupied, total = occupancy_row[0], occupancy_row[1]
        occupancy_rate = round((occupied / total) * 100, 2) if total else 0.0
        return {
            "properties": property_count,
            "active_contracts": contract_count,
            "occupied_rooms": occupied,
            "total_rooms": total,
            "occupancy_rate": occupancy_rate,
        }

    @app.post("/matching/score")
    def matching_score(
        interests_overlap: int = Query(ge=0, le=10),
        schedule_alignment: int = Query(ge=0, le=10),
        cleanliness_alignment: int = Query(ge=0, le=10),
    ) -> dict:
        score = round(
            (interests_overlap * 0.45 + schedule_alignment * 0.35 + cleanliness_alignment * 0.20) * 10,
            2,
        )
        return {"compatibility_score": score, "scale": "0-100"}

    app.mount("/", StaticFiles(directory="apps/web", html=True), name="web")
    return app


app = create_app()
