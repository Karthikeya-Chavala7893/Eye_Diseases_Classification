/**
 * lib/firebase.ts
 * ───────────────
 * Firebase client SDK bootstrap.
 *
 * Uses the modular v10 SDK only (`firebase/app`, `firebase/auth`) so the bundler
 * can tree-shake — the `firebase/compat` namespace is forbidden (constraint #4).
 *
 * The `NEXT_PUBLIC_FIREBASE_*` values are intentionally public: they identify
 * the project, they do not authenticate it. Real security comes from Firebase
 * Security Rules plus backend JWT verification.
 */

import { getApp, getApps, initializeApp, type FirebaseApp } from 'firebase/app';
import { GoogleAuthProvider, connectAuthEmulator, getAuth, type Auth } from 'firebase/auth';

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? '',
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ?? '',
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? '',
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET ?? '',
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID ?? '',
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID ?? '',
  measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID ?? '',
};

/**
 * True when the client config is complete enough to talk to Firebase.
 *
 * The UI checks this so a missing `.env.local` produces a clear setup message
 * instead of an opaque SDK crash.
 */
export const isFirebaseConfigured: boolean = Boolean(
  firebaseConfig.apiKey && firebaseConfig.authDomain && firebaseConfig.projectId,
);

/**
 * Get (or lazily create) the singleton Firebase app.
 *
 * @returns The initialised `FirebaseApp`.
 * @throws Error when the `NEXT_PUBLIC_FIREBASE_*` variables are missing.
 */
export function getFirebaseApp(): FirebaseApp {
  if (!isFirebaseConfigured) {
    throw new Error(
      'Firebase is not configured. Copy frontend/.env.example to frontend/.env.local ' +
        'and fill in the NEXT_PUBLIC_FIREBASE_* values from your Firebase console.',
    );
  }
  return getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
}

/**
 * Host:port of a local Firebase Auth emulator, e.g. `127.0.0.1:9099`.
 *
 * Set `NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST` to develop and test the full
 * sign-in flow offline, without touching the live Firebase project. Leave it
 * unset in every deployed environment.
 */
const AUTH_EMULATOR_HOST = process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST ?? '';

let emulatorConnected = false;

/**
 * Get the Firebase Auth instance for this app.
 *
 * Connects to the local Auth emulator on first call when
 * `NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST` is set.
 *
 * @returns The `Auth` singleton.
 * @throws Error when Firebase is not configured.
 */
export function getFirebaseAuth(): Auth {
  const auth = getAuth(getFirebaseApp());
  if (AUTH_EMULATOR_HOST && !emulatorConnected) {
    emulatorConnected = true;
    connectAuthEmulator(auth, `http://${AUTH_EMULATOR_HOST}`, { disableWarnings: true });
  }
  return auth;
}

/**
 * Build a Google OIDC provider that always shows the account chooser.
 *
 * @returns A configured `GoogleAuthProvider`.
 */
export function googleProvider(): GoogleAuthProvider {
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: 'select_account' });
  return provider;
}
