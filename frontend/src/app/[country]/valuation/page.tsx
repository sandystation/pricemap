"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { AppHeader } from "@/components/AppHeader";
import { AuthNav } from "@/components/AuthNav";
import { PropertyForm } from "@/components/forms/PropertyForm";
import { PriceCard } from "@/components/valuation/PriceCard";
import { ComparablesList } from "@/components/valuation/ComparablesList";
import { track } from "@/lib/analytics";
import { COUNTRY_CONFIGS, type ValuationResponse } from "@/lib/types";

const MapContainer = dynamic(
  () => import("@/components/map/MapContainer"),
  { ssr: false, loading: () => <div className="h-[400px] animate-pulse rounded-xl bg-[var(--color-bg-secondary)]" /> }
);

export default function ValuationPage() {
  const params = useParams();
  const countryKey = params.country as string;
  const config = COUNTRY_CONFIGS[countryKey];
  const [result, setResult] = useState<ValuationResponse | null>(null);
  const [coords, setCoords] = useState<[number, number] | null>(null);

  if (!config) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p>Country not found</p>
      </div>
    );
  }

  return (
    <main className="min-h-screen">
      <AppHeader>
        <Link
          href={`/${countryKey}`}
          className="text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
        >
          Back to {config.name} Map
        </Link>
        <AuthNav />
      </AppHeader>

      <div className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-8">
          <h2 className="text-3xl font-bold">
            Property Analysis - {config.name}
          </h2>
          <p className="mt-2 max-w-3xl text-sm text-[var(--color-text-secondary)]">
            First-pass valuation support based on available listing data,
            comparable properties, location, and property features. Not a formal
            Perit valuation, bank valuation, or legal opinion.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
          {/* Left: Form */}
          <div>
            <PropertyForm
              countryCode={config.code}
              countryKey={countryKey}
              onResult={(val, latlon) => {
                setResult(val);
                if (latlon) setCoords(latlon);
                track("result_viewed", {
                  estimate_eur: val.estimate_eur,
                  price_per_sqm: val.price_per_sqm,
                  confidence_score: val.confidence_score,
                  model_version: val.model_version,
                  comparables_count: val.comparables.length,
                });
              }}
            />
          </div>

          {/* Right: Results */}
          <div className="space-y-6">
            {result && <PriceCard result={result} />}

            <div className="overflow-hidden rounded-xl border border-[var(--color-border)]">
              <MapContainer
                center={coords || config.center}
                zoom={coords ? 15 : config.zoom}
                countryCode={config.code}
                comparables={result?.comparables}
                markerPosition={coords}
              />
            </div>

            {result && result.comparables.length > 0 && (
              <ComparablesList comparables={result.comparables} />
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
