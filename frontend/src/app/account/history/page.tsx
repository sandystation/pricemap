"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AppHeader } from "@/components/AppHeader";
import { AuthNav } from "@/components/AuthNav";
import { PriceCard } from "@/components/valuation/PriceCard";
import type { ValuationResponse } from "@/lib/types";

type Summary = {
  id: number;
  created_at: string;
  address: string | null;
  listing_type: string | null;
  property_type: string | null;
  area_sqm: number | null;
  estimate_eur: number | null;
};
type Detail = Summary & { input: Record<string, unknown>; result: ValuationResponse };

const eur = (n: number | null) =>
  n == null
    ? "—"
    : new Intl.NumberFormat("en-IE", {
        style: "currency",
        currency: "EUR",
        maximumFractionDigits: 0,
      }).format(n);
const when = (s: string) =>
  new Date(s).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

export default function HistoryPage() {
  const [items, setItems] = useState<Summary[] | null>(null);
  const [selected, setSelected] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/valuations/history");
      if (!res.ok) throw new Error();
      setItems((await res.json()).valuations);
    } catch {
      setError("Couldn't load your history.");
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  async function view(id: number) {
    const res = await fetch(`/api/valuations/${id}`);
    if (res.ok) setSelected(await res.json());
  }
  async function remove(id: number) {
    await fetch(`/api/valuations/${id}`, { method: "DELETE" });
    if (selected?.id === id) setSelected(null);
    setItems((prev) => prev?.filter((x) => x.id !== id) ?? null);
  }

  return (
    <main className="min-h-screen">
      <AppHeader>
        <Link
          href="/mt/valuation"
          className="text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
        >
          New valuation
        </Link>
        <AuthNav />
      </AppHeader>

      <div className="mx-auto max-w-7xl px-6 py-8">
        <h2 className="text-3xl font-bold">Your valuations</h2>
        <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
          Every valuation you run while signed in is saved here.
        </p>

        {error && <p className="mt-6 text-sm text-[var(--color-danger)]">{error}</p>}

        <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-2">
          {/* List */}
          <div className="space-y-3">
            {items == null && !error && (
              <p className="text-sm text-[var(--color-text-secondary)]">Loading…</p>
            )}
            {items?.length === 0 && (
              <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-sm text-[var(--color-text-secondary)]">
                No saved valuations yet.{" "}
                <Link href="/mt/valuation" className="text-[var(--color-primary)] hover:underline">
                  Run your first one
                </Link>
                .
              </div>
            )}
            {items?.map((v) => (
              <button
                key={v.id}
                type="button"
                onClick={() => view(v.id)}
                className={`w-full rounded-xl border p-4 text-left transition hover:border-[var(--color-primary)] ${
                  selected?.id === v.id
                    ? "border-[var(--color-primary)] bg-[var(--color-info-bg)]"
                    : "border-[var(--color-border)] bg-[var(--color-surface)]"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{v.address || "Unknown address"}</p>
                    <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
                      {when(v.created_at)} · {v.listing_type ?? "—"} · {v.property_type ?? "—"}
                      {v.area_sqm ? ` · ${v.area_sqm} m²` : ""}
                    </p>
                  </div>
                  <span className="shrink-0 font-semibold text-[var(--color-primary)]">
                    {eur(v.estimate_eur)}
                  </span>
                </div>
              </button>
            ))}
          </div>

          {/* Detail */}
          <div className="space-y-4">
            {selected ? (
              <>
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold">{selected.address || "Valuation"}</h3>
                  <button
                    type="button"
                    onClick={() => remove(selected.id)}
                    className="text-sm text-[var(--color-danger)] hover:underline"
                  >
                    Delete
                  </button>
                </div>
                <PriceCard result={selected.result} />
              </>
            ) : (
              <p className="text-sm text-[var(--color-text-secondary)]">
                Select a valuation to see its full result.
              </p>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
