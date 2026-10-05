/**
 * types/user.ts
 * Identity contracts mirroring the Firestore `users` collection.
 */

/** How the account authenticated with Firebase. */
export type LoginMethod = 'email' | 'google';

/** A user profile as persisted by `POST /api/user/sync`. */
export interface UserProfile {
  /** Firebase Auth UID — also the Firestore document ID. */
  uid: string;
  email: string;
  displayName: string;
  loginMethod: LoginMethod;
  /** ISO 8601 timestamp. */
  createdAt: string;
  /** ISO 8601 timestamp. */
  lastLogin: string;
}
