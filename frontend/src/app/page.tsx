import Link from "next/link";

const COUNTRIES = [
  {
    code: "mt",
    name: "Malta",
    flag: "MT",
    description: "Verified transaction data from Property Price Registry",
    status: "Active",
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
      <header className="border-b border-[var(--color-border)] px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <h1 className="text-2xl font-bold text-[var(--color-primary)]">
            PriceMap
          </h1>
          <nav className="flex gap-4 text-sm text-[var(--color-text-secondary)]">
            <span>About</span>
            <span>API</span>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="px-6 py-20 text-center">
        <h2 className="mx-auto max-w-3xl text-5xl font-bold leading-tight">
          Property Price Estimates for
          <span className="text-[var(--color-primary)]"> Underserved </span>
          EU Markets
        </h2>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-[var(--color-text-secondary)]">
          Get instant, data-driven property valuations for markets where
          automated tools don&apos;t exist. Powered by transaction data, listing
          analysis, and machine learning.
        </p>
      </section>

      {/* Country Cards */}
      <section className="mx-auto max-w-5xl px-6 pb-20">
        <h3 className="mb-8 text-center text-2xl font-semibold">
          Select a Country
        </h3>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {COUNTRIES.map((country) => {
            const isActive = country.status === "Active";
            const CardWrapper = isActive ? Link : "div";
            return (
              <CardWrapper
                key={country.code}
                href={isActive ? `/${country.code}` : "#"}
                className={`rounded-xl border border-[var(--color-border)] p-6 transition-all ${
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
                      ? "bg-green-100 text-green-800"
                      : "bg-gray-100 text-gray-600"
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
          PriceMap - Open source property valuation for Malta, Bulgaria, Cyprus
          &amp; Croatia
        </p>
      </footer>
    </main>
  );
}
