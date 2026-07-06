import Link from "next/link";
import { AppHeader } from "@/components/AppHeader";

const COUNTRIES = [
  {
    code: "mt",
    name: "Malta",
    flag: "MT",
    description: "Professional beta using local listing data and comparable analysis",
    status: "Beta",
  },
  {
    code: "bg",
    name: "Bulgaria",
    flag: "BG",
    description: "Market data from Imot.bg and NSI statistics",
    status: "Active",
  },
  {
    code: "cy",
    name: "Cyprus",
    flag: "CY",
    description: "Coming soon - CYSTAT and Bazaraki data",
    status: "Coming Soon",
  },
  {
    code: "hr",
    name: "Croatia",
    flag: "HR",
    description: "Coming soon - DZS and Nekretnine.hr data",
    status: "Coming Soon",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen">
      {/* Header */}
      <AppHeader>
        <span className="text-[var(--color-text-secondary)]">About</span>
        <span className="text-[var(--color-text-secondary)]">API</span>
      </AppHeader>

      {/* Hero */}
      <section className="px-6 py-20 text-center">
        <h2 className="mx-auto max-w-3xl text-5xl font-bold leading-tight">
          Property Price Estimates for
          <span className="text-[var(--color-primary)]"> Underserved </span>
          EU Markets
        </h2>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-[var(--color-text-secondary)]">
          Instant, data-driven property valuations for markets where automated
          tools don&apos;t exist — built on local listing data and
          comparable-property analysis.
        </p>
      </section>

      {/* Country Cards */}
      <section className="mx-auto max-w-5xl px-6 pb-20">
        <h3 className="mb-8 text-center text-2xl font-semibold">
          Select a Country
        </h3>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {COUNTRIES.map((country) => {
            const isActive = country.status === "Active" || country.status === "Beta";
            const CardWrapper = isActive ? Link : "div";
            return (
              <CardWrapper
                key={country.code}
                href={isActive ? `/${country.code}` : "#"}
                className={`rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 transition-all ${
                  isActive
                    ? "cursor-pointer hover:border-[var(--color-primary)] hover:shadow-lg"
                    : "cursor-not-allowed opacity-60"
                }`}
              >
                <div className="mb-3 text-3xl">{country.flag}</div>
                <h4 className="text-lg font-semibold">{country.name}</h4>
                <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
                  {country.description}
                </p>
                <span
                  className={`mt-4 inline-block rounded-full px-3 py-1 text-xs font-medium ${
                    isActive
                      ? "bg-[var(--color-success-bg)] text-[var(--color-success)]"
                      : "bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)]"
                  }`}
                >
                  {country.status}
                </span>
              </CardWrapper>
            );
          })}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--color-border)] px-6 py-8 text-center text-sm text-[var(--color-text-secondary)]">
        <p>
          Casaval - Open source property valuation for Malta, Bulgaria, Cyprus
          &amp; Croatia
        </p>
      </footer>
    </main>
  );
}
