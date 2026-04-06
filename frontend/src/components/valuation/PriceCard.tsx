"use client";

import type { ValuationResponse } from "@/lib/types";
import { ConfidenceMeter } from "./ConfidenceMeter";

interface PriceCardProps {
  result: ValuationResponse;
}

const formatEur = (value: number) =>
  new Intl.NumberFormat("en", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);

export function PriceCard({ result }: PriceCardProps) {
  if (result.method === "no_data") {
    return (
      <div className="rounded-xl border border-[var(--color-border)] p-6">
        <p className="text-center text-[var(--color-text-secondary)]">
          Insufficient data to provide an estimate for this location. Try a
          different address or check back later as we collect more data.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[var(--color-border)] p-6">
      <div className="text-center">
        <p className="text-sm text-[var(--color-text-secondary)]">
          Estimated Value
        </p>
        <p className="mt-1 text-4xl font-bold text-[var(--color-primary)]">
          {formatEur(result.estimate_eur)}
        </p>
        <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
          {formatEur(result.confidence_low)} &ndash;{" "}
          {formatEur(result.confidence_high)}
        </p>
        <p className="text-xs text-[var(--color-text-secondary)]">
          {formatEur(result.price_per_sqm)} / m²
        </p>
      </div>

      <div className="mt-6">
        <ConfidenceMeter
          score={result.confidence_score}
          label={result.confidence_label}
        />
      </div>

      {/* Feature importance */}
      {Object.keys(result.feature_importance).length > 0 && (
        <div className="mt-6">
          <p className="mb-2 text-xs font-medium text-[var(--color-text-secondary)]">
            Price Drivers
          </p>
          <div className="space-y-1">
            {Object.entries(result.feature_importance)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 5)
              .map(([feature, importance]) => (
                <div key={feature} className="flex items-center gap-2">
                  <span className="w-24 text-xs capitalize">
                    {feature.replace(/_/g, " ")}
                  </span>
                  <div className="h-2 flex-1 rounded-full bg-[var(--color-bg-secondary)]">
                    <div
                      className="h-2 rounded-full bg-[var(--color-primary)]"
                      style={{ width: `${importance * 100}%` }}
                    />
                  </div>
                  <span className="w-10 text-right text-xs text-[var(--color-text-secondary)]">
                    {Math.round(importance * 100)}%
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      <div className="mt-4 flex justify-between text-xs text-[var(--color-text-secondary)]">
        <span>Method: {result.method}</span>
        <span>Model: {result.model_version}</span>
      </div>
    </div>
  );
}
