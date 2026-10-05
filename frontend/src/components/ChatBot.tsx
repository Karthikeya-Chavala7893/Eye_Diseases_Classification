'use client';

/**
 * components/ChatBot.tsx
 * ──────────────────────
 * Fixed bottom-right interactive chatbot widget.
 * Features:
 * 1. Vertical Category Menu: All 5 categories listed vertically with icons & descriptions.
 * 2. Vertical Questions View: Clicking any category opens its questions vertically with a Back button.
 * 3. Clean Q&A Card Accordion: Clicking any question smoothly reveals its clear, formatted answer.
 */

import { useEffect, useRef, useState } from 'react';

interface QA {
  q: string;
  a: string;
}

interface Category {
  id: string;
  label: string;
  icon: string;
  description: string;
  color: string;
  items: QA[];
}

const CATEGORIES: readonly Category[] = [
  {
    id: 'home-mode',
    label: 'Home Eye Check',
    icon: '🏠',
    description: 'Self-screening with smartphone camera & symptom triage',
    color: '#06B6D4',
    items: [
      {
        q: 'What is the Daily Home Eye Check?',
        a: 'It is a quick, no-equipment screening where you upload a close-up smartphone photo of your eye and tick a short symptom checklist. Our rule engine instantly scores five common home conditions from allergy irritation to early vision-loss warning signs.',
      },
      {
        q: 'Do I need a special camera for the Home Check?',
        a: 'No. Any modern smartphone camera works fine. Just take a well-lit close-up of your open eye from about 15-20 cm away. Avoid using flash directly into the eye.',
      },
      {
        q: 'What conditions can the Home Check detect?',
        a: '1. Itchiness & Allergy Irritation\n2. Digital Eye Strain & Dry Eye\n3. Bloodshot Red Eye / Conjunctivitis\n4. Visible Lens Cloudiness (early cataract signs)\n5. Early Vision Loss Red-Alert (urgent referral)',
      },
      {
        q: 'How accurate is the Home Check?',
        a: 'The Home Check is a triage guide, not a clinical diagnosis. It uses symptom weights and basic image colour cues to point you toward the right action. Think of it as a smart first-aid assistant — always consult a doctor for definitive answers.',
      },
    ],
  },
  {
    id: 'clinical-scan',
    label: 'Clinical Retinal Scan',
    icon: '🏥',
    description: 'RETFound ViT AI model for hospital fundus & OCT scans',
    color: '#8B5CF6',
    items: [
      {
        q: 'What is the Clinical Retinal Scan?',
        a: 'It is an AI analysis of a retinal fundus photograph or OCT scan using our fine-tuned RETFound Vision Transformer model. It detects four conditions: Healthy Retina, Diabetic Retinopathy, Glaucoma, and Cataract with 91.6% test accuracy.',
      },
      {
        q: 'What kind of image do I need for a Clinical Scan?',
        a: 'A retinal fundus photograph (circular, showing the optic disc and blood vessels) or an OCT B-scan. These are captured by a fundus camera at an eye clinic. A regular phone selfie of your eye will not work for the Clinical Scan.',
      },
      {
        q: 'How long does the AI analysis take?',
        a: 'Typically under 30 seconds. The first request after the server starts may take up to 5 seconds longer while the RETFound model loads into memory.',
      },
      {
        q: 'Can I download a report of my results?',
        a: 'Yes. After your Clinical Scan results appear, tap the Download PDF Report button to save a full medical-grade summary including diagnosis, confidence score, recommendations, and prevention tips to share with your doctor.',
      },
    ],
  },
  {
    id: 'diseases',
    label: 'Eye Conditions',
    icon: '👁️',
    description: 'Diabetic Retinopathy, Glaucoma, Cataracts & Healthy Retina',
    color: '#10B981',
    items: [
      {
        q: 'What is Diabetic Retinopathy?',
        a: 'Diabetic Retinopathy is damage to the blood vessels in the retina caused by long-term high blood sugar. It is the leading cause of blindness in working-age adults. Early DR has no symptoms, which is why AI screening is critical.',
      },
      {
        q: 'What is Glaucoma?',
        a: 'Glaucoma damages the optic nerve, often due to elevated eye pressure. Called the silent thief of sight, it causes no pain and no early vision changes. Untreated, it leads to irreversible peripheral blindness.',
      },
      {
        q: 'What is a Cataract?',
        a: 'A cataract is a clouding of the natural lens inside the eye, making vision foggy or faded. It develops slowly with age and is corrected by a safe 15-minute lens-replacement surgery with excellent outcomes.',
      },
      {
        q: 'What does a Healthy Retina result mean?',
        a: 'No signs of the four detectable conditions were found. Continue annual eye exams, maintain good blood sugar and blood pressure, eat antioxidant-rich foods, and protect your eyes from UV light.',
      },
    ],
  },
  {
    id: 'privacy',
    label: 'Privacy & Security',
    icon: '🔐',
    description: 'Zero-disk RAM processing, encryption & data privacy',
    color: '#F59E0B',
    items: [
      {
        q: 'Are my eye images stored permanently?',
        a: 'No. Images are processed entirely in volatile server RAM and discarded the moment inference is complete. No raw retinal images are ever written to disk or saved to any database.',
      },
      {
        q: 'Is my scan history private?',
        a: 'Your scan history (label, confidence score, timestamp) is stored in Firestore under your Firebase UID. Only you can see it. VisionAI staff do not have access to individual scan records.',
      },
      {
        q: 'Is my account data secure?',
        a: 'Authentication uses Firebase Auth with industry-standard JWT tokens. Passwords are never stored by VisionAI. Firebase handles credential storage with bcrypt hashing and all API calls use HTTPS.',
      },
    ],
  },
  {
    id: 'general',
    label: 'General Help',
    icon: '❓',
    description: 'Account setup, login, 7-day sessions & disclaimer',
    color: '#6366F1',
    items: [
      {
        q: 'Who is VisionAI for?',
        a: 'VisionAI is designed for patients, caregivers, rural health workers, and clinics who need accessible, fast, AI-powered eye screening. The Home Mode serves everyday users at home; the Clinical Scan serves clinics and doctors with fundus cameras.',
      },
      {
        q: 'Is VisionAI a replacement for an eye doctor?',
        a: 'No. VisionAI is a screening and triage tool, not a substitute for professional medical care. Always consult a qualified ophthalmologist for diagnosis, treatment, and prescriptions.',
      },
      {
        q: 'How do I create an account?',
        a: 'Click Get Screened or Login, then choose Create Account. Fill in your name, email, and a password of at least 8 characters. You can also sign up with Google in one click.',
      },
      {
        q: 'Why does the Screening button ask me to log in again?',
        a: 'The screening page is protected to keep your health records private. Log in once and your session stays active for 7 days without needing to sign in again.',
      },
    ],
  },
];

export function ChatBot(): JSX.Element {
  const [open, setOpen] = useState(false);
  const [selectedCatId, setSelectedCatId] = useState<string | null>(null);
  const [openQA, setOpenQA] = useState<string | null>(null);
  const [unread, setUnread] = useState(true);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const toggleOpen = () => {
    setOpen((v) => !v);
    setUnread(false);
    if (!open) {
      // Reset view on open
      setSelectedCatId(null);
      setOpenQA(null);
    }
  };

  const selectedCategory = CATEGORIES.find((c) => c.id === selectedCatId) ?? null;

  return (
    <>
      {/* Fixed Floating Launcher Button */}
      <button
        id="chatbot-launcher"
        onClick={toggleOpen}
        aria-label={open ? 'Close help chat' : 'Open help chat'}
        aria-expanded={open}
        style={{
          position: 'fixed',
          bottom: '1.75rem',
          right: '1.75rem',
          width: '58px',
          height: '58px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #0ea5e9 0%, #6366F1 100%)',
          border: 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 8px 24px rgba(14,165,233,0.45)',
          zIndex: 9999,
          transition: 'transform 0.2s ease, box-shadow 0.2s ease',
          transform: open ? 'scale(0.92)' : 'scale(1)',
          color: '#fff',
          fontSize: '1.5rem',
        }}
      >
        {open ? '✕' : '💬'}
        {unread && !open && (
          <span
            style={{
              position: 'absolute',
              top: '3px',
              right: '3px',
              width: '13px',
              height: '13px',
              background: '#EF4444',
              borderRadius: '50%',
              border: '2.5px solid #fff',
              boxShadow: '0 0 8px rgba(239,68,68,0.8)',
            }}
          />
        )}
      </button>

      {/* Main Chat Panel */}
      {open && (
        <div
          ref={panelRef}
          role="dialog"
          aria-label="VisionAI Help Assistant"
          style={{
            position: 'fixed',
            bottom: '5.5rem',
            right: '1.75rem',
            width: 'min(410px, calc(100vw - 2rem))',
            maxHeight: '560px',
            borderRadius: '20px',
            background: 'rgba(255, 255, 255, 0.98)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(14,165,233,0.22)',
            boxShadow: '0 24px 60px rgba(12,74,110,0.22)',
            display: 'flex',
            flexDirection: 'column',
            zIndex: 9998,
            overflow: 'hidden',
            animation: 'chatSlideUp 0.22s cubic-bezier(0.34,1.56,0.64,1)',
          }}
        >
          {/* Header */}
          <div
            style={{
              background: 'linear-gradient(135deg, #0ea5e9 0%, #6366F1 100%)',
              padding: '1rem 1.25rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              boxShadow: '0 2px 8px rgba(14,165,233,0.15)',
            }}
          >
            <span style={{ fontSize: '1.5rem' }}>👁️</span>
            <div style={{ flex: 1 }}>
              <div style={{ color: '#fff', fontWeight: 700, fontSize: '0.98rem', lineHeight: 1.2 }}>
                VisionAI Assistant
              </div>
              <div style={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.76rem' }}>
                Instant answers to common questions
              </div>
            </div>
            <span
              style={{
                background: 'rgba(255,255,255,0.22)',
                color: '#fff',
                fontSize: '0.65rem',
                fontWeight: 700,
                padding: '0.2rem 0.55rem',
                borderRadius: '99px',
                letterSpacing: '0.05em',
              }}
            >
              PREDEFINED
            </span>
          </div>

          {/* Body Content */}
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '0.85rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.6rem',
            }}
          >
            {/* VIEW 1: Vertical Categories List */}
            {!selectedCategory ? (
              <>
                <div style={{ padding: '0.2rem 0.35rem 0.35rem' }}>
                  <p style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    Select a topic to explore:
                  </p>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  {CATEGORIES.map((cat) => (
                    <button
                      key={cat.id}
                      onClick={() => {
                        setSelectedCatId(cat.id);
                        setOpenQA(null);
                      }}
                      className="category-vertical-card"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.85rem',
                        padding: '0.85rem 1rem',
                        borderRadius: '14px',
                        background: '#ffffff',
                        border: '1.5px solid #e2e8f0',
                        cursor: 'pointer',
                        textAlign: 'left',
                        transition: 'all 0.18s ease',
                        boxShadow: '0 2px 6px rgba(15, 23, 42, 0.04)',
                      }}
                    >
                      {/* Icon Circle */}
                      <div
                        style={{
                          width: '42px',
                          height: '42px',
                          borderRadius: '12px',
                          background: `${cat.color}15`,
                          border: `1px solid ${cat.color}35`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '1.35rem',
                          flexShrink: 0,
                        }}
                      >
                        {cat.icon}
                      </div>

                      {/* Text Content */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', marginBottom: '0.15rem' }}>
                          <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#0f172a' }}>
                            {cat.label}
                          </span>
                          <span
                            style={{
                              fontSize: '0.68rem',
                              fontWeight: 700,
                              color: cat.color,
                              background: `${cat.color}18`,
                              padding: '0.15rem 0.45rem',
                              borderRadius: '99px',
                            }}
                          >
                            {cat.items.length} Qs
                          </span>
                        </div>
                        <p style={{ fontSize: '0.75rem', color: '#64748b', lineHeight: 1.3, margin: 0 }}>
                          {cat.description}
                        </p>
                      </div>

                      {/* Chevron Arrow */}
                      <div style={{ color: '#94a3b8', fontSize: '1.1rem', fontWeight: 600, paddingLeft: '0.2rem' }}>
                        ›
                      </div>
                    </button>
                  ))}
                </div>
              </>
            ) : (
              /* VIEW 2: Vertical Questions List for Selected Category */
              <>
                {/* Back to Categories Navigation Bar */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.2rem 0.2rem 0.4rem',
                    borderBottom: '1px solid #e2e8f0',
                    marginBottom: '0.25rem',
                  }}
                >
                  <button
                    onClick={() => {
                      setSelectedCatId(null);
                      setOpenQA(null);
                    }}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      background: '#f1f5f9',
                      border: '1px solid #cbd5e1',
                      padding: '0.35rem 0.75rem',
                      borderRadius: '99px',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      color: '#334155',
                      cursor: 'pointer',
                      transition: 'background 0.15s ease',
                    }}
                  >
                    <span>←</span>
                    <span>All Topics</span>
                  </button>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                    <span style={{ fontSize: '1rem' }}>{selectedCategory.icon}</span>
                    <span style={{ fontSize: '0.82rem', fontWeight: 700, color: selectedCategory.color }}>
                      {selectedCategory.label}
                    </span>
                  </div>
                </div>

                {/* Question Cards (Vertical Stack) */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
                  {selectedCategory.items.map((qa) => {
                    const isOpen = openQA === qa.q;
                    return (
                      <div
                        key={qa.q}
                        style={{
                          borderRadius: '12px',
                          border: isOpen ? `1.5px solid ${selectedCategory.color}77` : '1.5px solid #e2e8f0',
                          background: isOpen ? `${selectedCategory.color}0a` : '#ffffff',
                          overflow: 'hidden',
                          transition: 'all 0.18s ease',
                          boxShadow: isOpen
                            ? `0 4px 14px ${selectedCategory.color}18`
                            : '0 1px 3px rgba(15, 23, 42, 0.03)',
                        }}
                      >
                        {/* Question Button Card */}
                        <button
                          onClick={() => setOpenQA(isOpen ? null : qa.q)}
                          style={{
                            width: '100%',
                            textAlign: 'left',
                            padding: '0.75rem 0.95rem',
                            background: 'transparent',
                            border: 'none',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'flex-start',
                            gap: '0.65rem',
                            color: isOpen ? selectedCategory.color : '#1e293b',
                            fontWeight: 600,
                            fontSize: '0.84rem',
                            lineHeight: 1.4,
                          }}
                        >
                          <span
                            style={{
                              flexShrink: 0,
                              width: '20px',
                              height: '20px',
                              borderRadius: '50%',
                              background: isOpen ? selectedCategory.color : '#f1f5f9',
                              color: isOpen ? '#ffffff' : '#64748b',
                              border: isOpen ? 'none' : '1px solid #cbd5e1',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: '0.7rem',
                              fontWeight: 800,
                              marginTop: '0.05rem',
                              transition: 'all 0.2s',
                            }}
                          >
                            {isOpen ? '−' : '+'}
                          </span>
                          <span style={{ flex: 1 }}>{qa.q}</span>
                        </button>

                        {/* Clean Answer Container */}
                        {isOpen && (
                          <div
                            style={{
                              padding: '0.2rem 1rem 0.9rem 2.5rem',
                              fontSize: '0.81rem',
                              color: '#334155',
                              lineHeight: 1.65,
                              whiteSpace: 'pre-line',
                              animation: 'chatFadeIn 0.2s ease',
                              borderTop: '1px dashed #e2e8f0',
                            }}
                          >
                            <div style={{ paddingTop: '0.5rem' }}>{qa.a}</div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>

          {/* Footer Guide */}
          <div
            style={{
              padding: '0.65rem 1rem',
              borderTop: '1px solid #e2e8f0',
              fontSize: '0.72rem',
              color: '#64748b',
              textAlign: 'center',
              background: '#f8fafc',
            }}
          >
            {!selectedCategory
              ? '💡 Click any category above to view its questions'
              : '💡 Click any question to reveal the full explanation'}
          </div>
        </div>
      )}

      {/* Embedded Component Styles */}
      <style>{`
        @keyframes chatSlideUp {
          from { opacity: 0; transform: translateY(16px) scale(0.96); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes chatFadeIn {
          from { opacity: 0; transform: translateY(-4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        #chatbot-launcher:hover {
          transform: scale(1.08) !important;
          box-shadow: 0 12px 32px rgba(14,165,233,0.55) !important;
        }
        .category-vertical-card:hover {
          border-color: #0ea5e9 !important;
          background: #f0f9ff !important;
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(14, 165, 233, 0.12) !important;
        }
      `}</style>
    </>
  );
}
