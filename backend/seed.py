"""
seed.py — Populates CognoDB with a synthetic beneficial-ownership graph.

Run:  python seed.py

It does three things, in order:
  1. Wipes the database (safe to re-run).
  2. Generates bulk random Companies, People, Addresses and OWNS/DIRECTOR_OF/
     REGISTERED_AT edges.
  3. Injects four hand-placed structures so the interesting queries always hit:
       - a deep 5-hop ownership chain
       - a circular ownership loop
       - a shared-address shell cluster
       - a diamond (one owner reaching a company via two paths)

All writes go through parameterized Cypher (no string-concatenated queries).
"""

import os
import random
from datetime import date, timedelta

from dotenv import load_dotenv
from faker import Faker
from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable

# ── Config ──────────────────────────────────────────────────────────────────
load_dotenv()
URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")

NUM_COMPANIES = 50
NUM_PEOPLE = 35
NUM_ADDRESSES = 12

JURISDICTIONS = ["UK", "US", "KY", "BVI", "LU", "SG", "AE"]  # incl. common shell havens
NATIONALITIES = ["British", "American", "German", "Indian", "Emirati", "Swiss"]

fake = Faker()
Faker.seed(42)      # deterministic data — same graph every run
random.seed(42)


# ── Helpers ─────────────────────────────────────────────────────────────────
def random_date(start_year=2005, end_year=2023):
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    return (start + timedelta(days=random.randint(0, (end - start).days))).isoformat()


# ── Data generation (build plain Python dicts first, then load in bulk) ───────
def build_data():
    companies, people, addresses = [], [], []

    for i in range(NUM_COMPANIES):
        companies.append({
            "id": f"COMP-{i:05d}",
            "name": fake.company(),
            "jurisdiction": random.choice(JURISDICTIONS),
            "incorporation_date": random_date(),
            "status": random.choices(["active", "dissolved"], weights=[0.85, 0.15])[0],
        })

    for i in range(NUM_PEOPLE):
        people.append({
            "id": f"PERS-{i:05d}",
            "name": fake.name(),
            "nationality": random.choice(NATIONALITIES),
            "birth_year": random.randint(1950, 1995),
        })

    for i in range(NUM_ADDRESSES):
        addresses.append({
            "id": f"ADDR-{i:05d}",
            "line": fake.street_address(),
            "city": fake.city(),
            "country": random.choice(["UK", "US", "Cayman Islands", "Singapore"]),
        })

    return companies, people, addresses


def build_edges(companies, people, addresses):
    owns, directors, registered = [], [], []

    # Each company registered at some address.
    for c in companies:
        registered.append({
            "company": c["id"],
            "address": random.choice(addresses)["id"],
            "since": random_date(),
        })

    # People own companies (random stakes).
    for p in people:
        for c in random.sample(companies, random.randint(1, 3)):
            owns.append({
                "owner": p["id"], "company": c["id"],
                "percent": round(random.uniform(0.05, 0.6), 2),
                "since": random_date(),
            })

    # Some companies own other companies (holding structures).
    for c in random.sample(companies, 20):
        target = random.choice(companies)
        if target["id"] != c["id"]:
            owns.append({
                "owner": c["id"], "company": target["id"],
                "percent": round(random.uniform(0.2, 0.8), 2),
                "since": random_date(),
            })

    # Directors.
    for p in random.sample(people, 25):
        for c in random.sample(companies, random.randint(1, 2)):
            directors.append({
                "person": p["id"], "company": c["id"],
                "role": random.choice(["Director", "Secretary"]),
                "appointed": random_date(),
            })

    return owns, directors, registered


# ── The four planted structures ──────────────────────────────────────────────
# These use reserved ids (prefix P-) so they're easy to find in the demo.
def planted_structures():
    companies = [
        {"id": "P-CHAIN-1", "name": "Apex Holdings Ltd", "jurisdiction": "UK",
         "incorporation_date": "2010-03-01", "status": "active"},
        {"id": "P-CHAIN-2", "name": "Meridian Capital SA", "jurisdiction": "LU",
         "incorporation_date": "2011-06-01", "status": "active"},
        {"id": "P-CHAIN-3", "name": "Orion Nominees Ltd", "jurisdiction": "BVI",
         "incorporation_date": "2012-09-01", "status": "active"},
        {"id": "P-CHAIN-4", "name": "Zenith Trust Co", "jurisdiction": "KY",
         "incorporation_date": "2013-01-01", "status": "active"},
        {"id": "P-CHAIN-TARGET", "name": "Northwind Operating Ltd", "jurisdiction": "UK",
         "incorporation_date": "2014-01-01", "status": "active"},
        {"id": "P-LOOP-A", "name": "Circular Alpha Ltd", "jurisdiction": "BVI",
         "incorporation_date": "2015-01-01", "status": "active"},
        {"id": "P-LOOP-B", "name": "Circular Beta Ltd", "jurisdiction": "BVI",
         "incorporation_date": "2015-02-01", "status": "active"},
        {"id": "P-LOOP-C", "name": "Circular Gamma Ltd", "jurisdiction": "BVI",
         "incorporation_date": "2015-03-01", "status": "active"},
        {"id": "P-SHELL-1", "name": "Shell One Ltd", "jurisdiction": "KY",
         "incorporation_date": "2018-01-01", "status": "active"},
        {"id": "P-SHELL-2", "name": "Shell Two Ltd", "jurisdiction": "KY",
         "incorporation_date": "2018-01-01", "status": "active"},
        {"id": "P-SHELL-3", "name": "Shell Three Ltd", "jurisdiction": "KY",
         "incorporation_date": "2018-01-01", "status": "active"},
        {"id": "P-DIAMOND-MID1", "name": "Diamond Left Ltd", "jurisdiction": "UK",
         "incorporation_date": "2016-01-01", "status": "active"},
        {"id": "P-DIAMOND-MID2", "name": "Diamond Right Ltd", "jurisdiction": "UK",
         "incorporation_date": "2016-02-01", "status": "active"},
        {"id": "P-DIAMOND-TARGET", "name": "Diamond Core Ltd", "jurisdiction": "UK",
         "incorporation_date": "2016-03-01", "status": "active"},
    ]
    people = [
        {"id": "P-OWNER-CHAIN", "name": "Eleanor Vance", "nationality": "British",
         "birth_year": 1968},
        {"id": "P-OWNER-DIAMOND", "name": "Marcus Feld", "nationality": "Swiss",
         "birth_year": 1972},
    ]
    addresses = [
        {"id": "P-ADDR-SHELL", "line": "Ugland House, South Church St",
         "city": "George Town", "country": "Cayman Islands"},
    ]

    owns = [
        # Deep chain: Eleanor -> C1 -> C2 -> C3 -> C4 -> TARGET  (5 hops)
        {"owner": "P-OWNER-CHAIN", "company": "P-CHAIN-1", "percent": 0.90, "since": "2010-03-01"},
        {"owner": "P-CHAIN-1", "company": "P-CHAIN-2", "percent": 0.80, "since": "2011-06-01"},
        {"owner": "P-CHAIN-2", "company": "P-CHAIN-3", "percent": 0.75, "since": "2012-09-01"},
        {"owner": "P-CHAIN-3", "company": "P-CHAIN-4", "percent": 0.70, "since": "2013-01-01"},
        {"owner": "P-CHAIN-4", "company": "P-CHAIN-TARGET", "percent": 0.60, "since": "2014-01-01"},

        # Circular loop: A -> B -> C -> A
        {"owner": "P-LOOP-A", "company": "P-LOOP-B", "percent": 0.50, "since": "2015-01-01"},
        {"owner": "P-LOOP-B", "company": "P-LOOP-C", "percent": 0.50, "since": "2015-02-01"},
        {"owner": "P-LOOP-C", "company": "P-LOOP-A", "percent": 0.50, "since": "2015-03-01"},

        # Diamond: Marcus reaches TARGET via two different mid companies
        {"owner": "P-OWNER-DIAMOND", "company": "P-DIAMOND-MID1", "percent": 1.0, "since": "2016-01-01"},
        {"owner": "P-OWNER-DIAMOND", "company": "P-DIAMOND-MID2", "percent": 1.0, "since": "2016-02-01"},
        {"owner": "P-DIAMOND-MID1", "company": "P-DIAMOND-TARGET", "percent": 0.30, "since": "2016-03-01"},
        {"owner": "P-DIAMOND-MID2", "company": "P-DIAMOND-TARGET", "percent": 0.25, "since": "2016-03-01"},
    ]

    # Shared-address cluster: three shells at the same address
    registered = [
        {"company": "P-SHELL-1", "address": "P-ADDR-SHELL", "since": "2018-01-01"},
        {"company": "P-SHELL-2", "address": "P-ADDR-SHELL", "since": "2018-01-01"},
        {"company": "P-SHELL-3", "address": "P-ADDR-SHELL", "since": "2018-01-01"},
    ]

    return companies, people, addresses, owns, registered


# ── Cypher write functions (all parameterized, all use UNWIND for bulk) ───────
def wipe(tx):
    tx.run("MATCH (n) DETACH DELETE n")

def load_companies(tx, rows):
    tx.run("""
        UNWIND $rows AS row
        MERGE (c:Company {id: row.id})
        SET c.name = row.name,
            c.jurisdiction = row.jurisdiction,
            c.incorporation_date = date(row.incorporation_date),
            c.status = row.status
    """, rows=rows)

def load_people(tx, rows):
    tx.run("""
        UNWIND $rows AS row
        MERGE (p:Person {id: row.id})
        SET p.name = row.name,
            p.nationality = row.nationality,
            p.birth_year = row.birth_year
    """, rows=rows)

def load_addresses(tx, rows):
    tx.run("""
        UNWIND $rows AS row
        MERGE (a:Address {id: row.id})
        SET a.line = row.line, a.city = row.city, a.country = row.country
    """, rows=rows)

def load_owns(tx, rows):
    # Owner may be a Person or a Company — match either label by id.
    tx.run("""
        UNWIND $rows AS row
        MATCH (owner {id: row.owner})
        MATCH (c:Company {id: row.company})
        MERGE (owner)-[r:OWNS]->(c)
        SET r.percent = row.percent, r.since = date(row.since)
    """, rows=rows)

def load_directors(tx, rows):
    tx.run("""
        UNWIND $rows AS row
        MATCH (p:Person {id: row.person})
        MATCH (c:Company {id: row.company})
        MERGE (p)-[r:DIRECTOR_OF]->(c)
        SET r.role = row.role, r.appointed = date(row.appointed)
    """, rows=rows)

def load_registered(tx, rows):
    tx.run("""
        UNWIND $rows AS row
        MATCH (c:Company {id: row.company})
        MATCH (a:Address {id: row.address})
        MERGE (c)-[r:REGISTERED_AT]->(a)
        SET r.since = date(row.since)
    """, rows=rows)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not all([URI, USER, PASSWORD]):
        raise SystemExit("Missing NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD in .env")

    # Random bulk data
    companies, people, addresses = build_data()
    owns, directors, registered = build_edges(companies, people, addresses)

    # Planted structures
    pc, pp, pa, po, pr = planted_structures()
    companies += pc
    people += pp
    addresses += pa
    owns += po
    registered += pr

    try:
        driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
        driver.verify_connectivity()
        with driver.session() as session:
            print("Wiping database...")
            session.execute_write(wipe)

            print(f"Loading {len(companies)} companies...")
            session.execute_write(load_companies, companies)
            print(f"Loading {len(people)} people...")
            session.execute_write(load_people, people)
            print(f"Loading {len(addresses)} addresses...")
            session.execute_write(load_addresses, addresses)

            print(f"Loading {len(owns)} OWNS edges...")
            session.execute_write(load_owns, owns)
            print(f"Loading {len(directors)} DIRECTOR_OF edges...")
            session.execute_write(load_directors, directors)
            print(f"Loading {len(registered)} REGISTERED_AT edges...")
            session.execute_write(load_registered, registered)

        driver.close()
        print("\n✅ Seed complete.")
        print("   Try these in the console:")
        print("   • Deep chain owner:   Eleanor Vance  -> Northwind Operating Ltd")
        print("   • Diamond owner:      Marcus Feld    -> Diamond Core Ltd")
        print("   • Shared address:     Ugland House   (3 shell companies)")
        print("   • Ownership loop:     Circular Alpha/Beta/Gamma")

    except AuthError:
        print("❌ Auth failed — check credentials in .env")
    except ServiceUnavailable:
        print("❌ Cannot reach the database — check NEO4J_URI / instance is running")


if __name__ == "__main__":
    main()