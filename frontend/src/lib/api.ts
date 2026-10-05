/**
 * lib/api.ts
 * ──────────
 * Typed fetch wrapper for the Flask JSON API.
 *
 * Responsibilities
 *   * Attach `Authorization: Bearer <Firebase ID token>` to authenticated calls.
 *   * Unwrap the `{ success, data, error }` envelope into a plain `T`.
 *   * Retry ONCE with a force-refreshed token on 401, then give up so the caller
 *     can redirect to /login (spec §4.1 token-refresh strategy).
 *
 * Every non-2xx response becomes an `ApiError` carrying the HTTP status.
 */

import { getIdToken, type User } from 'firebase/auth';

import { ApiError, type ApiResponse, type HealthData, type ServerConfig, type UserSyncData } from '@/types/api';
import type {
  AdminPromoteData,
  AdminScansData,
  AdminStatsData,
  AdminUsersData,
  AdminVerifyData,
} from '@/types/admin';
import type { PredictResponse, ScanHistoryData } from '@/types/prediction';

/** Base URL of the Flask API; overridden per environment. */
export const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:5000';

interface RequestOptions {
  method?: 'GET' | 'POST';
  body?: BodyInit;
  /** Firebase user whose ID token authenticates the call; omit for public routes. */
  user?: User | null;
  signal?: AbortSignal;
  /** Internal: set while replaying a request with a force-refreshed token. */
  forceRefresh?: boolean;
}

/**
 * Perform one API call and unwrap its envelope.
 *
 * @param path API path beginning with `/api/`.
 * @param options Method, body, authenticating user and abort signal.
 * @returns The `data` member of a successful response.
 * @throws ApiError when the request fails, the response is not JSON, or the
 *   envelope reports `success: false`.
 */
async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, user, signal, forceRefresh = false } = options;

  const headers: Record<string, string> = {};
  if (user) {
    // Firebase silently refreshes ~5 minutes before expiry; forceRefresh is the
    // explicit retry path after a 401.
    headers.Authorization = `Bearer ${await getIdToken(user, forceRefresh)}`;
  }
  // FormData sets its own multipart boundary — never override Content-Type.
  if (body && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { method, headers, body, signal });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause;
    throw new ApiError('Network error. Check your connection and that the API is running.', 0);
  }

  // One silent retry with a fresh token, then surface the 401 to the caller.
  if (response.status === 401 && user && !forceRefresh) {
    return request<T>(path, { ...options, forceRefresh: true });
  }

  let payload: ApiResponse<T> | null = null;
  try {
    payload = (await response.json()) as ApiResponse<T>;
  } catch {
    throw new ApiError(`Unexpected non-JSON response (HTTP ${response.status}).`, response.status);
  }

  if (!response.ok || !payload.success) {
    const message = payload.success ? `Request failed (HTTP ${response.status}).` : payload.error;
    throw new ApiError(message, response.status);
  }

  return payload.data;
}

/**
 * Check backend and subsystem health.
 *
 * @returns Model and Firebase readiness flags.
 */
export function fetchHealth(signal?: AbortSignal): Promise<HealthData> {
  return request<HealthData>('/api/health', { signal });
}

/**
 * Fetch the server-authoritative upload limits.
 *
 * @returns Maximum file size and accepted MIME types.
 */
export function fetchServerConfig(signal?: AbortSignal): Promise<ServerConfig> {
  return request<ServerConfig>('/api/config', { signal });
}

/**
 * Upsert the signed-in user's Firestore profile.
 *
 * The body is deliberately empty — the backend derives every field from the
 * verified JWT, so a client can never claim another UID.
 *
 * @param user The authenticated Firebase user.
 * @returns The synced UID and whether the profile was newly created.
 */
export function syncUser(user: User): Promise<UserSyncData> {
  return request<UserSyncData>('/api/user/sync', { method: 'POST', body: '{}', user });
}

/**
 * Submit a retinal image for classification.
 *
 * @param user The authenticated Firebase user.
 * @param file The image chosen by the patient.
 * @param signal Abort signal so an unmounting component cancels the upload.
 * @returns Sorted predictions plus model metadata.
 */
export function predictImage(
  user: User,
  file: File,
  signal?: AbortSignal,
): Promise<PredictResponse> {
  const form = new FormData();
  form.append('mode', 'clinical');
  form.append('image', file);
  return request<PredictResponse>('/api/predict', { method: 'POST', body: form, user, signal });
}

/**
 * Run a Daily Home Mode screening.
 *
 * Hits the same endpoint as {@link predictImage} with `mode=home`, so the
 * result arrives in the identical envelope. The photo is optional — a symptom
 * checklist alone is enough to score the five home cards, and the backend never
 * loads the AI model on this path.
 *
 * @param user The authenticated Firebase user.
 * @param symptoms Ticked symptom ids from `lib/homeTriage.ts`.
 * @param file Optional smartphone photo of the eye.
 * @param signal Abort signal so an unmounting component cancels the request.
 * @returns Home cards sorted by descending match strength.
 */
export function screenHome(
  user: User,
  symptoms: string[],
  file?: File | null,
  signal?: AbortSignal,
): Promise<PredictResponse> {
  const form = new FormData();
  form.append('mode', 'home');
  form.append('symptoms', JSON.stringify(symptoms));
  if (file) form.append('image', file);
  return request<PredictResponse>('/api/predict', { method: 'POST', body: form, user, signal });
}

/**
 * Load the signed-in user's recent screening history.
 *
 * @param user The authenticated Firebase user.
 * @param limit Page size; the backend clamps this to 50.
 * @returns Scan records ordered newest first.
 */
export function fetchScanHistory(
  user: User,
  limit = 10,
  signal?: AbortSignal,
): Promise<ScanHistoryData> {
  return request<ScanHistoryData>(`/api/user/scans?limit=${limit}`, { user, signal });
}


// ═══════════════════════════════════════════════════════════════════════════
// ADMIN API
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Verify whether the signed-in user has admin privileges.
 *
 * @param user The authenticated Firebase user.
 * @returns Admin status, UID and email.
 */
export function verifyAdmin(user: User, signal?: AbortSignal): Promise<AdminVerifyData> {
  return request<AdminVerifyData>('/api/admin/verify', { user, signal });
}

/**
 * Fetch platform-wide statistics for the admin dashboard.
 *
 * @param user The authenticated admin user.
 * @returns Total users, scans, disease distribution and login method distribution.
 */
export function fetchAdminStats(user: User, signal?: AbortSignal): Promise<AdminStatsData> {
  return request<AdminStatsData>('/api/admin/stats', { user, signal });
}

/**
 * Fetch all registered users.
 *
 * @param user The authenticated admin user.
 * @param limit Maximum number of users to return.
 */
export function fetchAdminUsers(
  user: User,
  limit = 50,
  signal?: AbortSignal,
): Promise<AdminUsersData> {
  return request<AdminUsersData>(`/api/admin/users?limit=${limit}`, { user, signal });
}

/**
 * Fetch all scans across the platform.
 *
 * @param user The authenticated admin user.
 * @param limit Maximum number of scans to return.
 */
export function fetchAdminScans(
  user: User,
  limit = 50,
  signal?: AbortSignal,
): Promise<AdminScansData> {
  return request<AdminScansData>(`/api/admin/scans?limit=${limit}`, { user, signal });
}

/**
 * Promote a user to admin by email.
 *
 * @param user The authenticated admin user making the request.
 * @param email The email of the user to promote.
 */
export function promoteToAdmin(
  user: User,
  email: string,
): Promise<AdminPromoteData> {
  return request<AdminPromoteData>('/api/admin/promote', {
    method: 'POST',
    body: JSON.stringify({ email }),
    user,
  });
}
