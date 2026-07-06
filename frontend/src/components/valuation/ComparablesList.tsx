"use client";

import type { ComparableProperty } from "@/lib/types";

interface ComparablesListProps {
  comparables: ComparableProperty[];
}

const formatEur = (value: number) =>
  new Intl.NumberFormat("en", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);

export function ComparablesList({ comparables }: ComparablesListProps) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
      <h4 className="mb-1 text-sm font-semibold">
        Comparable listings ({comparables.length})
      </h4>
      <p className="mb-4 text-xs text-[var(--color-text-secondary)]">
        Nearby asking prices from recent listings — sorted by distance.
      </p>
      <div className="space-y-3">
        {comparables.map((comp) => (
          <a
            key={comp.id}
            href={comp.url ?? undefined}
            target={comp.url ? "_blank" : undefined}
            rel={comp.url ? "noopener noreferrer" : undefined}
            className={`flex items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] p-3 ${
              comp.url ? "transition hover:border-[var(--color-primary)]" : "cursor-default"
            }`}
          >
            <div>
              <p className="text-sm font-medium">{formatEur(comp.price_eur)}</p>
              <p className="text-xs text-[var(--color-text-secondary)]">
                {comp.area_sqm} m² | {comp.property_type} |{" "}
                {formatEur(comp.price_per_sqm)}/m²
              </p>
              {comp.address && (
                <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">
                  {comp.address}
                </p>
              )}
            </div>
            <div className="text-right">
              <p className="text-xs font-medium">
                {comp.distance_m < 1000
                  ? `${Math.round(comp.distance_m)}m`
                  : `${(comp.distance_m / 1000).toFixed(1)}km`}
              </p>
              <p className="text-xs text-[var(--color-text-secondary)]">
                {comp.source}
              </p>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
