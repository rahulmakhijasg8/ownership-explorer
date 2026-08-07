"""
db.py — Owns the single Neo4j driver for the whole app.

The driver is created once (expensive) and reused for every request.
Sessions are cheap and created per-query.
"""

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")

if not all([URI, USER, PASSWORD]):
    raise SystemExit("Missing NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD in .env")

# Created once when the app starts.
driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))


def get_driver():
    return driver


def close_driver():
    driver.close()