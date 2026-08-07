"""
main.py — FastAPI backend for the Beneficial Ownership Explorer.

Exposes:
  GET /api/search?q=...          → find companies by name (autocomplete)
  GET /api/ownership/{id}        → effective ownership of a company
  GET /api/shared-addresses      → addresses shared by 3+ companies (shell clusters)
  GET /                          → serves the frontend page

Talks to CognoDB via the shared Neo4j driver in db.py.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from neo4j.exceptions import ServiceUnavailable

from db import get_driver, close_driver


@asynccontextmanager
async def lifespan(app: FastAPI):
    # runs on startup / shutdown
    yield
    close_driver()   # cleanly close the driver when the server stops


app = FastAPI(title="Beneficial Ownership Explorer", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ownership-explorer-chi.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Queries ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}

def run_search(q: str):
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (c:Company)
            WHERE toLower(c.name) CONTAINS toLower($q)
            RETURN c.id AS id, c.name AS name, c.jurisdiction AS jurisdiction
            ORDER BY c.name
            LIMIT 10
            """,
            q=q,
        )
        return [dict(record) for record in result]


def run_ownership(company_id: str):
    driver = get_driver()
    with driver.session() as session:
        # The company's own details
        info = session.run(
            "MATCH (c:Company {id: $id}) RETURN c.name AS name, c.jurisdiction AS jurisdiction",
            id=company_id,
        ).single()

        if info is None:
            return None

        # Effective ownership: walk OWNS chains, multiply % along each path, sum paths
        owners = session.run(
            """
            MATCH path = (owner:Person)-[:OWNS*1..10]->(target:Company {id: $id})
            WITH owner,
                 reduce(pct = 1.0, r IN relationships(path) | pct * r.percent) AS effective
            RETURN owner.name AS owner,
                   sum(effective) AS effectiveOwnership,
                   count(*) AS pathCount
            ORDER BY effectiveOwnership DESC
            """,
            id=company_id,
        )
        return {
            "company": {"name": info["name"], "jurisdiction": info["jurisdiction"]},
            "owners": [dict(record) for record in owners],
        }


def run_shared_addresses():
    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (a:Address)<-[:REGISTERED_AT]-(c:Company)
            WITH a, collect(c.name) AS companies, count(c) AS companyCount
            WHERE companyCount >= 3
            RETURN a.line AS address, a.city AS city,
                   companyCount, companies
            ORDER BY companyCount DESC
            """
        )
        return [dict(record) for record in result]


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/api/search")
def search(q: str = ""):
    if not q.strip():
        return []
    try:
        return run_search(q)
    except ServiceUnavailable:
        raise HTTPException(status_code=503, detail="Database unavailable. Try again shortly.")


@app.get("/api/ownership/{company_id}")
def ownership(company_id: str):
    try:
        result = run_ownership(company_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Company not found.")
        return result
    except ServiceUnavailable:
        raise HTTPException(status_code=503, detail="Database unavailable. Try again shortly.")


@app.get("/api/shared-addresses")
def shared_addresses():
    try:
        return run_shared_addresses()
    except ServiceUnavailable:
        raise HTTPException(status_code=503, detail="Database unavailable. Try again shortly.")
