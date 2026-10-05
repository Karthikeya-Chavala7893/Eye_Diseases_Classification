/**
 * lib/pdf.ts
 * ──────────
 * Client-side PDF screening report, ported from the legacy `static/js/report.js`.
 *
 * Privacy: the document is assembled entirely in browser memory and saved by the
 * browser. Nothing is transmitted to the backend or any third party.
 * The layout, colours, sections and disclaimer text match the original exactly.
 */

import { jsPDF } from 'jspdf';

import { getDisease } from '@/lib/diseases';
import type { PredictionResult, Severity } from '@/types/prediction';

/** RGB triple used by jsPDF's colour setters. */
type Rgb = readonly [number, number, number];

/** Report palette — identical to the legacy generator. */
const C = {
  primary: [14, 165, 233],
  dark: [15, 23, 42],
  text: [71, 85, 105],
  muted: [148, 163, 184],
  bg: [248, 250, 252],
  white: [255, 255, 255],
  green: [16, 185, 129],
  amber: [245, 158, 11],
  red: [239, 68, 68],
  teal: [20, 184, 166],
} satisfies Record<string, Rgb>;

/** A4 page width in millimetres. */
const PAGE_WIDTH = 210;
/** Page margin in millimetres. */
const MARGIN = 15;
/** Usable content width. */
const CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN;
/** Vertical cursor position that forces a page break. */
const PAGE_BREAK_Y = 280;

const DISCLAIMER =
  'This screening tool is powered by an artificial intelligence model intended strictly for ' +
  'educational and research demonstration purposes. It does not provide medical advice, formal ' +
  'diagnosis, or treatment plans. Always consult a licensed ophthalmologist or healthcare provider ' +
  'for clinical evaluation. Do not disregard professional medical advice or delay seeking it because ' +
  'of results from this screening tool. For emergencies, contact your local emergency services immediately.';

/** Capitalise the first character of a string. */
function cap(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

/** Map a severity band to its report colour. */
function severityColor(severity: Severity): Rgb {
  if (severity === 'healthy') return C.green;
  if (severity === 'warning') return C.amber;
  return C.red;
}

/**
 * Generate a report identifier.
 *
 * @returns An ID of the form `VR-` plus base-36 uppercase characters.
 */
export function makeReportId(): string {
  return `VR-${Date.now().toString(36).toUpperCase()}`;
}

/**
 * Build and download the full screening report.
 *
 * @param predictions Sorted prediction list from `/api/predict`.
 * @param patientName Display name shown on the report.
 * @returns The generated report ID, so the caller can surface it in the UI.
 * @throws Error when `predictions` is empty.
 */
export function downloadReport(predictions: PredictionResult[], patientName: string): string {
  if (predictions.length === 0) {
    throw new Error('No analysis results to export');
  }

  const doc = new jsPDF('p', 'mm', 'a4');
  let y = 0;

  const topPrediction = predictions[0];
  const disease = getDisease(topPrediction.label);
  const now = new Date();
  const sevCol = severityColor(disease.severity);

  /** Start a new page when the next block would overflow. */
  const needPage = (height: number): void => {
    if (y + height > PAGE_BREAK_Y) {
      doc.addPage();
      y = 20;
    }
  };

  /** Draw a section heading with a coloured rule. */
  const drawSection = (title: string, color: Rgb): void => {
    needPage(16);
    doc.setFillColor(...color);
    doc.rect(MARGIN, y, 3, 10, 'F');
    doc.setTextColor(...C.dark);
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.text(title, MARGIN + 7, y + 7);
    doc.setDrawColor(226, 232, 240);
    doc.setLineWidth(0.3);
    doc.line(MARGIN + 7, y + 10, MARGIN + CONTENT_WIDTH, y + 10);
    y += 15;
  };

  // ═══ PAGE HEADER ═══
  doc.setFillColor(...C.primary);
  doc.rect(0, 0, PAGE_WIDTH, 32, 'F');
  doc.setFillColor(...C.teal);
  doc.rect(0, 32, PAGE_WIDTH, 2, 'F');

  doc.setTextColor(...C.white);
  doc.setFontSize(20);
  doc.setFont('helvetica', 'bold');
  doc.text('VisionAI', MARGIN, 14);
  doc.setFontSize(9);
  doc.setFont('helvetica', 'normal');
  doc.text('Eye Health Screening Report', MARGIN, 21);

  const dateStr = now.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  const timeStr = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  const reportId = makeReportId();
  doc.setFontSize(8);
  doc.text(`${dateStr}  •  ${timeStr}`, PAGE_WIDTH - MARGIN, 12, { align: 'right' });
  doc.text(`ID: ${reportId}`, PAGE_WIDTH - MARGIN, 18, { align: 'right' });

  y = 42;

  // ═══ PATIENT + PRIMARY FINDING ═══
  doc.setFillColor(...C.bg);
  doc.roundedRect(MARGIN, y, CONTENT_WIDTH, 36, 3, 3, 'F');
  doc.setDrawColor(...sevCol);
  doc.setLineWidth(0.6);
  doc.line(MARGIN, y, MARGIN, y + 36);

  doc.setFillColor(...sevCol);
  doc.roundedRect(MARGIN + 5, y + 4, 18, 6, 2, 2, 'F');
  doc.setTextColor(...C.white);
  doc.setFontSize(6);
  doc.setFont('helvetica', 'bold');
  doc.text(cap(disease.severity).toUpperCase(), MARGIN + 14, y + 8.5, { align: 'center' });

  doc.setTextColor(...C.dark);
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text(disease.name, MARGIN + 26, y + 9);

  doc.setTextColor(...C.text);
  doc.setFontSize(9);
  doc.setFont('helvetica', 'normal');
  doc.text(`Patient: ${patientName}`, MARGIN + 5, y + 17);
  doc.text(`AI Confidence: ${topPrediction.confidence.toFixed(1)}%`, MARGIN + 5, y + 23);

  doc.setFontSize(8);
  doc.setTextColor(...C.muted);
  doc.text(doc.splitTextToSize(disease.desc, CONTENT_WIDTH - 10).slice(0, 2), MARGIN + 5, y + 29);

  y += 42;

  // ═══ ANALYSIS RESULTS TABLE ═══
  drawSection('Analysis Results', C.primary);

  const col = {
    num: MARGIN + 3,
    name: MARGIN + 10,
    bar: MARGIN + 80,
    pct: MARGIN + 125,
    badge: MARGIN + 138,
  };

  doc.setFillColor(...C.primary);
  doc.roundedRect(MARGIN, y, CONTENT_WIDTH, 8, 1.5, 1.5, 'F');
  doc.setTextColor(...C.white);
  doc.setFontSize(7);
  doc.setFont('helvetica', 'bold');
  doc.text('#', col.num, y + 5.5);
  doc.text('Condition', col.name, y + 5.5);
  doc.text('AI Confidence', col.bar, y + 5.5);
  doc.text('%', col.pct, y + 5.5);
  doc.text('Status', col.badge + 5, y + 5.5, { align: 'center' });
  y += 10;

  predictions.forEach((prediction, index) => {
    needPage(9);
    const rowDisease = getDisease(prediction.label);
    const rowColor = severityColor(rowDisease.severity);

    if (index % 2 === 0) {
      doc.setFillColor(248, 250, 252);
      doc.rect(MARGIN, y - 3, CONTENT_WIDTH, 8, 'F');
    }

    doc.setTextColor(...C.muted);
    doc.setFontSize(8);
    doc.setFont('helvetica', 'normal');
    doc.text(String(index + 1), col.num, y + 2);

    doc.setTextColor(...C.dark);
    doc.setFont('helvetica', 'bold');
    const label =
      rowDisease.name.length > 28 ? `${rowDisease.name.substring(0, 26)}…` : rowDisease.name;
    doc.text(label, col.name, y + 2);

    const barW = 42;
    const barH = 3.5;
    doc.setFillColor(226, 232, 240);
    doc.roundedRect(col.bar, y - 0.5, barW, barH, 1, 1, 'F');

    doc.setFillColor(...rowColor);
    doc.roundedRect(col.bar, y - 0.5, Math.max(barW * (prediction.confidence / 100), 1.5), barH, 1, 1, 'F');

    doc.setTextColor(...C.text);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.text(`${prediction.confidence.toFixed(1)}%`, col.pct, y + 2);

    doc.setFillColor(...rowColor);
    doc.roundedRect(col.badge, y - 2, 22, 6, 2, 2, 'F');
    doc.setTextColor(...C.white);
    doc.setFontSize(5.5);
    doc.setFont('helvetica', 'bold');
    doc.text(cap(rowDisease.severity).toUpperCase(), col.badge + 11, y + 1.5, { align: 'center' });

    y += 8;
  });
  y += 8;

  // ═══ DETAILED ANALYSIS ═══
  drawSection('Detailed Analysis', C.teal);
  doc.setTextColor(...C.text);
  doc.setFontSize(9);
  doc.setFont('helvetica', 'normal');
  const infoLines = doc.splitTextToSize(disease.info, CONTENT_WIDTH - 6) as string[];
  needPage(infoLines.length * 4.5 + 4);
  doc.text(infoLines, MARGIN + 3, y);
  y += infoLines.length * 4.5 + 6;

  // ═══ RECOMMENDATIONS ═══
  if (disease.recs.length > 0) {
    drawSection('Recommendations', C.amber);
    disease.recs.forEach((rec, index) => {
      needPage(18);
      doc.setFillColor(255, 251, 235);
      doc.roundedRect(MARGIN, y - 2, CONTENT_WIDTH, 15, 2, 2, 'F');

      doc.setFillColor(...C.amber);
      doc.circle(MARGIN + 6, y + 3, 3, 'F');
      doc.setTextColor(...C.white);
      doc.setFontSize(7);
      doc.setFont('helvetica', 'bold');
      doc.text(String(index + 1), MARGIN + 6, y + 4.5, { align: 'center' });

      doc.setTextColor(...C.dark);
      doc.setFontSize(10);
      doc.setFont('helvetica', 'bold');
      doc.text(rec.title, MARGIN + 13, y + 4);

      doc.setTextColor(...C.text);
      doc.setFontSize(8);
      doc.setFont('helvetica', 'normal');
      doc.text(doc.splitTextToSize(rec.text, CONTENT_WIDTH - 18).slice(0, 1), MARGIN + 13, y + 10);

      y += 18;
    });
  }

  // ═══ DAILY HABITS ═══
  if (disease.habits.length > 0) {
    drawSection('Daily Habits', C.green);
    disease.habits.forEach((habit) => {
      needPage(14);
      doc.setFillColor(236, 253, 245);
      doc.roundedRect(MARGIN, y - 2, CONTENT_WIDTH, 12, 2, 2, 'F');

      doc.setFillColor(...C.green);
      doc.circle(MARGIN + 5, y + 3, 1.5, 'F');

      doc.setTextColor(...C.dark);
      doc.setFontSize(9);
      doc.setFont('helvetica', 'bold');
      doc.text(habit.title, MARGIN + 10, y + 3);

      doc.setTextColor(...C.muted);
      doc.setFontSize(7);
      doc.setFont('helvetica', 'normal');
      doc.text(habit.freq, MARGIN + CONTENT_WIDTH - 5, y + 3, { align: 'right' });

      doc.setTextColor(...C.text);
      doc.setFontSize(8);
      doc.text(habit.desc, MARGIN + 10, y + 8);

      y += 14;
    });
  }

  // ═══ PREVENTION TIPS ═══
  if (disease.prevent.length > 0) {
    drawSection('Prevention Tips', C.primary);
    disease.prevent.forEach((tip) => {
      needPage(12);
      doc.setTextColor(...C.primary);
      doc.setFontSize(9);
      doc.setFont('helvetica', 'bold');
      doc.text('▸', MARGIN + 3, y + 2);
      doc.setTextColor(...C.dark);
      doc.text(tip.title, MARGIN + 9, y + 2);
      doc.setTextColor(...C.text);
      doc.setFontSize(8);
      doc.setFont('helvetica', 'normal');
      doc.text(doc.splitTextToSize(tip.text, CONTENT_WIDTH - 12).slice(0, 1), MARGIN + 9, y + 7);
      y += 12;
    });
  }

  // ═══ MEDICAL DISCLAIMER ═══
  needPage(30);
  y += 5;
  doc.setFillColor(254, 243, 199);
  doc.roundedRect(MARGIN, y, CONTENT_WIDTH, 24, 3, 3, 'F');
  doc.setDrawColor(...C.amber);
  doc.setLineWidth(0.4);
  doc.roundedRect(MARGIN, y, CONTENT_WIDTH, 24, 3, 3, 'S');

  doc.setTextColor(146, 64, 14);
  doc.setFontSize(8);
  doc.setFont('helvetica', 'bold');
  doc.text('EDUCATIONAL DEMONSTRATION DISCLAIMER', MARGIN + CONTENT_WIDTH / 2, y + 6, {
    align: 'center',
  });
  doc.setFontSize(7);
  doc.setFont('helvetica', 'normal');
  doc.text(doc.splitTextToSize(DISCLAIMER, CONTENT_WIDTH - 14), MARGIN + 7, y + 12);

  // ═══ FOOTER ON EVERY PAGE ═══
  const totalPages = doc.internal.pages.length - 1;
  for (let page = 1; page <= totalPages; page += 1) {
    doc.setPage(page);
    const pageHeight = doc.internal.pageSize.height;
    doc.setFillColor(...C.primary);
    doc.rect(0, pageHeight - 10, PAGE_WIDTH, 10, 'F');
    doc.setTextColor(...C.white);
    doc.setFontSize(7);
    doc.setFont('helvetica', 'normal');
    doc.text(
      'Powered by VisionAI Eye Hospital  |  AI-Powered Retinal Screening',
      PAGE_WIDTH / 2,
      pageHeight - 4,
      { align: 'center' },
    );
    doc.text(`Page ${page} of ${totalPages}`, PAGE_WIDTH - MARGIN, pageHeight - 4, {
      align: 'right',
    });
  }

  doc.save(`VisionAI_Report_${now.toISOString().split('T')[0]}.pdf`);
  return reportId;
}
