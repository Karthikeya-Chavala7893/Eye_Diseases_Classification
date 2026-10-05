"""
Generate VisionAI Research Summary PDF
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.platypus import PageBreak
from reportlab.lib.colors import HexColor

OUTPUT_PATH = r"C:\Users\chkar\Desktop\Eye_Diseases_Classification\VisionAI_Research_Summary.pdf"

# ── Colour Palette ────────────────────────────────────────────────────────────
NAVY       = HexColor('#1A237E')
BLUE       = HexColor('#1565C0')
LIGHT_BLUE = HexColor('#E3F2FD')
TEAL       = HexColor('#00796B')
TEAL_LIGHT = HexColor('#E0F2F1')
GOLD       = HexColor('#F57F17')
GOLD_LIGHT = HexColor('#FFF9C4')
RED        = HexColor('#C62828')
RED_LIGHT  = HexColor('#FFEBEE')
GREY       = HexColor('#F5F5F5')
MID_GREY   = HexColor('#9E9E9E')
DARK_GREY  = HexColor('#424242')
WHITE      = colors.white
BLACK      = colors.black

doc = SimpleDocTemplate(
    OUTPUT_PATH,
    pagesize=A4,
    rightMargin=1.8*cm, leftMargin=1.8*cm,
    topMargin=1.5*cm, bottomMargin=1.5*cm,
)

W = A4[0] - 3.6*cm   # usable width

# ── Styles ────────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

def S(name, **kw):
    return ParagraphStyle(name, **kw)

cover_title = S('CoverTitle',
    fontSize=26, textColor=WHITE, fontName='Helvetica-Bold',
    alignment=TA_CENTER, leading=32, spaceAfter=6)

cover_sub = S('CoverSub',
    fontSize=13, textColor=HexColor('#BBDEFB'), fontName='Helvetica',
    alignment=TA_CENTER, leading=18)

cover_author = S('CoverAuthor',
    fontSize=11, textColor=HexColor('#E3F2FD'), fontName='Helvetica-Oblique',
    alignment=TA_CENTER, leading=16)

sec_heading = S('SecHead',
    fontSize=14, textColor=WHITE, fontName='Helvetica-Bold',
    alignment=TA_LEFT, leading=18, spaceBefore=14, spaceAfter=4)

body = S('Body',
    fontSize=10, textColor=DARK_GREY, fontName='Helvetica',
    alignment=TA_JUSTIFY, leading=15, spaceAfter=5)

body_bold = S('BodyBold',
    fontSize=10, textColor=DARK_GREY, fontName='Helvetica-Bold',
    alignment=TA_LEFT, leading=14, spaceAfter=3)

bullet = S('Bullet',
    fontSize=10, textColor=DARK_GREY, fontName='Helvetica',
    alignment=TA_LEFT, leading=14, leftIndent=14,
    firstLineIndent=-10, spaceAfter=3)

small_note = S('SmallNote',
    fontSize=8, textColor=MID_GREY, fontName='Helvetica-Oblique',
    alignment=TA_CENTER, leading=11)

metric_val = S('MetricVal',
    fontSize=22, textColor=TEAL, fontName='Helvetica-Bold',
    alignment=TA_CENTER, leading=26)

metric_label = S('MetricLabel',
    fontSize=9, textColor=MID_GREY, fontName='Helvetica',
    alignment=TA_CENTER, leading=12)

story = []

# ════════════════════════════════════════════════════════════════════════════
# COVER PAGE
# ════════════════════════════════════════════════════════════════════════════
cover_bg = Table(
    [[Paragraph('VisionAI', cover_title)],
     [Spacer(1, 6)],
     [Paragraph('Eye Disease Classification System', cover_sub)],
     [Spacer(1, 4)],
     [Paragraph('Clinical Ensemble CNN Model — Research Summary', cover_sub)],
     [Spacer(1, 18)],
     [HRFlowable(width=W*0.6, color=HexColor('#64B5F6'), thickness=1.5)],
     [Spacer(1, 18)],
     [Paragraph('Prepared by: Karthikeya Chavala', cover_author)],
     [Paragraph('Domain: AI-Powered Tele-Ophthalmology', cover_author)],
     [Spacer(1, 6)],
     [Paragraph('October 2026', cover_author)],
    ],
    colWidths=[W],
)
cover_bg.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), NAVY),
    ('TOPPADDING',    (0,0), (-1,-1), 6),
    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ('LEFTPADDING',   (0,0), (-1,-1), 20),
    ('RIGHTPADDING',  (0,0), (-1,-1), 20),
    ('ROUNDEDCORNERS', [8]),
]))
story.append(Spacer(1, 1.2*cm))
story.append(cover_bg)
story.append(Spacer(1, 0.7*cm))

# Tagline box
tagline = Table([[Paragraph(
    '"Achieving 95.42% clinical accuracy through a 3-model CNN ensemble '
    'with advanced training optimizations — outperforming the previous '
    'single-model baseline by <b>+2.65%</b>."',
    S('TL', fontSize=11, textColor=BLUE, fontName='Helvetica-Oblique',
      alignment=TA_CENTER, leading=16)
)]], colWidths=[W])
tagline.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), LIGHT_BLUE),
    ('BOX', (0,0), (-1,-1), 1, BLUE),
    ('TOPPADDING', (0,0), (-1,-1), 10),
    ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ('LEFTPADDING', (0,0), (-1,-1), 16),
    ('RIGHTPADDING', (0,0), (-1,-1), 16),
]))
story.append(tagline)
story.append(PageBreak())


# ── Helper: section header ────────────────────────────────────────────────────
def section_header(title, icon=''):
    t = Table([[Paragraph(f'{icon}  {title}', sec_heading)]], colWidths=[W])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), NAVY),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ('ROUNDEDCORNERS', [4]),
    ]))
    return t

def metric_box(value, label, color=TEAL, bg=TEAL_LIGHT):
    t = Table([
        [Paragraph(value, S('MV', fontSize=20, textColor=color,
                             fontName='Helvetica-Bold', alignment=TA_CENTER, leading=24))],
        [Paragraph(label, S('ML', fontSize=8, textColor=MID_GREY,
                             fontName='Helvetica', alignment=TA_CENTER, leading=11))],
    ], colWidths=[(W-1*cm)/3])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg),
        ('BOX', (0,0), (-1,-1), 1, color),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ROUNDEDCORNERS', [6]),
    ]))
    return t

# ════════════════════════════════════════════════════════════════════════════
# SECTION 1 — MODELS USED
# ════════════════════════════════════════════════════════════════════════════
story.append(section_header('1. Models Used for Screening', ''))
story.append(Spacer(1, 8))

# Clinical model table
story.append(Paragraph('<b>Clinical Screening — Ensemble CNN Classifier</b>', body_bold))
story.append(Spacer(1, 4))

clinical_data = [
    ['Sub-Model', 'Parameters', 'Input Size', 'Role'],
    ['EfficientNetB3', '~12 Million', '300 × 300 px', 'Best single-model accuracy;\nefficient feature scaling'],
    ['DenseNet121', '~8 Million', '224 × 224 px', 'Dense feature reuse;\ncomplementary to EfficientNet'],
    ['InceptionResNetV2', '~55 Million', '299 × 299 px', 'Deepest feature extraction;\ncaptures complex patterns'],
    ['Ensemble (Soft Vote)', '~75 Million total', '3 resolutions', 'Averages all 3 model outputs\nfor final prediction'],
]

ct = Table(clinical_data, colWidths=[W*0.22, W*0.18, W*0.18, W*0.42])
ct.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), BLUE),
    ('TEXTCOLOR', (0,0), (-1,0), WHITE),
    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ('FONTSIZE', (0,0), (-1,0), 9),
    ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
    ('FONTSIZE', (0,1), (-1,-1), 9),
    ('BACKGROUND', (0,1), (-1,1), GREY),
    ('BACKGROUND', (0,2), (-1,2), WHITE),
    ('BACKGROUND', (0,3), (-1,3), GREY),
    ('BACKGROUND', (0,4), (-1,4), TEAL_LIGHT),
    ('FONTNAME', (0,4), (0,4), 'Helvetica-Bold'),
    ('TEXTCOLOR', (0,4), (0,4), TEAL),
    ('GRID', (0,0), (-1,-1), 0.5, HexColor('#BDBDBD')),
    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('TOPPADDING', (0,0), (-1,-1), 6),
    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ('LEFTPADDING', (0,0), (-1,-1), 6),
    ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ('ALIGN', (3,1), (3,-1), 'LEFT'),
]))
story.append(ct)
story.append(Spacer(1, 12))

# Home model
story.append(Paragraph('<b>Home Screening — NeuronZero / EyeDiseaseClassifier</b>', body_bold))
story.append(Spacer(1, 4))

home_data = [
    ['Aspect', 'Details'],
    ['Architecture', 'BEiT (BERT Image Transformer) — HuggingFace AutoModel'],
    ['Purpose', 'Fast home self-check using a smartphone camera photo + 25-symptom checklist'],
    ['Input', 'External eye photos (not fundus/retinal scans)'],
    ['Backend', 'Rule-based triage engine (triage.py) + BEiT image classifier'],
    ['When used', 'Daily Home Eye Check mode — no hospital equipment needed'],
]
ht = Table(home_data, colWidths=[W*0.25, W*0.75])
ht.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), GOLD),
    ('TEXTCOLOR', (0,0), (-1,0), WHITE),
    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ('FONTSIZE', (0,0), (-1,0), 9),
    ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
    ('FONTSIZE', (0,1), (-1,-1), 9),
    ('BACKGROUND', (0,1), (0,-1), GOLD_LIGHT),
    ('FONTNAME', (0,1), (0,-1), 'Helvetica-Bold'),
    ('GRID', (0,0), (-1,-1), 0.5, HexColor('#BDBDBD')),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('TOPPADDING', (0,0), (-1,-1), 6),
    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ('LEFTPADDING', (0,0), (-1,-1), 6),
    ('RIGHTPADDING', (0,0), (-1,-1), 6),
]))
story.append(ht)
story.append(Spacer(1, 16))

# ════════════════════════════════════════════════════════════════════════════
# SECTION 2 — ACCURACY & TECHNIQUES
# ════════════════════════════════════════════════════════════════════════════
story.append(section_header('2. Clinical Screening Accuracy & Techniques', ''))
story.append(Spacer(1, 10))

# Metric boxes
m1 = metric_box('95.42%', 'Ensemble Test Accuracy', TEAL, TEAL_LIGHT)
m2 = metric_box('95.35%', 'Macro F1 Score', BLUE, LIGHT_BLUE)
m3 = metric_box('53.3 min', 'Total Training Time', GOLD, GOLD_LIGHT)
metrics_row = Table([[m1, Spacer(0.5*cm,1), m2, Spacer(0.5*cm,1), m3]],
                    colWidths=[(W-1*cm)/3, 0.5*cm, (W-1*cm)/3, 0.5*cm, (W-1*cm)/3])
metrics_row.setStyle(TableStyle([
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ('TOPPADDING', (0,0), (-1,-1), 0),
    ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ('LEFTPADDING', (0,0), (-1,-1), 0),
    ('RIGHTPADDING', (0,0), (-1,-1), 0),
]))
story.append(metrics_row)
story.append(Spacer(1, 12))

# Per-class performance
story.append(Paragraph('<b>Per-Class Performance:</b>', body_bold))
story.append(Spacer(1, 4))

perf_data = [
    ['Disease Class', 'Precision', 'Recall', 'F1-Score', 'Support'],
    ['Normal', '92.45%', '91.30%', '91.87%', '161 images'],
    ['Diabetic Retinopathy', '99.40%', '100.00%', '99.70%', '165 images'],
    ['Glaucoma', '92.11%', '92.72%', '92.41%', '151 images'],
    ['Cataract', '97.44%', '97.44%', '97.44%', '156 images'],
    ['Weighted Average', '95.41%', '95.42%', '95.41%', '633 images'],
]
pt = Table(perf_data, colWidths=[W*0.30, W*0.16, W*0.16, W*0.16, W*0.22])
pt.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), TEAL),
    ('TEXTCOLOR', (0,0), (-1,0), WHITE),
    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ('FONTSIZE', (0,0), (-1,-1), 9),
    ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
    ('BACKGROUND', (0,5), (-1,5), TEAL_LIGHT),
    ('FONTNAME', (0,5), (-1,5), 'Helvetica-Bold'),
    ('ROWBACKGROUNDS', (0,1), (-1,4), [WHITE, GREY]),
    ('GRID', (0,0), (-1,-1), 0.5, HexColor('#BDBDBD')),
    ('ALIGN', (1,0), (-1,-1), 'CENTER'),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('TOPPADDING', (0,0), (-1,-1), 6),
    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ('LEFTPADDING', (0,0), (-1,-1), 6),
]))
story.append(pt)
story.append(Spacer(1, 12))

# Techniques
story.append(Paragraph('<b>Optimization Techniques Used:</b>', body_bold))
story.append(Spacer(1, 4))

techniques = [
    ['#', 'Technique', 'What it Does'],
    ['1', 'Soft-Voting Ensemble', 'Averages probabilities from 3 different CNN models — reduces individual model errors'],
    ['2', 'Albumentations Augmentation', 'CLAHE, elastic distortion, random flips, colour jitter — creates more diverse training data'],
    ['3', 'Cosine Annealing LR + Warmup', 'Learning rate starts low, peaks at epoch 3, then gradually decreases — avoids overfitting'],
    ['4', 'Label Smoothing (0.1)', 'Prevents the model from being overconfident — improves generalisation'],
    ['5', 'Weighted Random Sampling', 'Balances class frequencies in each batch — prevents bias toward majority class'],
    ['6', 'Gradient Clipping (max=1.0)', 'Prevents exploding gradients — keeps training stable'],
    ['7', 'Early Stopping on F1', 'Stops training when F1 stops improving — prevents overfitting'],
    ['8', '5-View TTA at Inference', 'Test-Time Augmentation: averages 5 flipped/rotated views — boosts final accuracy'],
    ['9', 'Mixed Precision (AMP)', 'Uses float16 during training — 2x faster, less GPU memory'],
    ['10', 'AdamW Optimizer', 'Decoupled weight decay — better regularization than standard Adam'],
]
tt = Table(techniques, colWidths=[W*0.05, W*0.30, W*0.65])
tt.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), BLUE),
    ('TEXTCOLOR', (0,0), (-1,0), WHITE),
    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ('FONTSIZE', (0,0), (-1,-1), 9),
    ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
    ('FONTNAME', (1,1), (1,-1), 'Helvetica-Bold'),
    ('TEXTCOLOR', (1,1), (1,-1), BLUE),
    ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LIGHT_BLUE]),
    ('GRID', (0,0), (-1,-1), 0.5, HexColor('#BDBDBD')),
    ('ALIGN', (0,0), (0,-1), 'CENTER'),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('TOPPADDING', (0,0), (-1,-1), 5),
    ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ('LEFTPADDING', (0,0), (-1,-1), 6),
    ('RIGHTPADDING', (0,0), (-1,-1), 6),
]))
story.append(tt)
story.append(PageBreak())

# ════════════════════════════════════════════════════════════════════════════
# SECTION 3 — PREDICTION PARAMETERS PER DISEASE
# ════════════════════════════════════════════════════════════════════════════
story.append(section_header('3. Parameters the Model Uses to Predict Each Disease', ''))
story.append(Spacer(1, 8))

story.append(Paragraph(
    'The ensemble CNN models learn visual features from retinal fundus photographs. '
    'Each disease produces characteristic changes on the retina that the model identifies through '
    'convolutional feature maps at multiple scales.',
    body))
story.append(Spacer(1, 8))

diseases = [
    {
        'name': 'Normal (Healthy Retina)',
        'color': TEAL,
        'bg': TEAL_LIGHT,
        'params': [
            'Clear, uniform retinal background with no lesions',
            'Sharp, well-defined optic disc with distinct margins',
            'Normal cup-to-disc ratio (< 0.4)',
            'No microaneurysms, haemorrhages, or exudates',
            'Regular blood vessel calibre and branching pattern',
        ]
    },
    {
        'name': 'Diabetic Retinopathy',
        'color': RED,
        'bg': RED_LIGHT,
        'params': [
            'Microaneurysms — tiny red dots scattered across the retina',
            'Haemorrhages — flame-shaped or blot bleeding patterns',
            'Hard exudates — yellow-white lipid deposits',
            'Cotton-wool spots — fluffy white patches (nerve fibre infarcts)',
            'Neovascularisation — abnormal new blood vessels (advanced stage)',
        ]
    },
    {
        'name': 'Glaucoma',
        'color': BLUE,
        'bg': LIGHT_BLUE,
        'params': [
            'Enlarged cup-to-disc ratio (> 0.6) — optic cup is abnormally large',
            'Optic disc pallor — reduced pink colour of the disc',
            'Notching of the neuroretinal rim — loss at inferior/superior poles',
            'Bayoneting of blood vessels at disc margin',
            'Asymmetric disc appearance between left and right eye',
        ]
    },
    {
        'name': 'Cataract',
        'color': GOLD,
        'bg': GOLD_LIGHT,
        'params': [
            'Hazy, reduced overall image clarity and brightness',
            'Diffuse whitish or yellowish scatter in the lens region',
            'Loss of contrast and sharpness in fundus details',
            'Reduced visibility of fine blood vessel structures',
            'Altered colour balance — image appears washed out or brownish',
        ]
    },
]

for d in diseases:
    rows = [[
        Paragraph(f"<b>{d['name']}</b>",
                  S('DH', fontSize=10, textColor=d['color'],
                    fontName='Helvetica-Bold', alignment=TA_LEFT, leading=14)),
    ]]
    for p in d['params']:
        rows.append([
            Paragraph(f"<bullet>&bull;</bullet> {p}",
                      S('DP', fontSize=9, textColor=DARK_GREY, fontName='Helvetica',
                        leftIndent=10, leading=13, alignment=TA_LEFT))
        ])
    dt = Table(rows, colWidths=[W])
    dt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), d['bg']),
        ('BACKGROUND', (0,1), (-1,-1), WHITE),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (0,0), 8),
        ('BOTTOMPADDING', (0,0), (0,0), 8),
        ('TOPPADDING', (0,1), (-1,-1), 3),
        ('BOTTOMPADDING', (0,1), (-1,-1), 3),
        ('BOX', (0,0), (-1,-1), 1, d['color']),
        ('LINEBELOW', (0,0), (-1,0), 1, d['color']),
    ]))
    story.append(dt)
    story.append(Spacer(1, 8))

story.append(Spacer(1, 4))
story.append(Paragraph(
    'Note: The models do not use any hand-crafted rules. They automatically learn these '
    'visual patterns through backpropagation on 4,217 labelled clinical fundus images.',
    small_note))
story.append(PageBreak())

# ════════════════════════════════════════════════════════════════════════════
# SECTION 4 — PREVIOUS VS NOW COMPARISON
# ════════════════════════════════════════════════════════════════════════════
story.append(section_header('4. Previous vs Current Clinical Screening (Key Changes)', ''))
story.append(Spacer(1, 8))

comp_data = [
    ['Aspect', 'Previous (RETFound ViT)', 'Current (CNN Ensemble)'],
    ['Architecture', 'Single model: RETFound ViT-Large/16\n(Vision Transformer)',
                     '3-model ensemble: EfficientNetB3 +\nDenseNet121 + InceptionResNetV2'],
    ['Parameters', '307 Million (ViT-Large backbone)', '~75 Million total across 3 models'],
    ['Checkpoint Size', '1.2 GB', '276 MB'],
    ['Test Accuracy', '91.62% – 92.77%', '95.42%'],
    ['Macro F1 Score', '~91–92%', '95.35%'],
    ['Training Data', 'ODIR-5K / gunavenkatdoddi\ndataset', 'gunavenkatdoddi dataset\n(same, better preprocessing)'],
    ['Augmentation', 'Basic flips and resize only', 'CLAHE, elastic distortion,\ncolour jitter, coarse dropout'],
    ['Class Balancing', 'None', 'Weighted Random Sampler\n+ class-weighted loss'],
    ['LR Schedule', 'Fixed or stepped LR', 'Cosine annealing with\n3-epoch warmup'],
    ['Inference', 'Single model, single pass', 'Soft voting across 3 models\n+ 5-view TTA'],
    ['Load Time', '~60–90 seconds (1.2 GB)', '~25–40 seconds (276 MB)'],
    ['Overfitting Risk', 'High (307M params, ~4K images)', 'Low (smaller models, strong regularisation)'],
]

prev_col = W * 0.32
cur_col  = W * 0.34
asp_col  = W * 0.34
comp_table = Table(comp_data, colWidths=[asp_col, prev_col, cur_col])
comp_table.setStyle(TableStyle([
    # Header row
    ('BACKGROUND', (0,0), (-1,0), NAVY),
    ('TEXTCOLOR', (0,0), (-1,0), WHITE),
    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ('FONTSIZE', (0,0), (-1,0), 10),
    # Aspect column
    ('FONTNAME', (0,1), (0,-1), 'Helvetica-Bold'),
    ('TEXTCOLOR', (0,1), (0,-1), DARK_GREY),
    ('BACKGROUND', (0,1), (0,-1), GREY),
    # Previous column — subtle red tint
    ('BACKGROUND', (1,1), (1,-1), WHITE),
    ('TEXTCOLOR', (1,1), (1,-1), DARK_GREY),
    # Current column — subtle green tint
    ('BACKGROUND', (2,1), (2,-1), TEAL_LIGHT),
    ('TEXTCOLOR', (2,1), (2,-1), DARK_GREY),
    # Accuracy row — highlight
    ('BACKGROUND', (1,4), (1,4), RED_LIGHT),
    ('BACKGROUND', (2,4), (2,4), TEAL_LIGHT),
    ('FONTNAME', (1,4), (2,5), 'Helvetica-Bold'),
    ('TEXTCOLOR', (1,4), (1,5), RED),
    ('TEXTCOLOR', (2,4), (2,5), TEAL),
    # General
    ('FONTSIZE', (0,1), (-1,-1), 9),
    ('FONTNAME', (1,1), (1,-1), 'Helvetica'),
    ('FONTNAME', (2,1), (2,-1), 'Helvetica'),
    ('GRID', (0,0), (-1,-1), 0.5, HexColor('#BDBDBD')),
    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('TOPPADDING', (0,0), (-1,-1), 6),
    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ('LEFTPADDING', (0,0), (-1,-1), 6),
    ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ('ALIGN', (0,1), (0,-1), 'LEFT'),
]))
story.append(comp_table)
story.append(PageBreak())

# ════════════════════════════════════════════════════════════════════════════
# SECTION 5 — KEY APPROACH
# ════════════════════════════════════════════════════════════════════════════
story.append(section_header('5. Key Approach to Gaining Higher Accuracy', ''))
story.append(Spacer(1, 8))

story.append(Paragraph(
    'The single most important change was switching from one large complex model '
    'to three smaller, smarter models working together.',
    S('Intro', fontSize=12, textColor=NAVY, fontName='Helvetica-Bold',
      alignment=TA_LEFT, leading=18, spaceAfter=10)
))

approach_items = [
    ('Why did the old model underperform?',
     'RETFound is a massive 307M-parameter Vision Transformer designed for few-shot '
     'medical research. When trained on only ~4,000 images (a small dataset), it memorised '
     'the training data instead of learning general patterns — this is called overfitting. '
     'Result: high training accuracy but weaker real-world accuracy.'),

    ('Why does the Ensemble work better?',
     'Three smaller, purpose-built CNNs (EfficientNetB3, DenseNet121, InceptionResNetV2) '
     'each look at the image from a slightly different angle — at different input resolutions '
     'and with different filter patterns. When their predictions are averaged, individual '
     'mistakes cancel out and shared correct answers are amplified.'),

    ('Simple analogy:',
     'Imagine asking 3 doctors independently for their diagnosis, then going with the '
     'majority opinion. This is far more reliable than consulting just one doctor, even if '
     'that doctor went to a more prestigious school.'),

    ('How were individual model errors reduced?',
     'Strong data augmentation (CLAHE, elastic transforms, colour jitter) showed the model '
     'many artificially varied versions of each image, so it learnt to focus on disease '
     'features rather than image-specific artefacts. Label smoothing prevented overconfidence. '
     'Weighted sampling ensured no single class dominated training.'),

    ('Why does 5-view TTA help at inference?',
     'At prediction time, each image is tested in 5 different orientations (original, '
     'flipped, rotated, cropped), and all results are averaged. This reduces the chance '
     'of a single unusual view causing a wrong answer.'),
]

for i, (heading, text) in enumerate(approach_items):
    bg = LIGHT_BLUE if i % 2 == 0 else TEAL_LIGHT
    row = Table([[
        Paragraph(f'<b>{heading}</b>', S('AH', fontSize=10, textColor=NAVY,
                  fontName='Helvetica-Bold', leading=14)),
        Paragraph(text, S('AT', fontSize=9.5, textColor=DARK_GREY,
                  fontName='Helvetica', leading=14, alignment=TA_JUSTIFY)),
    ]], colWidths=[W*0.28, W*0.72])
    row.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), bg),
        ('BACKGROUND', (1,0), (1,0), WHITE),
        ('BOX', (0,0), (-1,-1), 0.5, HexColor('#90CAF9')),
        ('LINEAFTER', (0,0), (0,0), 1, HexColor('#90CAF9')),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(row)
    story.append(Spacer(1, 4))

story.append(Spacer(1, 12))

# Summary bar
summary = Table([[
    Paragraph(
        '<b>In Summary:</b>  The accuracy improved from 92.77% to 95.42% because we replaced '
        'one overfit mega-model with three lighter, focused CNNs + smart training tricks. '
        'Ensemble diversity + strong augmentation + balanced training = robust accuracy.',
        S('SUM', fontSize=10, textColor=NAVY, fontName='Helvetica',
          leading=16, alignment=TA_JUSTIFY)
    )
]], colWidths=[W])
summary.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), LIGHT_BLUE),
    ('BOX', (0,0), (-1,-1), 2, BLUE),
    ('TOPPADDING', (0,0), (-1,-1), 12),
    ('BOTTOMPADDING', (0,0), (-1,-1), 12),
    ('LEFTPADDING', (0,0), (-1,-1), 14),
    ('RIGHTPADDING', (0,0), (-1,-1), 14),
]))
story.append(summary)
story.append(Spacer(1, 16))

# Footer note
story.append(HRFlowable(width=W, color=MID_GREY, thickness=0.5))
story.append(Spacer(1, 6))
story.append(Paragraph(
    'VisionAI — Eye Disease Classification System  |  Karthikeya Chavala  |  October 2026  |  '
    'Dataset: gunavenkatdoddi/eye-diseases-classification (Kaggle)  |  '
    'Models: EfficientNetB3, DenseNet121, InceptionResNetV2 via timm library',
    small_note))

# ── Build ─────────────────────────────────────────────────────────────────────
doc.build(story)
print(f"PDF saved: {OUTPUT_PATH}")
