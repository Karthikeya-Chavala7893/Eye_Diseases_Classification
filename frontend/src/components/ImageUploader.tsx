'use client';

/**
 * components/ImageUploader.tsx
 * ────────────────────────────
 * Drag-and-drop + file-picker uploader for retinal images.
 *
 * Accessibility (constraints #37 / #39): the drop zone is a real <button>, so it
 * is reachable by keyboard and activates with Enter/Space; the underlying
 * <input type="file"> remains the canonical control for assistive technology.
 */

import Image from 'next/image';
import { useCallback, useRef, useState, type DragEvent } from 'react';

import { ALLOWED_MIME_TYPES, MAX_FILE_SIZE_BYTES, formatBytes } from '@/lib/validation';

/**
 * Copy that differs between the two screening arms. Clinical mode demands a
 * fundus photograph and says so insistently; Home Mode wants an ordinary phone
 * photo and must make clear that it is entirely optional.
 */
const COPY = {
  clinical: {
    noticeIcon: '📷',
    noticeTitle: 'Requires a Retinal Fundus Photograph',
    title: 'Upload Retinal Image',
    subtitle: 'Drag and drop or click to browse',
    inputLabel: 'Choose a retinal image file',
    zoneLabel: 'Upload a retinal image: drag and drop here, or activate to browse',
    previewAlt: 'Uploaded retinal image preview',
    icon: '👁️',
  },
  home: {
    noticeIcon: '🤳',
    noticeTitle: 'Optional: add a photo of your eye',
    title: 'Add an Eye Photo',
    subtitle: 'Optional — drag and drop or click to browse',
    inputLabel: 'Choose a photo of your eye',
    zoneLabel: 'Add an optional photo of your eye: drag and drop here, or activate to browse',
    previewAlt: 'Uploaded eye photo preview',
    icon: '🤳',
  },
} as const;

interface ImageUploaderProps {
  /** Called with the chosen file once the user selects or drops one. */
  onSelect: (file: File) => void;
  /** Object URL of the current preview, or null while none is selected. */
  previewUrl: string | null;
  /** Clears the current selection. */
  onClear: () => void;
  /** Disables interaction while a request is in flight. */
  disabled?: boolean;
  /** Which screening arm this uploader is feeding; changes the copy only. */
  variant?: 'clinical' | 'home';
}

/**
 * Render the upload card: drop zone, file picker and preview.
 */
export function ImageUploader({
  onSelect,
  previewUrl,
  onClear,
  disabled = false,
  variant = 'clinical',
}: ImageUploaderProps): JSX.Element {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState<boolean>(false);
  const copy = COPY[variant];

  const openPicker = useCallback((): void => {
    if (!disabled) inputRef.current?.click();
  }, [disabled]);

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>): void => {
      event.preventDefault();
      setDragging(false);
      if (disabled) return;
      const file = event.dataTransfer.files[0];
      if (file) onSelect(file);
    },
    [disabled, onSelect],
  );

  const handleDragOver = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    if (!disabled) setDragging(true);
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    setDragging(false);
  };

  return (
    <div className="upload-card" id="uploadCard">
      {/* Fix C: Fundus image type requirement banner */}
      <div
        role="note"
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '0.75rem',
          padding: '0.75rem 1rem',
          background: 'linear-gradient(90deg, rgba(14,165,233,0.08), rgba(99,102,241,0.06))',
          border: '1px solid rgba(14,165,233,0.25)',
          borderRadius: 'var(--radius-lg)',
          marginBottom: '1rem',
          fontSize: '0.8rem',
          lineHeight: 1.5,
          color: 'var(--gray-600)',
        }}
      >
        <span style={{ fontSize: '1.1rem', flexShrink: 0 }} aria-hidden="true">{copy.noticeIcon}</span>
        <div>
          <strong style={{ color: 'var(--gray-800)', fontSize: '0.82rem' }}>
            {copy.noticeTitle}
          </strong>
          {variant === 'clinical' ? (
            <p style={{ margin: '0.15rem 0 0' }}>
              This AI is trained on <strong>fundus camera images</strong> of the back of the retina — a circular image
              showing blood vessels &amp; the optic disc. External eye photos or selfies will not produce accurate results.
            </p>
          ) : (
            <p style={{ margin: '0.15rem 0 0' }}>
              An ordinary, well-lit phone photo is fine. We check it only for two surface cues — how red the
              white of the eye looks, and whether the pupil appears cloudy. Your symptoms carry more weight than
              the photo, so you can skip this entirely.
            </p>
          )}
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        id="imageInput"
        className="file-input"
        accept={ALLOWED_MIME_TYPES.join(',')}
        aria-label={copy.inputLabel}
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onSelect(file);
          event.target.value = '';
        }}
      />

      {previewUrl ? (
        <div className="image-preview" id="imagePreview" style={{ display: 'flex' }}>
          <Image
            id="previewImg"
            src={previewUrl}
            alt={copy.previewAlt}
            width={400}
            height={400}
            unoptimized
            style={{ objectFit: 'contain', width: '100%', height: 'auto' }}
          />
          <button
            type="button"
            className="remove-btn"
            onClick={onClear}
            aria-label="Remove uploaded image"
          >
            ✕
          </button>
        </div>
      ) : (
        <div
          className={`upload-area${dragging ? ' dragover' : ''}`}
          id="uploadArea"
          role="button"
          tabIndex={disabled ? -1 : 0}
          aria-label={copy.zoneLabel}
          onClick={openPicker}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              openPicker();
            }
          }}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragEnter={handleDragOver}
          onDragLeave={handleDragLeave}
        >
          <div className="upload-content">
            <div className="upload-icon-container">
              <div className="upload-icon-bg" />
              <span className="upload-icon" aria-hidden="true">{copy.icon}</span>
            </div>
            <h3 className="upload-title">{copy.title}</h3>
            <p className="upload-subtitle">{copy.subtitle}</p>
            <p className="upload-formats">
              PNG, JPG, JPEG, BMP, TIFF, WEBP • Max {formatBytes(MAX_FILE_SIZE_BYTES)}
            </p>
            <button
              type="button"
              className="btn btn-primary"
              id="uploadBtn"
              onClick={(event) => {
                event.stopPropagation();
                openPicker();
              }}
              disabled={disabled}
            >
              <span aria-hidden="true">📁</span>
              <span>Choose File</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
