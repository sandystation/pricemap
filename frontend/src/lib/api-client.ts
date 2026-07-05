import type { FeatureCollection } from "geojson";

import type {
  EnrichedValuationJobResponse,
  EnrichedValuationStatusResponse,
  GeocodeResult,
  CountryStats,
  ValuationRequest,
  ValuationResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Short-lived API token for the logged-in user (same-origin /api/token, minted by
// Auth.js). Empty header when not signed in — the backend then treats the request
// as anonymous while require_auth is off.
async function authHeader(): Promise<Record<string, string>> {
  try {
    const res = await fetch("/api/token");
    if (!res.ok) return {};
    const { token } = await res.json();
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

async function fetchApi<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }

  return res.json();
}

export const api = {
  valuations: {
    estimate(request: ValuationRequest): Promise<ValuationResponse> {
      return fetchApi("/api/v1/valuations/estimate", {
        method: "POST",
        body: JSON.stringify(request),
      });
    },
    async submitEnriched(formData: FormData): Promise<EnrichedValuationJobResponse> {
      const res = await fetch(`${API_BASE}/api/v1/valuations/enriched`, {
        method: "POST",
        body: formData,
        headers: await authHeader(),
      });
      if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(error.detail || `API error: ${res.status}`);
      }
      return res.json();
    },
    getEnriched(jobId: string): Promise<EnrichedValuationStatusResponse> {
      return fetchApi(`/api/v1/valuations/enriched/${jobId}`);
    },
  },

  geocode: {
    lookup(
      address: string,
      countryCode: string
    ): Promise<GeocodeResult> {
      const params = new URLSearchParams({ address, country_code: countryCode });
      return fetchApi(`/api/v1/geocode?${params}`);
    },
  },

  stats: {
    getCountry(countryCode: string): Promise<CountryStats> {
      return fetchApi(`/api/v1/stats/${countryCode}`);
    },
    getHeatmap(
      countryCode: string
    ): Promise<FeatureCollection> {
      return fetchApi(`/api/v1/stats/${countryCode}/heatmap`);
    },
  },
};
