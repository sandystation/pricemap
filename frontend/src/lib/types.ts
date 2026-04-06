export interface ValuationRequest {
  country_code: string;
  address?: string;
  lat?: number;
  lon?: number;
  property_type: PropertyType;
  area_sqm: number;
  floor?: number;
  total_floors?: number;
  rooms?: number;
  bedrooms?: number;
  bathrooms?: number;
  year_built?: number;
  year_renovated?: number;
  condition?: PropertyCondition;
  has_parking?: boolean;
  has_garden?: boolean;
  has_pool?: boolean;
  has_elevator?: boolean;
  has_balcony?: boolean;
}

export interface ComparableProperty {
  id: number;
  address: string | null;
  lat: number;
  lon: number;
  property_type: string;
  area_sqm: number;
  price_eur: number;
  price_per_sqm: number;
  distance_m: number;
  listing_date: string | null;
  source: string;
}

export interface ValuationResponse {
  estimate_eur: number;
  confidence_low: number;
  confidence_high: number;
  confidence_score: number;
  confidence_label: "High" | "Moderate" | "Low";
  price_per_sqm: number;
  comparables: ComparableProperty[];
  feature_importance: Record<string, number>;
  model_version: string;
  data_freshness: string | null;
  method: "model" | "comparables" | "no_data";
}

export interface GeocodeResult {
  lat: number;
  lon: number;
  display_name: string;
  locality: string | null;
  confidence: number;
}

export interface CountryStats {
  country_code: string;
  total_properties: number;
  avg_price_eur: number | null;
  avg_price_per_sqm: number | null;
  min_price_eur: number | null;
  max_price_eur: number | null;
  latest_index: {
    quarter: string;
    value: number;
    source: string;
  } | null;
}

export type PropertyType =
  | "apartment"
  | "house"
  | "villa"
  | "studio"
  | "maisonette"
  | "penthouse";

export type PropertyCondition =
  | "new"
  | "excellent"
  | "good"
  | "needs_renovation"
  | "shell";

export interface CountryConfig {
  code: string;
  name: string;
  center: [number, number]; // [lat, lon]
  zoom: number;
  currency: string;
}

export const COUNTRY_CONFIGS: Record<string, CountryConfig> = {
  mt: {
    code: "MT",
    name: "Malta",
    center: [35.9375, 14.3754],
    zoom: 11,
    currency: "EUR",
  },
  bg: {
    code: "BG",
    name: "Bulgaria",
    center: [42.7339, 25.4858],
    zoom: 7,
    currency: "EUR",
  },
  cy: {
    code: "CY",
    name: "Cyprus",
    center: [35.1264, 33.4299],
    zoom: 9,
    currency: "EUR",
  },
  hr: {
    code: "HR",
    name: "Croatia",
    center: [45.1, 15.2],
    zoom: 7,
    currency: "EUR",
  },
};
