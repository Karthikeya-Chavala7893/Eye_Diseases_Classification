'use client';

/**
 * components/PdfReportButton.tsx
 * ──────────────────────────────
 * Triggers client-side PDF generation.
 *
 * jsPDF (~350 KB) is loaded with a dynamic import on first click, so it never
 * enters the initial bundle (constraint: code-split heavy libraries).
 */

import { useState } from 'react';

import type { PredictionResult } from '@/types/prediction';

interface PdfReportButtonProps {
  predictions: PredictionResult[];
  patientName: string;
  /** Surfaces a failure message to the page-level error UI. */
  onError?: (message: string) => void;
}

/**
 * Render the "Download Report" action.
 */
export function PdfReportButton({
  predictions,
  patientName,
  onError,
}: PdfReportButtonProps): JSX.Element {
  const [busy, setBusy] = useState<boolean>(false);

  const handleDownload = async (): Promise<void> => {
    setBusy(true);
    try {
      const { downloadReport } = await import('@/lib/pdf');
      downloadReport(predictions, patientName);
    } catch (cause) {
      onError?.(
        cause instanceof Error ? cause.message : 'Could not generate the PDF report.',
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      className="btn btn-primary"
      id="downloadReport"
      onClick={handleDownload}
      disabled={busy || predictions.length === 0}
      aria-label="Download the full screening report as a PDF"
    >
      <span aria-hidden="true">📄</span>
      <span>{busy ? 'Preparing…' : 'Download Report'}</span>
    </button>
  );
}
