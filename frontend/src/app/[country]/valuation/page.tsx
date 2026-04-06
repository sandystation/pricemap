"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { PropertyForm } from "@/components/forms/PropertyForm";
import { PriceCard } from "@/components/valuation/PriceCard";
import { ComparablesList } from "@/components/valuation/ComparablesList";
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
      <header className="border-b border-[var(--color-border)] px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <Link href="/" className="text-2xl font-bold text-[var(--color-primary)]">
            PriceMap
          </Link>
          <Link
            href={`/${countryKey}`}
            className="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
          >
            Back to {config.name} Map
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-8">
        <h2 className="mb-8 text-3xl font-bold">
          Property Valuation - {config.name}
        </h2>

        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
          {/* Left: Form */}
          <div>
            <PropertyForm
              countryCode={config.code}
              countryKey={countryKey}
              onResult={(val, latlon) => {
                setResult(val);
                if (latlon) setCoords(latlon);
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
