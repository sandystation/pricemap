import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

// Self-hosted at build time (no runtime request to Google). Fraunces is the
// characterful display serif; Inter carries body/UI. Exposed as CSS variables
// so the landing can use Fraunces for display while the app keeps Inter as its
// default body face.
const display = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});
const body = Inter({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://casaval.eu"),
  title: {
    default: "Casaval — Comparable property evidence for Malta",
    template: "%s · Casaval",
  },
  description:
    "Casaval finds nearby comparables, a defensible price range, and the caveats behind them — first-pass market evidence for Malta periti, valuers, and buyer-side agents.",
  openGraph: {
    title: "Casaval — Comparable property evidence for Malta",
    description:
      "Nearby comparables, a defensible price range, and the caveats behind them. First-pass market evidence for Malta property professionals.",
    siteName: "Casaval",
    type: "website",
    locale: "en_MT",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <head>
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
          crossOrigin=""
        />
      </head>
      <body className="min-h-screen bg-[var(--color-bg)]">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
