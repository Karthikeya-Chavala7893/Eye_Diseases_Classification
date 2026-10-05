/**
 * app/page.tsx
 * ────────────
 * Landing page — a Server Component rendered with ISR (revalidated hourly).
 *
 * Ported section-for-section from templates/index.html. The only interactive
 * parts (navigation, theme toggle, the auth-aware screening call to action) are
 * isolated in Client Components so the marketing copy stays server-rendered.
 */

import Link from 'next/link';

import { Footer } from '@/components/Footer';
import { LandingNav } from '@/components/LandingNav';
import { ScreeningCta } from '@/components/ScreeningCta';

/** Regenerate the static landing page at most once an hour. */
export const revalidate = 3600;

/** One feature card on the marketing grid. */
interface Feature {
  icon: string;
  title: string;
  description: string;
}

const FEATURES: readonly Feature[] = [
  {
    icon: '🔍',
    title: 'Early Detection',
    description:
      'Identify diabetic retinopathy and other conditions at their earliest stages, when treatment is most effective.',
  },
  {
    icon: '🤖',
    title: 'AI-Powered Analysis',
    description:
      'Advanced neural networks trained on thousands of retinal images provide clinical-grade accuracy in seconds.',
  },
  {
    icon: '📋',
    title: 'Personalized Guidance',
    description:
      'Receive customized recommendations, lifestyle tips, and prevention strategies based on your results.',
  },
  {
    icon: '🔐',
    title: 'Privacy First',
    description:
      'Your images are processed securely and never stored. We prioritize your privacy and data protection.',
  },
  {
    icon: '📱',
    title: 'Accessible Anywhere',
    description:
      'Use on any device with an internet connection. Bringing eye care to underserved communities worldwide.',
  },
  {
    icon: '📊',
    title: 'Detailed Reports',
    description:
      'Download comprehensive reports to share with your healthcare provider for informed decision-making.',
  },
];

const STEPS: ReadonlyArray<{ number: string; icon: string; title: string; description: string }> = [
  {
    number: '1',
    icon: '📤',
    title: 'Upload Image',
    description:
      'Upload a retinal fundus image from your ophthalmologist or use our mobile capture guide.',
  },
  {
    number: '2',
    icon: '🤖',
    title: 'AI Analysis',
    description:
      'Our deep learning model analyzes your image for signs of diabetic retinopathy and other conditions.',
  },
  {
    number: '3',
    icon: '📋',
    title: 'Get Results',
    description:
      'Receive instant results with severity classification, recommendations, and prevention tips.',
  },
];

/** Five home-mode triage cards previewed on the landing page. */
interface HomeModeCard {
  icon: string;
  title: string;
  badge: string;
  badgeColor: string;
  description: string;
}

const HOME_MODE_CARDS: readonly HomeModeCard[] = [
  {
    icon: '🌿',
    title: 'Itchiness & Allergy Relief',
    badge: 'Mild',
    badgeColor: '#06B6D4',
    description: 'Identifies dust, pollen, and seasonal surface irritation. Provides cold-compress and lubricating-drop guidance so the itch-rub cycle never starts.',
  },
  {
    icon: '📱',
    title: 'Digital Eye Strain & Dry Eye',
    badge: 'Moderate',
    badgeColor: '#F59E0B',
    description: 'Detects screen-fatigue patterns — burning evenings, blur that clears on rest. Delivers the 20-20-20 rule and ergonomic corrections.',
  },
  {
    icon: '🩸',
    title: 'Bloodshot Red Eye & Pink Eye',
    badge: 'Warning',
    badgeColor: '#F97316',
    description: 'Flags bloodshot sclera, crusty discharge, or pink-eye exposure. Guides hygiene, saline rinse, and antibiotic-drop awareness.',
  },
  {
    icon: '🌫️',
    title: 'Visible Lens Cloudiness',
    badge: 'Chronic',
    badgeColor: '#8B5CF6',
    description: 'Detects milky-pupil haze and night-halo patterns typical of early cataract. Advises UV protection and ophthalmologist timing.',
  },
  {
    icon: '🚨',
    title: 'Early Vision Loss Alert',
    badge: 'Urgent',
    badgeColor: '#DC2626',
    description: 'Escalates sudden blur, dark floaters, or tunnel vision immediately — and offers a one-click switch to the Clinical Retinal Scan.',
  },
];

const TRUST_ITEMS: ReadonlyArray<{ icon: string; text: string }> = [
  { icon: '🏥', text: 'Clinically Validated' },
  { icon: '🤖', text: 'Clinical-Grade AI' },
  { icon: '⚡', text: 'Instant Results' },
  { icon: '🌍', text: 'Accessible Worldwide' },
  { icon: '🔬', text: 'Deep Learning AI' },
];

const STATS: ReadonlyArray<{ icon: string; value: string; desc: string }> = [
  { icon: '🌍', value: '463M', desc: 'People with diabetes worldwide' },
  { icon: '👁️', value: '1 in 3', desc: 'Diabetics develop retinopathy' },
  { icon: '⏰', value: '95%', desc: 'Vision loss preventable with early detection' },
  { icon: '🔬', value: '98%', desc: 'AI detection accuracy' },
];

/**
 * Render the public landing page.
 */
export default function HomePage(): JSX.Element {
  return (
    <>
      <LandingNav />

      {/* ═══ HERO ═══ */}
      <section className="hero" id="home">
        <div className="hero-bg">
          <div className="hero-gradient" />
          <div className="hero-pattern" />
        </div>
        <div className="hero-container">
          <div className="hero-content">
            <div className="hero-badge">
              <span className="badge-icon" aria-hidden="true">🔬</span>
              <span>AI-Powered Eye Health Technology</span>
            </div>
            <h1 className="hero-title">
              Protecting Your Vision with <span className="gradient-text">Advanced AI</span>
            </h1>
            <p className="hero-description">
              Early detection saves sight. Our cutting-edge artificial intelligence analyzes retinal
              images to detect diabetic retinopathy and other eye conditions with clinical-grade
              accuracy.
            </p>
            <div className="hero-actions">
              <Link href="#screening" className="btn btn-primary btn-lg">
                <span aria-hidden="true">🔍</span>
                <span>Start Free Screening</span>
              </Link>
              <Link href="#how-it-works" className="btn btn-secondary btn-lg">
                <span aria-hidden="true">▶️</span>
                <span>See How It Works</span>
              </Link>
            </div>
            <div className="hero-stats">
              <div className="stat-item">
                <span className="stat-number">98%</span>
                <span className="stat-label">Accuracy Rate</span>
              </div>
              <div className="stat-divider" />
              <div className="stat-item">
                <span className="stat-number">30s</span>
                <span className="stat-label">Analysis Time</span>
              </div>
              <div className="stat-divider" />
              <div className="stat-item">
                <span className="stat-number">5+</span>
                <span className="stat-label">Conditions Detected</span>
              </div>
            </div>
          </div>

          <div className="hero-visual">
            <div className="hero-image-container">
              <div className="floating-card card-1">
                <span className="card-icon" aria-hidden="true">✅</span>
                <span className="card-text">No DR Detected</span>
              </div>
              <div className="floating-card card-2">
                <span className="card-icon" aria-hidden="true">🔬</span>
                <span className="card-text">AI Analysis</span>
              </div>
              <div className="floating-card card-3">
                <span className="card-icon" aria-hidden="true">📊</span>
                <span className="card-text">98% Confidence</span>
              </div>
              <div className="eye-graphic" aria-hidden="true">
                <div className="eye-outer">
                  <div className="eye-inner">
                    <div className="eye-pupil">
                      <div className="scan-line" />
                    </div>
                  </div>
                </div>
                <div className="eye-glow" />
              </div>
            </div>
          </div>
        </div>

        <div className="hero-wave" aria-hidden="true">
          <svg viewBox="0 0 1440 120" preserveAspectRatio="none">
            <path d="M0,64 C480,150 960,-20 1440,64 L1440,120 L0,120 Z" fill="currentColor" />
          </svg>
        </div>
      </section>

      {/* ═══ TRUST ═══ */}
      <section className="trust-section">
        <div className="container">
          <div className="trust-grid">
            {TRUST_ITEMS.map((item) => (
              <div key={item.text} className="trust-item">
                <span className="trust-icon" aria-hidden="true">{item.icon}</span>
                <span className="trust-text">{item.text}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ FEATURES ═══ */}
      <section className="features-section" id="features">
        <div className="container">
          <div className="section-header">
            <span className="section-badge">Features</span>
            <h2 className="section-title">Advanced Eye Care Technology</h2>
            <p className="section-description">
              Our AI-powered platform combines cutting-edge deep learning with medical expertise to
              provide accurate, accessible eye health screening.
            </p>
          </div>
          <div className="features-grid">
            {FEATURES.map((feature) => (
              <article key={feature.title} className="feature-card">
                <div className="feature-icon-wrapper">
                  <span className="feature-icon" aria-hidden="true">{feature.icon}</span>
                </div>
                <h3 className="feature-title">{feature.title}</h3>
                <p className="feature-description">{feature.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ HOW IT WORKS ═══ */}
      <section className="how-section" id="how-it-works">
        <div className="container">
          <div className="section-header">
            <span className="section-badge">Process</span>
            <h2 className="section-title">How It Works</h2>
            <p className="section-description">
              Get your eye health assessment in three simple steps
            </p>
          </div>
          <div className="steps-container">
            {STEPS.map((step, index) => (
              <div key={step.number} style={{ display: 'contents' }}>
                <article className="step-card">
                  <div className="step-number">{step.number}</div>
                  <div className="step-icon" aria-hidden="true">{step.icon}</div>
                  <h3 className="step-title">{step.title}</h3>
                  <p className="step-description">{step.description}</p>
                </article>
                {index < STEPS.length - 1 && (
                  <div className="step-connector" aria-hidden="true">
                    <div className="connector-line" />
                    <div className="connector-arrow">→</div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ DAILY HOME SCREENING ═══ */}
      <section className="features-section" id="home-screening" style={{ background: 'var(--bg-secondary, #f8fafc)' }}>
        <div className="container">
          <div className="section-header">
            <span className="section-badge">Daily Home Mode</span>
            <h2 className="section-title">Screen Your Eyes from Home</h2>
            <p className="section-description">
              No fundus camera? No problem. The Daily Home Mode lets anyone check their eye
              health using a regular smartphone photo and a 30-second symptom checklist — no
              specialist equipment required.
            </p>
          </div>

          {/* Two-mode comparison callout */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '1.5rem',
            marginBottom: '3rem',
          }}>
            {/* Home Mode card */}
            <div style={{
              background: 'linear-gradient(135deg, rgba(6,182,212,0.08) 0%, rgba(59,130,246,0.08) 100%)',
              border: '1.5px solid rgba(6,182,212,0.3)',
              borderRadius: '16px',
              padding: '1.75rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                <span style={{ fontSize: '1.75rem' }}>🏠</span>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--text-primary)' }}>Daily Home Check</div>
                  <div style={{ fontSize: '0.78rem', color: '#06B6D4', fontWeight: 600 }}>For everyone at home</div>
                </div>
              </div>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
                Upload a close-up smartphone photo of your eye, tick the symptoms you feel, and get
                instant plain-language guidance — from allergy relief to urgent referral advice.
              </p>
              <ul style={{ marginTop: '1rem', paddingLeft: '1.2rem', fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                <li>No specialist equipment needed</li>
                <li>5 targeted triage conditions</li>
                <li>Instant home-care action plan</li>
                <li>Red-flag escalation to clinical scan</li>
              </ul>
            </div>

            {/* Clinical Mode card */}
            <div style={{
              background: 'linear-gradient(135deg, rgba(139,92,246,0.08) 0%, rgba(99,102,241,0.08) 100%)',
              border: '1.5px solid rgba(139,92,246,0.3)',
              borderRadius: '16px',
              padding: '1.75rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                <span style={{ fontSize: '1.75rem' }}>🏥</span>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--text-primary)' }}>Clinical Retinal Scan</div>
                  <div style={{ fontSize: '0.78rem', color: '#8B5CF6', fontWeight: 600 }}>For fundus &amp; OCT images</div>
                </div>
              </div>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
                Upload a retinal fundus or OCT scan and let our fine-tuned RETFound Foundation Model
                deliver a clinical-grade diagnosis with 91.6% accuracy.
              </p>
              <ul style={{ marginTop: '1rem', paddingLeft: '1.2rem', fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                <li>91.6% test accuracy (RETFound ViT)</li>
                <li>4 clinical conditions detected</li>
                <li>Severity rating &amp; confidence score</li>
                <li>Downloadable medical PDF report</li>
              </ul>
            </div>
          </div>

          {/* 5 home triage cards */}
          <div className="features-grid">
            {HOME_MODE_CARDS.map((card) => (
              <article key={card.title} className="feature-card">
                <div className="feature-icon-wrapper">
                  <span className="feature-icon" aria-hidden="true">{card.icon}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                  <h3 className="feature-title" style={{ margin: 0 }}>{card.title}</h3>
                  <span style={{
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    padding: '0.15rem 0.55rem',
                    borderRadius: '99px',
                    background: `${card.badgeColor}22`,
                    color: card.badgeColor,
                    letterSpacing: '0.03em',
                    whiteSpace: 'nowrap',
                  }}>{card.badge}</span>
                </div>
                <p className="feature-description">{card.description}</p>
              </article>
            ))}
          </div>

          {/* Bottom CTA row */}
          <div style={{ textAlign: 'center', marginTop: '2.5rem' }}>
            <Link href="/screening" className="btn btn-primary btn-lg">
              <span aria-hidden="true">🏠</span>
              <span>Try Home Eye Check Now</span>
            </Link>
          </div>
        </div>
      </section>

      {/* ═══ SCREENING CTA ═══ */}
      <section className="screening-section" id="screening">
        <div className="container">
          <div className="section-header">
            <span className="section-badge">AI Screening</span>
            <h2 className="section-title">Start Your Eye Health Assessment</h2>
            <p className="section-description">
              Upload a retinal image for instant AI-powered analysis and personalized recommendations
            </p>
          </div>
          <ScreeningCta />
        </div>
      </section>

      {/* ═══ AWARENESS ═══ */}
      <section className="awareness-section" id="awareness">
        <div className="container">
          <div className="section-header">
            <span className="section-badge">Eye Health</span>
            <h2 className="section-title">Protect Your Vision</h2>
            <p className="section-description">
              Understanding diabetic retinopathy and eye health is crucial for prevention
            </p>
          </div>

          <div className="awareness-grid">
            <article className="awareness-card">
              <div className="awareness-icon" aria-hidden="true">👀</div>
              <h3>What is Diabetic Retinopathy?</h3>
              <p>
                A diabetes complication affecting the eyes. High blood sugar damages blood vessels in
                the retina, potentially leading to vision loss if untreated.
              </p>
            </article>
            <article className="awareness-card">
              <div className="awareness-icon" aria-hidden="true">⚠️</div>
              <h3>Warning Signs</h3>
              <ul className="warning-list">
                <li>Blurred or fluctuating vision</li>
                <li>Dark spots or floaters</li>
                <li>Difficulty seeing colors</li>
                <li>Vision loss in advanced stages</li>
              </ul>
            </article>
            <article className="awareness-card">
              <div className="awareness-icon" aria-hidden="true">🛡️</div>
              <h3>Prevention Tips</h3>
              <ul className="prevention-list">
                <li>Control blood sugar levels</li>
                <li>Annual comprehensive eye exams</li>
                <li>Manage blood pressure</li>
                <li>Quit smoking</li>
                <li>Healthy diet &amp; exercise</li>
              </ul>
            </article>
          </div>

          <div className="awareness-cta">
            <div className="cta-content">
              <h3>Early Detection Saves Sight</h3>
              <p>
                Don&apos;t wait for symptoms. Regular screening can detect problems before vision
                loss occurs.
              </p>
            </div>
            <Link href="#screening" className="btn btn-primary btn-lg">
              <span aria-hidden="true">🔍</span>
              <span>Get Screened Now</span>
            </Link>
          </div>
        </div>
      </section>

      {/* ═══ STATISTICS ═══ */}
      <section className="stats-section">
        <div className="container">
          <div className="stats-grid">
            {STATS.map((stat) => (
              <div key={stat.value} className="stat-card">
                <div className="stat-icon" aria-hidden="true">{stat.icon}</div>
                <div className="stat-value">{stat.value}</div>
                <div className="stat-desc">{stat.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}
