import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Casaval - Property Analysis",
  description:
    "Comparable-property analysis and valuation support for underserved EU markets",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
          crossOrigin=""
        />
      </head>
      <body className="min-h-screen bg-[var(--color-bg)]">{children}</body>
    </html>
  );
}
