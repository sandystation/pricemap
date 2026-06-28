import Link from "next/link";
import styles from "./professional-beta.module.css";

const BENEFITS = [
  {
    title: "Save comp research time",
    detail: "Start with relevant Malta listing comparables instead of building the set from scratch.",
  },
  {
    title: "Challenge asking prices",
    detail: "Use range, EUR/sqm, and nearby evidence to spot cases that need a closer look.",
  },
  {
    title: "Shape it around Malta",
    detail: "Tell us which comps are wrong and what local context would make the tool useful.",
  },
];

const LIMITATION_BADGES = [
  "Not formal",
  "Not PPR-backed",
  "Not bank-grade",
];

export default function MaltaProfessionalBetaPage() {
  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link href="/" className={styles.brand}>
            PriceMap
          </Link>
          <nav className={styles.nav}>
            <Link href="/mt" className={styles.navLink}>
              Malta Map
            </Link>
            <Link href="/mt/valuation" className={styles.navButton}>
              Run Analysis
            </Link>
          </nav>
        </div>
      </header>

      <section className={styles.hero}>
        <div className={styles.heroInner}>
          <div className={styles.heroCopy}>
            <div className={styles.eyebrow}>
              <span className={styles.statusDot} />
              Malta professional beta
            </div>
            <h1>Comparable evidence for Malta property professionals</h1>
            <p>
              Sanity-check asking prices, find local comparables, and inspect
              valuation-support evidence from Malta listing data.
            </p>
            <div className={styles.actions}>
              <Link href="/mt/valuation" className={styles.primaryAction}>
                Run Sample Analysis
              </Link>
              <Link href="/mt" className={styles.secondaryAction}>
                View Malta Market Map
              </Link>
            </div>
          </div>

          <aside className={styles.reportPreview} aria-label="Illustrative evidence pack preview">
            <div className={styles.reportTopbar}>
              <span />
              <span />
              <span />
            </div>
            <div className={styles.reportHeader}>
              <div>
                <p>Illustrative output structure</p>
                <h2>Evidence pack preview</h2>
              </div>
              <span className={styles.previewBadge}>Beta</span>
            </div>

            <div className={styles.subjectGrid}>
              <div>
                <span>Subject</span>
                <strong>Sliema apartment</strong>
              </div>
              <div>
                <span>Inputs</span>
                <strong>112 sqm, 3 bed</strong>
              </div>
              <div>
                <span>Use</span>
                <strong>Review only</strong>
              </div>
            </div>

            <div className={styles.rangePanel}>
              <div>
                <span>Indicative listing-data range</span>
                <strong>EUR 510k-590k</strong>
              </div>
              <div className={styles.confidence}>
                <span>Moderate confidence</span>
                <div>
                  <i />
                  <i />
                  <i className={styles.mutedBar} />
                </div>
              </div>
            </div>

            <div className={styles.miniMap}>
              <span className={styles.pinSubject}>Subject</span>
              <span className={styles.pinOne}>Comp</span>
              <span className={styles.pinTwo}>Comp</span>
              <span className={styles.pinThree}>Comp</span>
            </div>

            <div className={styles.compTable}>
              <div className={styles.compHeader}>
                <span>Comparable</span>
                <span>EUR/sqm</span>
                <span>Distance</span>
              </div>
              {[
                ["Sliema, 3 bed", "5,180", "420 m"],
                ["Gzira, 2 bed", "4,760", "1.1 km"],
                ["St Julian's, 3 bed", "5,420", "1.5 km"],
              ].map(([name, price, distance]) => (
                <div key={name} className={styles.compRow}>
                  <span>{name}</span>
                  <span>{price}</span>
                  <span>{distance}</span>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </section>

      <section className={styles.lowerSection}>
        <div className={styles.benefitIntro}>
          <p className={styles.kicker}>Why join the beta</p>
          <h2>Less searching. Better first-pass judgment.</h2>
        </div>

        <div className={styles.benefitGrid}>
          {BENEFITS.map((item) => (
            <article key={item.title} className={styles.benefitCard}>
              <h3>{item.title}</h3>
              <p>{item.detail}</p>
            </article>
          ))}
        </div>

        <div className={styles.finalCta}>
          <div>
            <p>Private Malta beta</p>
            <h2>Send one real case. See if PriceMap saves you time.</h2>
            <span>32k+ RE/MAX listings, 4k+ MaltaPark listings, 5 beta seats.</span>
          </div>
          <Link href="/mt/valuation" className={styles.primaryAction}>
            Run Sample Analysis
          </Link>
        </div>

        <div className={styles.disclaimerLine}>
          <span>Listing-data support only.</span>
          {LIMITATION_BADGES.map((badge) => (
            <strong key={badge}>{badge}</strong>
          ))}
        </div>
      </section>
    </main>
  );
}
