import type { FeatureCollection } from "geojson";

import type {
  GeocodeResult,
  CountryStats,
  ValuationRequest,
  ValuationResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
