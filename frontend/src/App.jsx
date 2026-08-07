import { useState, useEffect } from "react";
import { searchCompanies, getOwnership, getSharedAddresses } from "./api";
import "./index.css";

export default function App() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(null);
  const [ownership, setOwnership] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [clusters, setClusters] = useState([]);

  // Load shared-address clusters once on startup.
  useEffect(() => {
    getSharedAddresses().then(setClusters).catch(() => {});
  }, []);

  // Search as the user types (debounced).
  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    const timer = setTimeout(() => {
      searchCompanies(query)
        .then(setResults)
        .catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);

  async function handleSelect(company) {
    setSelected(company);
    setResults([]);
    setQuery(company.name);
    setLoading(true);
    setError(null);
    setOwnership(null);
    try {
      const data = await getOwnership(company.id);
      setOwnership(data);
    } catch (e) {
      setError("Couldn't load ownership. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <header>
        <h1>Beneficial Ownership Explorer</h1>
        <p className="subtitle">
          Trace who really controls a company — through every layer of holding
          companies.
        </p>
      </header>

      <div className="search">
        <input
          type="text"
          placeholder="Search for a company…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {results.length > 0 && (
          <ul className="dropdown">
            {results.map((c) => (
              <li key={c.id} onClick={() => handleSelect(c)}>
                <span>{c.name}</span>
                <span className="tag">{c.jurisdiction}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {loading && <div className="panel muted">Loading ownership…</div>}
      {error && <div className="panel error">{error}</div>}

      {ownership && !loading && (
        <div className="panel">
          <h2>{ownership.company.name}</h2>
          <p className="muted">{ownership.company.jurisdiction}</p>

          {ownership.owners.length === 0 ? (
            <p className="muted">
              No individual beneficial owners found through ownership chains.
            </p>
          ) : (
            <>
              <h3>Ultimate beneficial owners</h3>
              <ul className="owners">
                {ownership.owners.map((o, i) => (
                  <li key={i}>
                    <span className="owner-name">{o.owner}</span>
                    <span className="owner-pct">
                      {(o.effectiveOwnership * 100).toFixed(2)}%
                    </span>
                    {o.pathCount > 1 && (
                      <span className="paths">via {o.pathCount} paths</span>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {clusters.length > 0 && (
        <div className="panel">
          <h3>⚠ Shared-address clusters</h3>
          <p className="muted">
            Addresses used by three or more companies — a common shell-company
            signal.
          </p>
          {clusters.map((c, i) => (
            <div key={i} className="cluster">
              <strong>{c.address}</strong>, {c.city} — {c.companyCount} companies
              <div className="cluster-companies">{c.companies.join(", ")}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}