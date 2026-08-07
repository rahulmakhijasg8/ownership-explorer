// api.js — all calls to the FastAPI backend live here, in one place.

const API = import.meta.env.VITE_API_URL;

export async function searchCompanies(q) {
  const res = await fetch(`${API}/api/search?q=${encodeURIComponent(q)}`);
  if (!res.ok) throw new Error("Search failed");
  return res.json();
}

export async function getOwnership(companyId) {
  const res = await fetch(`${API}/api/ownership/${encodeURIComponent(companyId)}`);
  if (!res.ok) throw new Error("Could not load ownership");
  return res.json();
}

export async function getSharedAddresses() {
  const res = await fetch(`${API}/api/shared-addresses`);
  if (!res.ok) throw new Error("Could not load shared addresses");
  return res.json();
}