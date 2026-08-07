import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable

# Load NEO4J_URI / USER / PASSWORD from the .env file
load_dotenv()

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")

# Fail loudly if any secret is missing, rather than a confusing error later
if not all([URI, USER, PASSWORD]):
    raise SystemExit("Missing one of NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD in .env")

print(f"Connecting to {URI} as '{USER}'...")

try:
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    # verify_connectivity actually opens a connection and checks auth
    driver.verify_connectivity()

    # Run a trivial query to prove we can read a result back
    with driver.session() as session:
        result = session.run("RETURN 1 AS ok")
        value = result.single()["ok"]
        print(f"✅ Success — database returned: {value}")

    driver.close()

except AuthError:
    print("❌ Auth failed — check NEO4J_USER and NEO4J_PASSWORD in .env")
except ServiceUnavailable:
    print("❌ Cannot reach the database — check NEO4J_URI, and that the instance is running")
except Exception as e:
    print(f"❌ Unexpected error: {type(e).__name__}: {e}")