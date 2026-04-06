"use client";

import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import Link from "next/link";
import { COUNTRY_CONFIGS } from "@/lib/types";

const MapContainer = dynamic(
  () => import("@/components/map/MapContainer"),
  { ssr: false, loading: () => <div className="h-[500px] animate-pulse rounded-xl bg-[var(--color-bg-secondary)]" /> }
);

export default function CountryPage() {
  const params = useParams();
  const countryKey = params.country as string;
  const config = COUNTRY_CONFIGS[countryKey];

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
          <nav className="flex items-center gap-4">
            <span className="text-sm text-[var(--color-text-secondary)]">
              {config.name}
            </span>
            <Link
              href={`/${countryKey}/valuation`}
              className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--color-primary-dark)]"
            >
              Get Valuation
            </Link>
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold">{config.name} Price Map</h2>
            <p className="mt-1 text-[var(--color-text-secondary)]">
              Interactive property price heatmap
            </p>
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-[var(--color-border)]">
          <MapContainer
            center={config.center}
            zoom={config.zoom}
            countryCode={config.code}
          />
        </div>

        <div className="mt-8 text-center">
          <Link
            href={`/${countryKey}/valuation`}
            className="inline-block rounded-lg bg-[var(--color-primary)] px-8 py-3 text-lg font-medium text-white transition-colors hover:bg-[var(--color-primary-dark)]"
          >
            Estimate a Property Value
          </Link>
        </div>
      </div>
    </main>
  );
}
