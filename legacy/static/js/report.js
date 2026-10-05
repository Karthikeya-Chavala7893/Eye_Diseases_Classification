/**
 * VisionAI — report.js
 * jsPDF report generation function.
 * Depends on: app.js (cap, darken), diseases.js (getDisease), jsPDF (CDN)
 * Loaded only on the /screening page.
 */

// ═══════════════════════════════════════════════════════════════════════════════
// PDF REPORT GENERATION
// ═══════════════════════════════════════════════════════════════════════════════

function downloadReport() {
    if (!State.result) return alert('No analysis to download');
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF('p', 'mm', 'a4');
    const W = 210, M = 15, CW = W - 2 * M;
    let y = 0;

    const topPred = State.result.predictions[0];
    const d = getDisease(topPred?.label);
    const allPreds = State.result.predictions;
    const now = new Date();

    // Color palette
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
        teal: [20, 184, 166]
    };
    const sevCol = d.severity === 'healthy' ? C.green : d.severity === 'warning' ? C.amber : C.red;

    function needPage(h) { if (y + h > 280) { doc.addPage(); y = 20; } }

    function drawSection(title, color) {
        needPage(16);
        doc.setFillColor(...color);
        doc.rect(M, y, 3, 10, 'F');
        doc.setTextColor(...C.dark);
        doc.setFontSize(12);
        doc.setFont('helvetica', 'bold');
        doc.text(title, M + 7, y + 7);
        doc.setDrawColor(226, 232, 240);
        doc.setLineWidth(0.3);
        doc.line(M + 7, y + 10, M + CW, y + 10);
        y += 15;
    }

    // ═══ PAGE HEADER ═══
    doc.setFillColor(...C.primary);
    doc.rect(0, 0, W, 32, 'F');
    doc.setFillColor(...C.teal);
    doc.rect(0, 32, W, 2, 'F');

    doc.setTextColor(...C.white);
    doc.setFontSize(20);
    doc.setFont('helvetica', 'bold');
    doc.text('VisionAI', M, 14);
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.text('Eye Health Screening Report', M, 21);

    const dateStr = now.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
    const timeStr = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    const reportId = 'VR-' + Date.now().toString(36).toUpperCase();
    doc.setFontSize(8);
    doc.text(dateStr + '  •  ' + timeStr, W - M, 12, { align: 'right' });
    doc.text('ID: ' + reportId, W - M, 18, { align: 'right' });

    y = 42;

    // ═══ PRIMARY FINDING ═══
    doc.setFillColor(...C.bg);
    doc.roundedRect(M, y, CW, 30, 3, 3, 'F');
    doc.setDrawColor(...sevCol);
    doc.setLineWidth(0.6);
    doc.line(M, y, M, y + 30);

    // Severity badge
    doc.setFillColor(...sevCol);
    doc.roundedRect(M + 5, y + 4, 18, 6, 2, 2, 'F');
    doc.setTextColor(...C.white);
    doc.setFontSize(6);
    doc.setFont('helvetica', 'bold');
    doc.text(cap(d.severity).toUpperCase(), M + 14, y + 8.5, { align: 'center' });

    // Disease name
    doc.setTextColor(...C.dark);
    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.text(d.name, M + 26, y + 9);

    // Match score
    doc.setTextColor(...C.text);
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.text('AI Match Score: ' + (topPred?.confidence || 0).toFixed(1) + '%', M + 5, y + 18);

    // Description
    doc.setFontSize(8);
    doc.setTextColor(...C.muted);
    const descLines = doc.splitTextToSize(d.desc, CW - 10);
    doc.text(descLines.slice(0, 2), M + 5, y + 24);

    y += 36;

    // ═══ ANALYSIS RESULTS TABLE ═══
    drawSection('Analysis Results', C.primary);

    // Column positions (fixed alignment)
    const col = { num: M + 3, name: M + 10, bar: M + 80, pct: M + 125, badge: M + 138 };

    // Table header
    doc.setFillColor(...C.primary);
    doc.roundedRect(M, y, CW, 8, 1.5, 1.5, 'F');
    doc.setTextColor(...C.white);
    doc.setFontSize(7);
    doc.setFont('helvetica', 'bold');
    doc.text('#', col.num, y + 5.5);
    doc.text('Condition', col.name, y + 5.5);
    doc.text('Match Score', col.bar, y + 5.5);
    doc.text('%', col.pct, y + 5.5);
    doc.text('Status', col.badge + 5, y + 5.5, { align: 'center' });
    y += 10;

    allPreds.forEach((p, i) => {
        needPage(9);
        const rd = getDisease(p.label);
        const sc = rd.severity === 'healthy' ? C.green : rd.severity === 'warning' ? C.amber : C.red;

        // Alternating row bg
        if (i % 2 === 0) {
            doc.setFillColor(248, 250, 252);
            doc.rect(M, y - 3, CW, 8, 'F');
        }

        // Row number
        doc.setTextColor(...C.muted);
        doc.setFontSize(8);
        doc.setFont('helvetica', 'normal');
        doc.text(String(i + 1), col.num, y + 2);

        // Condition name
        doc.setTextColor(...C.dark);
        doc.setFont('helvetica', 'bold');
        doc.text(rd.name.length > 28 ? rd.name.substring(0, 26) + '…' : rd.name, col.name, y + 2);

        // Progress bar background
        const barW = 42, barH = 3.5;
        doc.setFillColor(226, 232, 240);
        doc.roundedRect(col.bar, y - 0.5, barW, barH, 1, 1, 'F');

        // Progress bar fill
        doc.setFillColor(...sc);
        const fillW = Math.max(barW * (p.confidence / 100), 1.5);
        doc.roundedRect(col.bar, y - 0.5, fillW, barH, 1, 1, 'F');

        // Percentage text
        doc.setTextColor(...C.text);
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(8);
        doc.text(p.confidence.toFixed(1) + '%', col.pct, y + 2);

        // Status badge
        doc.setFillColor(...sc);
        doc.roundedRect(col.badge, y - 2, 22, 6, 2, 2, 'F');
        doc.setTextColor(...C.white);
        doc.setFontSize(5.5);
        doc.setFont('helvetica', 'bold');
        doc.text(cap(rd.severity).toUpperCase(), col.badge + 11, y + 1.5, { align: 'center' });

        y += 8;
    });
    y += 8;

    // ═══ DETAILED ANALYSIS ═══
    drawSection('Detailed Analysis', C.teal);
    doc.setTextColor(...C.text);
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    const infoLines = doc.splitTextToSize(d.info, CW - 6);
    needPage(infoLines.length * 4.5 + 4);
    doc.text(infoLines, M + 3, y);
    y += infoLines.length * 4.5 + 6;

    // ═══ RECOMMENDATIONS ═══
    if (d.recs && d.recs.length > 0) {
        drawSection('Recommendations', C.amber);
        d.recs.forEach((r, i) => {
            needPage(18);
            // Card background
            doc.setFillColor(255, 251, 235);
            doc.roundedRect(M, y - 2, CW, 15, 2, 2, 'F');

            // Number circle
            doc.setFillColor(...C.amber);
            doc.circle(M + 6, y + 3, 3, 'F');
            doc.setTextColor(...C.white);
            doc.setFontSize(7);
            doc.setFont('helvetica', 'bold');
            doc.text(String(i + 1), M + 6, y + 4.5, { align: 'center' });

            // Title
            doc.setTextColor(...C.dark);
            doc.setFontSize(10);
            doc.setFont('helvetica', 'bold');
            doc.text(r.title, M + 13, y + 4);

            // Description
            doc.setTextColor(...C.text);
            doc.setFontSize(8);
            doc.setFont('helvetica', 'normal');
            const recLines = doc.splitTextToSize(r.text, CW - 18);
            doc.text(recLines.slice(0, 1), M + 13, y + 10);

            y += 18;
        });
    }

    // ═══ DAILY HABITS ═══
    if (d.habits && d.habits.length > 0) {
        drawSection('Daily Habits', C.green);
        d.habits.forEach((h) => {
            needPage(14);
            doc.setFillColor(236, 253, 245);
            doc.roundedRect(M, y - 2, CW, 12, 2, 2, 'F');

            doc.setFillColor(...C.green);
            doc.circle(M + 5, y + 3, 1.5, 'F');

            doc.setTextColor(...C.dark);
            doc.setFontSize(9);
            doc.setFont('helvetica', 'bold');
            doc.text(h.title, M + 10, y + 3);

            doc.setTextColor(...C.muted);
            doc.setFontSize(7);
            doc.setFont('helvetica', 'normal');
            doc.text(h.freq, M + CW - 5, y + 3, { align: 'right' });

            doc.setTextColor(...C.text);
            doc.setFontSize(8);
            doc.text(h.desc, M + 10, y + 8);

            y += 14;
        });
    }

    // ═══ PREVENTION TIPS ═══
    if (d.prevent && d.prevent.length > 0) {
        drawSection('Prevention Tips', C.primary);
        d.prevent.forEach((p) => {
            needPage(12);
            doc.setTextColor(...C.primary);
            doc.setFontSize(9);
            doc.setFont('helvetica', 'bold');
            doc.text('▸', M + 3, y + 2);
            doc.setTextColor(...C.dark);
            doc.text(p.title, M + 9, y + 2);
            doc.setTextColor(...C.text);
            doc.setFontSize(8);
            doc.setFont('helvetica', 'normal');
            const tipLines = doc.splitTextToSize(p.text, CW - 12);
            doc.text(tipLines.slice(0, 1), M + 9, y + 7);
            y += 12;
        });
    }

    // ═══ MEDICAL DISCLAIMER ═══
    needPage(30);
    y += 5;
    doc.setFillColor(254, 243, 199);
    doc.roundedRect(M, y, CW, 24, 3, 3, 'F');
    doc.setDrawColor(...C.amber);
    doc.setLineWidth(0.4);
    doc.roundedRect(M, y, CW, 24, 3, 3, 'S');

    doc.setTextColor(146, 64, 14);
    doc.setFontSize(8);
    doc.setFont('helvetica', 'bold');
    doc.text('⚠  EDUCATIONAL DEMONSTRATION DISCLAIMER', M + CW / 2, y + 6, { align: 'center' });
    doc.setFontSize(7);
    doc.setFont('helvetica', 'normal');
    const disc = 'This screening tool is powered by an artificial intelligence model intended strictly for educational and research demonstration purposes. It does not provide medical advice, formal diagnosis, or treatment plans. Always consult a licensed ophthalmologist or healthcare provider for clinical evaluation. Do not disregard professional medical advice or delay seeking it because of results from this screening tool. For emergencies, contact your local emergency services immediately.';
    doc.text(doc.splitTextToSize(disc, CW - 14), M + 7, y + 12);

    // ═══ FOOTER ON EVERY PAGE ═══
    const totalPages = doc.internal.getNumberOfPages();
    for (let pg = 1; pg <= totalPages; pg++) {
        doc.setPage(pg);
        const pH = doc.internal.pageSize.height;
        doc.setFillColor(...C.primary);
        doc.rect(0, pH - 10, W, 10, 'F');
        doc.setTextColor(...C.white);
        doc.setFontSize(7);
        doc.setFont('helvetica', 'normal');
        doc.text('Powered by VisionAI Eye Hospital  |  AI-Powered Retinal Screening', W / 2, pH - 4, { align: 'center' });
        doc.text('Page ' + pg + ' of ' + totalPages, W - M, pH - 4, { align: 'right' });
    }

    doc.save('VisionAI_Report_' + now.toISOString().split('T')[0] + '.pdf');
}
