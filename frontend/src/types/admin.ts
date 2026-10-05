/**
 * types/admin.ts
 * ──────────────
 * Type contracts for the admin API endpoints.
 */

/** Payload of `GET /api/admin/verify`. */
export interface AdminVerifyData {
  isAdmin: boolean;
  uid: string;
  email: string;
}

/** A user profile as returned by the admin users endpoint. */
export interface AdminUser {
  uid: string;
  email: string;
  displayName: string;
  loginMethod: string;
  role: string;
  createdAt: string | null;
  lastLogin: string | null;
}

/** Payload of `GET /api/admin/users`. */
export interface AdminUsersData {
  users: AdminUser[];
  total: number;
}

/** A scan record as returned by the admin scans endpoint. */
export interface AdminScan {
  id: string;
  uid: string;
  primaryLabel: string;
  confidence: number;
  allResults: Array<{ label: string; confidence: number }>;
  modelId: string;
  imageHash: string;
  timestamp: string | null;
}

/** Payload of `GET /api/admin/scans`. */
export interface AdminScansData {
  scans: AdminScan[];
  total: number;
}

/** Payload of `GET /api/admin/stats`. */
export interface AdminStatsData {
  totalUsers: number;
  totalScans: number;
  diseaseDistribution: Record<string, number>;
  loginMethodDistribution: Record<string, number>;
  model: string;
}

/** Payload of `POST /api/admin/promote`. */
export interface AdminPromoteData {
  email: string;
  uid: string;
  promoted: boolean;
}
