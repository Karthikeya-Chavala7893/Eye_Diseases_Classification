'use client';

/**
 * app/screening/page.tsx
 * ──────────────────────
 * The VisionAI screening gateway — a dual-mode experience over one endpoint.
 *
 *   🏠 Daily Home Mode     symptom checklist (+ optional phone photo)
 *                          → rule-based triage → 5 home cards
 *   🏥 Clinical RTF Mode   fundus / OCT retinal scan
 *                          → RETFound inference → the original 4 clinical cards
 *
 * The clinical arm is byte-for-byte the flow this page has always run: upload →
 * validate → POST /api/predict with a Bearer token → render the primary
 * finding, the full differential, and the PDF export. Home Mode sits alongside
 * it and never touches the model.
 */

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

import { MinimalFooter } from '@/components/Footer';
import { ImageUploader } from '@/components/ImageUploader';
import { ModeToggle } from '@/components/ModeToggle';
import { Navbar, type NavLink } from '@/components/Navbar';
import { PdfReportButton } from '@/components/PdfReportButton';
import { ResultCard } from '@/components/ResultCard';
import { SymptomChecklist } from '@/components/SymptomChecklist';
import { ConfidenceBar, getConfidenceLevel } from '@/components/ConfidenceBar';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { useAuth } from '@/hooks/useAuth';
import { usePrediction } from '@/hooks/usePrediction';
import { getDisease } from '@/lib/diseases';
import { hasRedFlag } from '@/lib/homeTriage';
import type { ScreeningMode } from '@/types/prediction';

const NAV_LINKS: NavLink[] = [
  { href: '/', label: 'Home' },
  { href: '/#features', label: 'Features' },
  { href: '/screening', label: 'AI Screening', active: true },
  { href: '/#awareness', label: 'Eye Health' },
];

/**
 * Minimum confidence (%) to show a prediction as a full result card.
 * Predictions below this are collapsed into an "Other Possibilities" list.
 */
const MIN_DISPLAY_CONFIDENCE = 5;

/**
 * If the top prediction is below this threshold, the result is considered
 * inconclusive — the model is not confident enough to render a full diagnosis.
 * Clinical mode only: a home card reports a symptom match, not a probability.
 */
const INCONCLUSIVE_THRESHOLD = 30;

/** The home card that must trigger the hospital-escalation banner. */
const RED_ALERT_CARD = 'Home_Vision_Loss_Alert';



/**
 * Darken a hex colour by a percentage.
 *
 * Ported from `darken()` in the legacy static/js/app.js; used to build the
 * primary-result gradient.
 *
 * @param hex Source colour, e.g. "#10B981".
 * @param pct Percentage to darken by.
 * @returns The darkened hex colour.
 */
function darken(hex: string, pct: number): string {
  const value = parseInt(hex.replace('#', ''), 16);
  const amount = Math.round(2.55 * -pct);
  const clamp = (channel: number): number => Math.max(0, Math.min(255, channel + amount));
  const r = clamp(value >> 16);
  const g = clamp((value >> 8) & 0xff);
  const b = clamp(value & 0xff);
  return `#${(0x1000000 + r * 0x10000 + g * 0x100 + b).toString(16).slice(1)}`;
}

/** Render the authenticated screening page. */
export default function ScreeningPage(): JSX.Element {
  const router = useRouter();
  const { user, loading } = useAuth();
  const { status, previewUrl, result, error, busy, analyze, assess, retry, reset } =
    usePrediction();

  const [mode, setMode] = useState<ScreeningMode>('home');
  const [symptoms, setSymptoms] = useState<ReadonlySet<string>>(() => new Set());
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const analysisRef = useRef<HTMLDivElement | null>(null);

  // Client-side guard backing up the Edge Middleware redirect.
  useEffect(() => {
    if (!loading && !user) router.replace('/login?next=/screening');
  }, [loading, user, router]);

  // Bring the analysis panel into view as soon as work starts.
  useEffect(() => {
    if (status !== 'idle') {
      analysisRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [status]);

  // The home photo preview is owned here, not by the hook, so revoke it here.
  useEffect(() => () => {
    if (photoPreview) URL.revokeObjectURL(photoPreview);
  }, [photoPreview]);

  /** Drop the home-mode photo and release its object URL. */
  const clearPhoto = useCallback((): void => {
    setPhotoPreview((current) => {
      if (current) URL.revokeObjectURL(current);
      return null;
    });
    setPhoto(null);
  }, []);

  /** Stage a home-mode photo for submission alongside the checklist. */
  const choosePhoto = useCallback((file: File): void => {
    setPhotoPreview((current) => {
      if (current) URL.revokeObjectURL(current);
      return URL.createObjectURL(file);
    });
    setPhoto(file);
  }, []);

  const toggleSymptom = useCallback((id: string): void => {
    setSymptoms((current) => {
      const next = new Set(current);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  }, []);

  /** Switch arms of the gateway, discarding whatever the other arm was showing. */
  const switchMode = useCallback(
    (next: ScreeningMode): void => {
      if (next === mode) return;
      reset();
      setPdfError(null);
      setMode(next);
    },
    [mode, reset],
  );

  /** Clear the home intake form without leaving Home Mode. */
  const resetHome = useCallback((): void => {
    reset();
    clearPhoto();
    setSymptoms(new Set());
  }, [reset, clearPhoto]);

  if (loading || !user) {
    return (
      <main className="screening-main">
        <div className="container">
          <div className="welcome-section" aria-busy="true">
            <h1 className="welcome-title">Loading…</h1>
            <p className="welcome-subtitle">Verifying your session</p>
          </div>
        </div>
      </main>
    );
  }

  const displayName = user.displayName ?? user.email?.split('@')[0] ?? 'there';
  const firstName = displayName.split(' ')[0];

  // Only render results that belong to the mode currently on screen — switching
  // modes resets state, so a stale panel can never outlive its own arm.
  const activeResult = result?.mode === mode ? result : null;
  const isHome = mode === 'home';
  const predictions = activeResult?.predictions ?? [];
  const top = predictions[0];
  const topDisease = top ? getDisease(top.label) : null;
  const visibleError = pdfError ?? error;

  // Fix E: Is the result inconclusive? (top confidence < INCONCLUSIVE_THRESHOLD)
  // Home matches are not probabilities, so they are never "inconclusive".
  const isInconclusive = !isHome && top ? top.confidence < INCONCLUSIVE_THRESHOLD : false;

  // Fix B: Split predictions into full cards vs collapsed "Other Possibilities"
  const visiblePredictions = predictions.filter((p) => p.confidence >= MIN_DISPLAY_CONFIDENCE);
  const collapsedPredictions = predictions.filter((p) => p.confidence < MIN_DISPLAY_CONFIDENCE);

  const showEscalation = isHome && top?.label === RED_ALERT_CARD;
  const isHealthy = isHome && top?.is_healthy === true;
  const isLowEvidence = isHome && top?.low_evidence === true;
  const homeModelUsed = isHome && activeResult?.home_model_used === true;
  const canSubmitHome = symptoms.size > 0 || photo !== null;

  return (
    <>
      <Navbar links={NAV_LINKS} />

      <main className="screening-main">
        <div className="container">
          <div className="welcome-section">
            <h1 className="welcome-title">Welcome, {firstName}!</h1>
            <p className="welcome-subtitle">
              {isHome
                ? 'Tell us what you are noticing and get plain-language guidance in seconds'
                : 'Upload a retinal image for AI-powered eye health analysis'}
            </p>
          </div>

          <ModeToggle mode={mode} onChange={switchMode} disabled={busy} />

          <div className="screening-app">
            {/* ── 🏠 MODE 1: DAILY HOME CHECK ── */}
            {isHome ? (
              <div id="mode-panel-home" role="tabpanel" aria-labelledby="mode-tab-home">
                <SymptomChecklist
                  selected={symptoms}
                  onToggle={toggleSymptom}
                  onClear={() => setSymptoms(new Set())}
                  disabled={busy}
                />

                <ImageUploader
                  variant="home"
                  onSelect={choosePhoto}
                  previewUrl={photoPreview}
                  onClear={clearPhoto}
                  disabled={busy}
                />

                <div className="home-submit">
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!canSubmitHome || busy}
                    onClick={() => assess([...symptoms], photo)}
                  >
                    <span aria-hidden="true">{hasRedFlag(symptoms) ? '🚨' : '🔎'}</span>
                    <span>Run My Home Check</span>
                  </button>
                  {(symptoms.size > 0 || photo) && (
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={resetHome}
                      disabled={busy}
                    >
                      <span aria-hidden="true">↺</span>
                      <span>Start Over</span>
                    </button>
                  )}
                  {!canSubmitHome && (
                    <p className="home-submit-hint">
                      Tick at least one symptom, or add a photo, to run your check.
                    </p>
                  )}
                </div>
              </div>
            ) : (
              /* ── 🏥 MODE 2: CLINICAL RETINAL SCAN ── */
              <div id="mode-panel-clinical" role="tabpanel" aria-labelledby="mode-tab-clinical">
                <ImageUploader
                  onSelect={analyze}
                  previewUrl={previewUrl}
                  onClear={reset}
                  disabled={busy}
                />
              </div>
            )}

            <div
              className="analysis-card"
              id="analysisSection"
              ref={analysisRef}
              style={{ display: status === 'idle' ? 'none' : 'block' }}
            >
              {/* ── Loading ── */}
              {busy && (
                <div className="loading-state" style={{ display: 'block' }}>
                  <Spinner />
                  <h3 className="loading-title">
                    {isHome ? 'Reviewing Your Answers' : 'Analyzing Image'}
                  </h3>
                  <p className="loading-text" aria-live="polite">
                    {isHome
                      ? (photo
                          ? 'Running AI analysis on your photo and matching symptoms…'
                          : 'Matching your symptoms against the home triage guide…')
                      : 'Our AI is examining your retinal image…'}
                  </p>
                  <div className="loading-bar">
                    <div className="loading-progress" />
                  </div>
                </div>
              )}

              {/* ── Results ── */}
              {status === 'success' && activeResult && top && topDisease && (
                <div className="results-state" style={{ display: 'block' }}>
                  <div className="results-header">
                    <div className="results-icon" aria-hidden="true">
                      {isInconclusive ? '🔍' : isHealthy ? '✅' : isHome ? '🏠' : '✨'}
                    </div>
                    <h2 className="results-title">
                      {isInconclusive
                        ? 'Inconclusive Result'
                        : isHealthy
                          ? 'Your Eyes Look Healthy!'
                          : isHome
                            ? 'Your Home Check'
                            : 'Analysis Complete'}
                    </h2>
                    <p className="results-subtitle">
                      Results for {activeResult.user ?? displayName}
                      {homeModelUsed && (
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                            marginLeft: '0.5rem',
                            padding: '0.125rem 0.5rem',
                            borderRadius: '999px',
                            background: 'rgba(16,185,129,0.15)',
                            color: 'var(--emerald-600, #059669)',
                            fontWeight: 600,
                            fontSize: '0.7rem',
                          }}
                        >
                          🤖 AI-Assisted
                        </span>
                      )}
                    </p>
                  </div>

                  {/* Fix E: Inconclusive state when confidence < 30% (clinical only) */}
                  {isInconclusive ? (
                    <div
                      role="alert"
                      style={{
                        background: 'linear-gradient(135deg, #f59e0b, #d97706)',
                        borderRadius: 'var(--radius-xl)',
                        padding: 'var(--space-6)',
                        color: '#fff',
                        marginBottom: 'var(--space-6)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)', marginBottom: 'var(--space-4)' }}>
                        <span style={{ fontSize: '2.5rem' }} aria-hidden="true">⚠️</span>
                        <div>
                          <div style={{ fontSize: '0.8rem', opacity: 0.85, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>Low Confidence Result</div>
                          <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>Image May Not Be a Retinal Fundus Scan</div>
                        </div>
                      </div>
                      <p style={{ opacity: 0.95, marginBottom: 'var(--space-4)', lineHeight: 1.7, fontSize: '0.95rem' }}>
                        The AI&apos;s highest confidence for any disease class is only <strong>{top.confidence.toFixed(1)}%</strong> — which is below the reliable detection threshold of {INCONCLUSIVE_THRESHOLD}%.
                        This typically means the uploaded image is <strong>not a retinal fundus photograph</strong>.
                      </p>
                      <div style={{ background: 'rgba(255,255,255,0.15)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)' }}>
                        <p style={{ fontWeight: 700, marginBottom: 'var(--space-2)', fontSize: '0.9rem' }}>📷 What image does this AI need?</p>
                        <p style={{ fontSize: '0.85rem', opacity: 0.95, lineHeight: 1.6, marginBottom: 'var(--space-3)' }}>
                          This model is trained exclusively on <strong>retinal fundus photographs</strong> — a specialised clinical image of the back of the retina. It is a circular dark image
                          showing the optic disc, blood vessels, and retinal tissue. It is <em>not</em> a regular photo of the eye.
                        </p>
                        <p style={{ fontSize: '0.85rem', opacity: 0.9, lineHeight: 1.6 }}>
                          ✅ Use images from a fundus camera or ophthalmology clinic.<br />
                          ❌ External eye photos, selfies, or non-fundus images will not produce accurate results.
                        </p>
                      </div>
                      <p style={{ fontSize: '0.85rem', opacity: 0.95, marginTop: 'var(--space-4)' }}>
                        No fundus camera?{' '}
                        <button
                          type="button"
                          className="link-button"
                          onClick={() => switchMode('home')}
                        >
                          Try the Daily Home Check instead →
                        </button>
                      </p>
                    </div>
                  ) : (
                    <>
                      {/* Low evidence warning for photo-only results */}
                      {isLowEvidence && (
                        <div
                          role="status"
                          style={{
                            background: 'linear-gradient(135deg, rgba(245,158,11,0.12), rgba(245,158,11,0.06))',
                            border: '1px solid rgba(245,158,11,0.25)',
                            borderRadius: 'var(--radius-lg)',
                            padding: 'var(--space-4)',
                            marginBottom: 'var(--space-4)',
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: 'var(--space-3)',
                          }}
                        >
                          <span style={{ fontSize: '1.5rem', flexShrink: 0 }} aria-hidden="true">📷</span>
                          <div>
                            <p style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.25rem', color: 'var(--amber-700, #b45309)' }}>
                              Photo Estimate Only
                            </p>
                            <p style={{ fontSize: '0.8rem', opacity: 0.85, lineHeight: 1.5 }}>
                              This result is based on photo analysis only — tick any symptoms you feel for a more accurate and detailed check.
                            </p>
                          </div>
                        </div>
                      )}

                      <div
                        id="primaryDiagnosis"
                        className="primary-result"
                        style={{
                          background: `linear-gradient(135deg, ${topDisease.color}, ${darken(topDisease.color, 20)})`,
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--space-3)',
                            marginBottom: 'var(--space-4)',
                          }}
                        >
                          <span style={{ fontSize: '2rem' }} aria-hidden="true">{topDisease.icon}</span>
                          <div>
                            <div style={{ fontSize: '0.875rem', opacity: 0.9 }}>
                              {isHealthy ? 'AI Assessment' : isHome ? 'Closest Match' : 'Primary Finding'}
                            </div>
                            <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{topDisease.name}</div>
                          </div>
                        </div>
                        <p style={{ opacity: 0.9, marginBottom: 'var(--space-4)' }}>{topDisease.desc}</p>
                        {(() => {
                          const cInfo = getConfidenceLevel(top.confidence);
                          const confidenceLabel = isHome
                            ? (top.source === 'ai_model'
                                ? 'AI + Symptom Score'
                                : top.source === 'photo_only'
                                  ? 'Photo Estimate'
                                  : 'Symptom Match')
                            : 'AI Confidence';
                          return (
                            <div
                              style={{
                                background: 'rgba(255,255,255,0.2)',
                                borderRadius: 'var(--radius-lg)',
                                padding: 'var(--space-3)',
                              }}
                            >
                              <div
                                style={{
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center',
                                  marginBottom: 'var(--space-2)',
                                  fontSize: '0.875rem',
                                }}
                              >
                                <span style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                                  {confidenceLabel}
                                  {!isHome && (
                                    <span
                                      style={{
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: '0.25rem',
                                        padding: '0.125rem 0.5rem',
                                        borderRadius: '999px',
                                        background: 'rgba(255,255,255,0.25)',
                                        color: '#fff',
                                        fontWeight: 600,
                                        fontSize: '0.7rem',
                                      }}
                                    >
                                      {cInfo.emoji} {cInfo.level}
                                    </span>
                                  )}
                                </span>
                                <span style={{ fontWeight: 700, fontSize: '1.1rem' }}>{top.confidence.toFixed(1)}%</span>
                              </div>
                              <ConfidenceBar
                                value={top.confidence}
                                label={
                                  isHome
                                    ? `${topDisease.name} ${confidenceLabel.toLowerCase()}`
                                    : `${topDisease.name} confidence level`
                                }
                                showLevel={false}
                              />
                              <p
                                style={{
                                  fontSize: '0.7rem',
                                  opacity: 0.75,
                                  marginTop: '0.5rem',
                                  lineHeight: 1.4,
                                }}
                              >
                                {isHome
                                  ? (top.source === 'ai_model'
                                      ? 'AI model classification combined with any symptoms you reported. This is not a medical diagnosis.'
                                      : 'How closely what you described matches this triage card. This is not a medical diagnosis.')
                                  : 'How confident the AI is that this condition matches your retinal image. This is not a medical diagnosis.'}
                              </p>
                            </div>
                          );
                        })()}
                      </div>
                    </>
                  )}

                  {/* Card 5 escalation: hospital first, one-click clinical scan second. */}
                  {showEscalation && (
                    <div className="escalation-banner" role="alert">
                      <div className="escalation-head">
                        <span aria-hidden="true">🏥</span>
                        <h3>Get seen by a doctor today</h3>
                      </div>
                      <p>
                        Do not treat this with home drops. What you described are warning signs of retinal or
                        optic-nerve distress — such as diabetic retinopathy or glaucoma — and the window for
                        protecting your sight is measured in hours to days, not weeks.
                      </p>
                      <div className="escalation-actions">
                        <button
                          type="button"
                          className="btn btn-primary"
                          onClick={() => switchMode('clinical')}
                        >
                          <span aria-hidden="true">🔄</span>
                          <span>Run a Clinical Retinal Scan</span>
                        </button>
                        <span className="escalation-note">
                          Have a fundus or OCT image from a clinic? Analyse it here while you arrange the appointment.
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Fix B: Full cards only for predictions >= MIN_DISPLAY_CONFIDENCE */}
                  <div id="predictions" className="predictions-list">
                    {visiblePredictions.map((prediction, index) => (
                      <ResultCard
                        key={`${prediction.label}-${index}`}
                        prediction={prediction}
                        index={index}
                        variant={mode}
                      />
                    ))}
                  </div>

                  {/* Fix B: Collapsed "Other Possibilities" for very-low-confidence predictions */}
                  {collapsedPredictions.length > 0 && (
                    <details
                      style={{
                        marginTop: 'var(--space-3)',
                        border: '1px solid var(--border-primary)',
                        borderRadius: 'var(--radius-lg)',
                        overflow: 'hidden',
                      }}
                    >
                      <summary
                        style={{
                          padding: 'var(--space-3) var(--space-4)',
                          cursor: 'pointer',
                          fontWeight: 600,
                          fontSize: '0.8rem',
                          color: 'var(--gray-500)',
                          background: 'var(--bg-secondary)',
                          userSelect: 'none',
                          listStyle: 'none',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                        }}
                      >
                        <span aria-hidden="true">📉</span>
                        {isHome
                          ? `Weaker matches (below ${MIN_DISPLAY_CONFIDENCE}%)`
                          : `Other Possibilities (below ${MIN_DISPLAY_CONFIDENCE}% — very unlikely)`}
                      </summary>
                      <div style={{ padding: 'var(--space-3) var(--space-4)' }}>
                        {collapsedPredictions.map((p) => (
                          <div
                            key={p.label}
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              padding: 'var(--space-2) 0',
                              borderBottom: '1px solid var(--border-primary)',
                              fontSize: '0.82rem',
                              color: 'var(--gray-500)',
                            }}
                          >
                            <span>{isHome ? getDisease(p.label).name : p.label.replace(/_/g, ' ')}</span>
                            <span style={{ fontWeight: 600 }}>{p.confidence.toFixed(1)}%</span>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}

                  <div className="results-actions">
                    {isHome ? (
                      <button type="button" className="btn btn-secondary" onClick={resetHome}>
                        <span aria-hidden="true">🔄</span>
                        <span>New Home Check</span>
                      </button>
                    ) : (
                      <>
                        <PdfReportButton
                          predictions={predictions}
                          patientName={activeResult.user ?? displayName}
                          onError={setPdfError}
                        />
                        <button type="button" className="btn btn-secondary" onClick={reset}>
                          <span aria-hidden="true">🔄</span>
                          <span>New Analysis</span>
                        </button>
                      </>
                    )}
                  </div>

                  <div className="disclaimer-box" role="note" aria-label="Medical Disclaimer">
                    <span className="disclaimer-icon" aria-hidden="true">⚠️</span>
                    <div className="disclaimer-content">
                      <strong>EDUCATIONAL DEMONSTRATION DISCLAIMER</strong>
                      <p>
                        {isHome
                          ? `This home check matches what you reported against a fixed guidance table. It is not
                             an examination, it cannot see inside your eye, and it does not provide medical
                             advice or diagnosis. Always consult a licensed ophthalmologist or healthcare
                             provider for clinical evaluation.`
                          : `This screening tool is powered by an artificial intelligence model intended
                             strictly for educational and research demonstration purposes. It does not
                             provide medical advice, formal diagnosis, or treatment plans. Always consult
                             a licensed ophthalmologist or healthcare provider for clinical evaluation.`}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* ── Error ── */}
              {status === 'error' && (
                <div className="error-state" style={{ display: 'block' }} role="alert">
                  <div className="error-icon" aria-hidden="true">😔</div>
                  <h3 className="error-title">
                    {isHome ? 'Home Check Failed' : 'Analysis Failed'}
                  </h3>
                  <p className="error-message">{visibleError ?? 'Something went wrong.'}</p>
                  <button type="button" className="btn btn-primary" onClick={retry}>
                    <span aria-hidden="true">🔄</span>
                    <span>Try Again</span>
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="info-cards">
            {isHome ? (
              <>
                <Card icon="🏠" title="No Equipment Needed">
                  Answer a short checklist — a phone photo is optional
                </Card>
                <Card icon="🧭" title="Plain-Language Guidance">
                  Five triage cards, from mild irritation to urgent warning signs
                </Card>
                <Card icon="🚨" title="Escalates When It Matters">
                  Urgent symptoms always route you to a doctor, never to home drops
                </Card>
              </>
            ) : (
              <>
                <Card icon="🔬" title="AI Analysis">
                  Deep learning model trained on thousands of retinal images
                </Card>
                <Card icon="⚡" title="Instant Results">
                  Get your analysis in under 30 seconds
                </Card>
                <Card icon="🔐" title="Secure &amp; Private">
                  Your images are processed securely and never stored
                </Card>
              </>
            )}
          </div>

          <p style={{ textAlign: 'center', marginTop: 'var(--space-8)' }}>
            <Link href="/" className="nav-link">
              ← Back to Home
            </Link>
          </p>
        </div>
      </main>

      <MinimalFooter />
    </>
  );
}
