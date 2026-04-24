from datetime import date
from typing import Dict, List, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(
    title="Sukan API",
    version="0.1.0",
    description="MVP API for Sukan (سكان) co-living governance and operations.",
)


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


PROPERTIES: Dict[int, Property] = {}
CONTRACTS: Dict[int, Contract] = {}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "sukan-api"}


@app.get("/properties", response_model=List[Property])
def list_properties() -> List[Property]:
    return list(PROPERTIES.values())


@app.post("/properties", response_model=Property, status_code=201)
def create_property(payload: PropertyCreate) -> Property:
    new_id = len(PROPERTIES) + 1
    property_obj = Property(id=new_id, **payload.model_dump())
    PROPERTIES[new_id] = property_obj
    return property_obj


@app.post("/contracts", response_model=Contract, status_code=201)
def create_contract(payload: ContractCreate) -> Contract:
    prop = PROPERTIES.get(payload.property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    if payload.end_date <= payload.start_date:
        raise HTTPException(status_code=400, detail="Invalid contract dates")
    if prop.occupied_rooms >= prop.total_rooms:
        raise HTTPException(status_code=409, detail="No rooms available")

    new_id = len(CONTRACTS) + 1
    contract = Contract(id=new_id, **payload.model_dump())
    CONTRACTS[new_id] = contract

    updated_prop = prop.model_copy(update={"occupied_rooms": prop.occupied_rooms + 1})
    PROPERTIES[prop.id] = updated_prop

    return contract


@app.get("/contracts", response_model=List[Contract])
def list_contracts() -> List[Contract]:
    return list(CONTRACTS.values())


@app.post("/matching/score")
def matching_score(
    interests_overlap: int = Query(ge=0, le=10),
    schedule_alignment: int = Query(ge=0, le=10),
) -> dict:
    score = round((interests_overlap * 0.6 + schedule_alignment * 0.4) * 10, 2)
    return {"compatibility_score": score, "scale": "0-100"}
