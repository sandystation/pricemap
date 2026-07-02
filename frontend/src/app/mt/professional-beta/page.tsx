import Link from "next/link";
import styles from "./professional-beta.module.css";

type BenefitIconName = "comps" | "price" | "caveats";

const BENEFITS = [
  {
    icon: "comps",
    title: "Find comps",
    detail: "Nearby listings",
  },
  {
    icon: "price",
    title: "Check price",
    detail: "Range + EUR/sqm",
  },
  {
    icon: "caveats",
    title: "Flag caveats",
    detail: "Weak matches",
  },
] satisfies Array<{
  icon: BenefitIconName;
  title: string;
  detail: string;
}>;

const LIMITATION_BADGES = [
  "Not formal",
  "Not bank-grade",
];

function BenefitIcon({ name }: { name: BenefitIconName }) {
  if (name === "comps") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 21s6-5.1 6-11a6 6 0 0 0-12 0c0 5.9 6 11 6 11Z" />
        <circle cx="12" cy="10" r="2.2" />
      </svg>
    );
  }

  if (name === "price") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 17.5 9.4 12l3.2 3.2L20 7.8" />
        <path d="M20 13V7.8h-5.2" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 4 21 19H3L12 4Z" />
      <path d="M12 9v4.5" />
      <path d="M12 16.8h.01" />
    </svg>
  );
}

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
            <h1>Faster Malta property comps</h1>
            <p>
              Paste a listing. Get a price range, nearby comps, and caveats for
              review.
            </p>
            <div className={styles.actions}>
              <Link href="/mt/valuation" className={styles.primaryAction}>
                Try One Case
              </Link>
              <Link href="/mt" className={styles.secondaryAction}>
                View Map
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
                <p>Live preview</p>
                <h2>Comp check</h2>
              </div>
              <span className={styles.previewBadge}>Beta</span>
            </div>

            <div className={styles.summaryPills}>
              <span>Sliema apartment</span>
              <span>112 sqm</span>
              <span>Review only</span>
            </div>

            <div className={styles.rangePanel}>
              <div>
                <span>Range</span>
                <strong>EUR 510k-590k</strong>
              </div>
              <div className={styles.confidence}>
                <span>Confidence</span>
                <strong>Moderate</strong>
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

            <div className={styles.compChips}>
              <span>8 comps</span>
              <span>420 m nearest</span>
              <span>EUR/sqm view</span>
            </div>
          </aside>
        </div>
      </section>

      <section className={styles.lowerSection}>
        <div className={styles.benefitIntro}>
          <p className={styles.kicker}>Why join</p>
          <h2>Know the price faster.</h2>
        </div>

        <div className={styles.benefitGrid}>
          {BENEFITS.map((item) => (
            <article key={item.title} className={styles.benefitCard}>
              <div className={styles.benefitMain}>
                <span className={styles.benefitIcon}>
                  <BenefitIcon name={item.icon} />
                </span>
                <h3>{item.title}</h3>
              </div>
              <span className={styles.benefitTag}>{item.detail}</span>
            </article>
          ))}
        </div>

        <div className={styles.finalCta}>
          <div>
            <p>Private beta</p>
            <h2>Try one real case.</h2>
            <span>5 Malta professionals. Listing-data support only.</span>
          </div>
          <Link href="/mt/valuation" className={styles.primaryAction}>
            Try One Case
          </Link>
        </div>

        <div className={styles.disclaimerLine}>
          <span>For review support.</span>
          {LIMITATION_BADGES.map((badge) => (
            <strong key={badge}>{badge}</strong>
          ))}
        </div>
      </section>
    </main>
  );
}
