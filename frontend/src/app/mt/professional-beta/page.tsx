import Link from "next/link";
import styles from "./professional-beta.module.css";

type BenefitIconName = "comps" | "price" | "caveats";

const HERO = {
  eyebrow: "Malta · Private beta",
  titleLead: "Comparable evidence for Malta property,",
  titleAccent: "in minutes — not weeks.",
  sub: "Casaval finds nearby comparables, a defensible price range, and the caveats behind them — first-pass market evidence for periti, valuers, and buyer-side agents.",
};

const HERO_STATS = [
  { value: "~12%", label: "Typical margin vs sale price" },
  { value: "36K+", label: "Malta listings behind each estimate" },
  { value: "Seconds", label: "For a first pass, vs 1–2 weeks manual" },
];

const POSITIONING = {
  lede: "Manual valuations take 1–2 weeks and €250–700. Casaval gives you a defensible first pass in minutes — so you can price, advise, and shortlist faster.",
  who: "Built for Malta periti, valuers, buyer-side agents, and small agencies.",
};

const STEPS = [
  {
    title: "Enter the property",
    body: "Type a Malta address with autocomplete and add the basics — area, type, condition. A listing description or photos sharpen the result.",
  },
  {
    title: "We find the comparables",
    body: "Casaval matches nearby listings by distance, size, and type, then runs a model trained on thousands of local sales.",
  },
  {
    title: "Review the evidence",
    body: "Get a price range, a confidence level, the comps behind it, and clear caveats — ready for your professional judgment.",
  },
];

const BENEFITS = [
  {
    icon: "comps",
    title: "Ranked comparables",
    body: "Nearby listings ranked by distance, size, and type — each with €/sqm, so the local market reads at a glance.",
  },
  {
    icon: "price",
    title: "A defensible range",
    body: "A price range and confidence level, learned from thousands of recent Malta sales.",
  },
  {
    icon: "caveats",
    title: "Caveats, not black boxes",
    body: "Every output flags weak matches and missing data, so your professional judgment stays in charge.",
  },
] satisfies Array<{ icon: BenefitIconName; title: string; body: string }>;

const ACCURACY = {
  kicker: "Built to be trusted",
  title: "Transparent by design.",
  body: "Casaval is a decision-support tool, not a regulatory one — so it shows its work. Estimates are trained and tested on thousands of real Malta sales, and every report scores its own confidence and lists the comparables and features behind it.",
  points: [
    "Trained on thousands of recent Malta sales",
    "Tested against actual sale prices across every locality",
    "A confidence score, with a wider range when details are missing",
    "Built on live Malta listings, refreshed regularly",
  ],
};

const ACCURACY_STATS = [
  { value: "~12%", label: "Typical margin vs sale price" },
  { value: "36K+", label: "Malta listings analysed" },
  { value: "5–10", label: "Comparables per report" },
  { value: "Daily", label: "Listings refreshed" },
];

const HONESTY = {
  kicker: "Straight about the limits",
  title: "What Casaval is — and isn't.",
  is: [
    "Fast comparable evidence for a property",
    "A defensible first-pass price range",
    "A transparent starting point for your own analysis",
  ],
  isnt: [
    "A formal Perit valuation",
    "A bank or mortgage valuation",
    "A replacement for professional judgment",
  ],
};

const FAQ = [
  {
    q: "Is this a formal valuation?",
    a: "No. Casaval is decision-support — fast comparable evidence and a first-pass range. It doesn't replace a Perit valuation, a bank valuation, or your professional judgment.",
  },
  {
    q: "Where does the data come from?",
    a: "Public Malta property listings — currently RE/MAX Malta and MaltaPark, tens of thousands of records refreshed regularly. It's listing data, not closed-transaction data.",
  },
  {
    q: "How accurate is it?",
    a: "On recent Malta sales, our estimates land within about 12% of the eventual sale price on average. Every report also shows a confidence level and widens the range when key details are missing.",
  },
  {
    q: "Who is it for?",
    a: "Malta property professionals — periti, valuers, buyer-side agents, and small agencies who want a faster first pass and a comparable set to work from.",
  },
  {
    q: "What does it cost?",
    a: "It's free during the private beta. We're onboarding a small group of Malta professionals and using their feedback to shape what comes next.",
  },
];

const FINAL_CTA = {
  kicker: "Private beta",
  title: "Try one real case.",
  sub: "Free during the private beta — now onboarding Malta professionals.",
};

const FOOTER_DISCLAIMER =
  "Casaval provides listing-data valuation support based on comparable properties, location, and property features. It is not a formal Perit valuation, a bank valuation, legal advice, or a substitute for professional judgment.";

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

function CheckIcon() {
  return (
    <svg className={styles.markIcon} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function CrossIcon() {
  return (
    <svg className={styles.markIcon} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

export default function MaltaProfessionalBetaPage() {
  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link href="/" className={styles.brand}>
            Casaval
          </Link>
          <nav className={styles.nav}>
            <a href="#how" className={styles.navLink}>
              How it works
            </a>
            <a href="#accuracy" className={styles.navLink}>
              Accuracy
            </a>
            <Link href="/mt" className={styles.navLink}>
              Malta map
            </Link>
            <Link href="/login" className={styles.signIn}>
              Sign in
            </Link>
            <Link href="/signup" className={styles.navButton}>
              Run your first case
            </Link>
          </nav>
        </div>
      </header>

      <section className={styles.hero}>
        <div className={styles.heroInner}>
          <div className={styles.heroCopy}>
            <div className={styles.eyebrow}>
              <span className={styles.statusDot} />
              {HERO.eyebrow}
            </div>
            <h1>
              {HERO.titleLead}{" "}
              <span className={styles.heroAccent}>{HERO.titleAccent}</span>
            </h1>
            <p>{HERO.sub}</p>
            <div className={styles.actions}>
              <Link href="/signup" className={styles.primaryAction}>
                Run your first case
              </Link>
              <Link href="/mt" className={styles.secondaryAction}>
                See the Malta map
              </Link>
            </div>
            <dl className={styles.trustRow}>
              {HERO_STATS.map((stat) => (
                <div key={stat.label} className={styles.trustItem}>
                  <dt className={styles.trustNum}>{stat.value}</dt>
                  <dd className={styles.trustLabel}>{stat.label}</dd>
                </div>
              ))}
            </dl>
          </div>

          <aside
            className={styles.reportPreview}
            aria-label="Illustrative evidence pack preview"
          >
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
                <strong>€510k–590k</strong>
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
              <span>€/sqm view</span>
            </div>
          </aside>
        </div>
      </section>

      <section className={styles.positioning}>
        <div className={styles.positioningInner}>
          <p className={styles.positioningLede}>{POSITIONING.lede}</p>
          <p className={styles.positioningWho}>{POSITIONING.who}</p>
        </div>
      </section>

      <section id="how" className={styles.section}>
        <div className={styles.sectionInner}>
          <p className={styles.kicker}>How it works</p>
          <h2 className={styles.sectionTitle}>
            From address to evidence in three steps.
          </h2>
          <ol className={styles.steps}>
            {STEPS.map((step, index) => (
              <li key={step.title} className={styles.step}>
                <span className={styles.stepNum}>{index + 1}</span>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionInner}>
          <p className={styles.kicker}>Why professionals use it</p>
          <h2 className={styles.sectionTitle}>
            Evidence you can put in front of a client.
          </h2>
          <div className={styles.benefitGrid}>
            {BENEFITS.map((item) => (
              <article key={item.title} className={styles.benefitCard}>
                <span className={styles.benefitIcon}>
                  <BenefitIcon name={item.icon} />
                </span>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="accuracy" className={styles.accuracy}>
        <div className={styles.accuracyInner}>
          <div className={styles.accuracyCopy}>
            <p className={styles.kicker}>{ACCURACY.kicker}</p>
            <h2 className={styles.sectionTitle}>{ACCURACY.title}</h2>
            <p className={styles.accuracyLede}>{ACCURACY.body}</p>
            <ul className={styles.methodList}>
              {ACCURACY.points.map((point) => (
                <li key={point}>
                  <CheckIcon />
                  {point}
                </li>
              ))}
            </ul>
          </div>
          <dl className={styles.statGrid}>
            {ACCURACY_STATS.map((stat) => (
              <div key={stat.label} className={styles.statCard}>
                <dt>{stat.value}</dt>
                <dd>{stat.label}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section className={styles.honesty}>
        <div className={styles.honestyInner}>
          <p className={styles.kicker}>{HONESTY.kicker}</p>
          <h2 className={styles.sectionTitle}>{HONESTY.title}</h2>
          <div className={styles.honestyCols}>
            <div className={`${styles.honestyCard} ${styles.honestyIs}`}>
              <h3>What it is</h3>
              <ul>
                {HONESTY.is.map((item) => (
                  <li key={item}>
                    <CheckIcon />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div className={`${styles.honestyCard} ${styles.honestyIsnt}`}>
              <h3>What it isn&apos;t</h3>
              <ul>
                {HONESTY.isnt.map((item) => (
                  <li key={item}>
                    <CrossIcon />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.faq}>
        <div className={styles.faqInner}>
          <p className={styles.kicker}>Questions</p>
          <h2 className={styles.sectionTitle}>Good to know.</h2>
          <div className={styles.faqList}>
            {FAQ.map((item) => (
              <details key={item.q} className={styles.faqItem}>
                <summary>
                  {item.q}
                  <span className={styles.faqMarker} aria-hidden="true" />
                </summary>
                <p>{item.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.finalCta}>
        <div className={styles.finalCtaInner}>
          <div>
            <p className={styles.finalKicker}>{FINAL_CTA.kicker}</p>
            <h2>{FINAL_CTA.title}</h2>
            <span>{FINAL_CTA.sub}</span>
          </div>
          <Link href="/signup" className={styles.finalAction}>
            Run your first case
          </Link>
        </div>
      </section>

      <footer className={styles.footer}>
        <div className={styles.footerInner}>
          <div className={styles.footerBrandCol}>
            <span className={styles.footerBrand}>Casaval</span>
            <p className={styles.footerDisclaimer}>{FOOTER_DISCLAIMER}</p>
          </div>
          <nav className={styles.footerNav}>
            <Link href="/mt">Malta map</Link>
            <Link href="/mt/valuation">Run a case</Link>
            <Link href="/login">Sign in</Link>
            <a href="mailto:hello@casaval.eu">Contact</a>
          </nav>
        </div>
      </footer>
    </main>
  );
}
