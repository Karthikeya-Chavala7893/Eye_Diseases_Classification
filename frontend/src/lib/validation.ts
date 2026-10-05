/**
 * lib/validation.ts
 * ─────────────────
 * Client-side image checks, mirroring the backend whitelist.
 *
 * This is a UX shortcut, never a security control — `backend/app.py` re-validates
 * every upload independently (constraint #9, defence in depth).
 */

/** Maximum accepted upload size: 16 MB, matching `Config.MAX_CONTENT_LENGTH`. */
export const MAX_FILE_SIZE_BYTES = 16 * 1024 * 1024;

/** MIME types the backend will decode. */
export const ALLOWED_MIME_TYPES: readonly string[] = [
  'image/png',
  'image/jpeg',
  'image/jpg',
  'image/bmp',
  'image/tiff',
  'image/webp',
];

/** Upper bound on pixel dimensions, guarding against decompression bombs. */
export const MAX_IMAGE_DIMENSION = 8192;

/** Outcome of a validation pass. */
export interface ValidationResult {
  ok: boolean;
  error?: string;
}

/**
 * Format a byte count for display.
 *
 * @param bytes Size in bytes.
 * @returns A short human-readable string such as "4.2 MB".
 */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Validate a chosen file's type and size before any upload begins.
 *
 * @param file The file from the picker or a drop event.
 * @returns `{ ok: true }`, or `{ ok: false, error }` with a user-facing message.
 */
export function validateImageFile(file: File | null | undefined): ValidationResult {
  if (!file) {
    return { ok: false, error: 'No file selected' };
  }
  if (!ALLOWED_MIME_TYPES.includes(file.type.toLowerCase())) {
    return { ok: false, error: 'Unsupported format. Use PNG, JPG, BMP, TIFF, or WEBP' };
  }
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return {
      ok: false,
      error: `File too large (${formatBytes(file.size)}). Maximum is ${formatBytes(MAX_FILE_SIZE_BYTES)}`,
    };
  }
  return { ok: true };
}

/**
 * Verify the decoded pixel dimensions are within safe bounds.
 *
 * Runs after the cheap type/size checks because it must decode the image.
 *
 * @param file The already type-validated image file.
 * @returns `{ ok: true }` when the bitmap decodes within `MAX_IMAGE_DIMENSION`.
 */
export async function validateImageDimensions(file: File): Promise<ValidationResult> {
  if (typeof createImageBitmap !== 'function') {
    return { ok: true };
  }
  try {
    const bitmap = await createImageBitmap(file);
    const { width, height } = bitmap;
    bitmap.close();
    if (width > MAX_IMAGE_DIMENSION || height > MAX_IMAGE_DIMENSION) {
      return {
        ok: false,
        error: `Image is too large (${width}x${height}px). Maximum is ${MAX_IMAGE_DIMENSION}x${MAX_IMAGE_DIMENSION}px`,
      };
    }
    return { ok: true };
  } catch {
    return { ok: false, error: 'This file could not be read as an image' };
  }
}
