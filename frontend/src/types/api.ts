/**
 * types/api.ts
 * Transport-level contracts shared by every backend call.
 *
 * The Flask API answers with exactly one envelope shape (backend constraint #21):
 *   success -> { success: true,  data: T }
 *   failure -> { success: false, error: string }
 */

/** Discriminated envelope returned by every `/api/*` endpoint. */
export type ApiResponse<T> =
  | { success: true; data: T; error?: undefined }
  | { success: false; data?: undefined; error: string };

/** Payload of `GET /api/health`. */
export interface HealthData {
  status: 'healthy' | 'degraded';
  model_loaded: boolean;
  firebase_connected: boolean;
  model: string;
  inference: 'local';
}

/** Payload of `GET /api/config`. */
export interface ServerConfig {
  maxFileSizeBytes: number;
  allowedMimeTypes: string[];
  allowedExtensions: string[];
  model: string;
  inference: 'local';
  modelLoaded: boolean;
}

/** Payload of `POST /api/user/sync`. */
export interface UserSyncData {
  uid: string;
  created: boolean;
}

/**
 * Error thrown by the typed fetch wrapper. Carries the HTTP status so callers
 * can branch on 401 (re-auth), 413 (file too large) or 429 (rate limited)
 * without parsing message strings.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}
