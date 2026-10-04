"""
Test Fine-Tuned RETFound on Your Sample Fundus Images
=====================================================
Tests the fine-tuned checkpoint on images from:
  Test images/sample_fundus_tests/

Extracts ground truth from filenames and prints per-image predictions
with confidence scores, then shows overall accuracy.

Usage (Colab — after training):
  1. Upload this script + your test images folder to Colab
  2. Set CHECKPOINT_PATH to your trained checkpoint
  3. Set TEST_DIR to your uploaded test images folder
  4. Run the script

Usage (Local — Windows):
  python test_on_sample_images.py
"""

import os, re, sys, glob
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms
from PIL import Image
from functools import partial
from collections import Counter

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION — Update these paths for your environment
# ═══════════════════════════════════════════════════════════════════════════════

# --- For Colab (after training): ---
# CHECKPOINT_PATH = '/content/retfound_output/retfound_classifier.pth'
# TEST_DIR = '/content/sample_fundus_tests'

# --- For Local (Windows): ---
CHECKPOINT_PATH = r'backend\models\retfound_classifier.pth'
TEST_DIR = r'Test images\sample_fundus_tests'

# Auto-resolve relative paths from project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.isabs(CHECKPOINT_PATH):
    CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, CHECKPOINT_PATH)
if not os.path.isabs(TEST_DIR):
    TEST_DIR = os.path.join(PROJECT_ROOT, TEST_DIR)

CLASS_NAMES = ['Normal', 'Diabetic_Retinopathy', 'Glaucoma', 'Cataract']
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

# ═══════════════════════════════════════════════════════════════════════════════
# MODEL ARCHITECTURE (must match training exactly)
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import timm.models.vision_transformer
except ImportError:
    print("ERROR: timm not installed. Run: pip install timm")
    sys.exit(1)


class RETFoundViT(timm.models.vision_transformer.VisionTransformer):
    """Official RETFound ViT architecture."""
    def __init__(self, global_pool=False, **kwargs):
        super().__init__(**kwargs)
        self.global_pool = global_pool
        if self.global_pool:
            norm_layer = kwargs['norm_layer']
            embed_dim = kwargs['embed_dim']
            self.fc_norm = norm_layer(embed_dim)
            del self.norm

    def forward_features(self, x):
        B = x.shape[0]
        x = self.patch_embed(x)
        cls_tokens = self.cls_token.expand(B, -1, -1)
        x = torch.cat((cls_tokens, x), dim=1)
        x = x + self.pos_embed
        x = self.pos_drop(x)
        for blk in self.blocks:
            x = blk(x)
        if self.global_pool:
            x = x[:, 1:, :].mean(dim=1)
            outcome = self.fc_norm(x)
        else:
            x = self.norm(x)
            outcome = x[:, 0]
        return outcome


class RETFoundClassifier(nn.Module):
    """RETFound backbone + classification head."""
    def __init__(self, backbone, num_classes=4, dropout=0.3):
        super().__init__()
        self.backbone = backbone
        embed_dim = getattr(backbone, 'embed_dim', 1024)
        self.classifier = nn.Sequential(
            nn.LayerNorm(embed_dim),
            nn.Dropout(dropout),
            nn.Linear(embed_dim, 512),
            nn.GELU(),
            nn.Dropout(dropout / 2),
            nn.Linear(512, num_classes),
        )

    def forward(self, x):
        features = self.backbone.forward_features(x)
        if features.dim() == 3:
            features = features[:, 0, :]
        return self.classifier(features)


def vit_large_patch16(**kwargs):
    return RETFoundViT(
        patch_size=16, embed_dim=1024, depth=24, num_heads=16,
        mlp_ratio=4, qkv_bias=True,
        norm_layer=partial(nn.LayerNorm, eps=1e-6), **kwargs
    )

# ═══════════════════════════════════════════════════════════════════════════════
# IMAGE PREPROCESSING (matches training/inference pipeline)
# ═══════════════════════════════════════════════════════════════════════════════

def crop_retina_circle(image, tol=15):
    """Identical to backend/model.py:crop_retina_circle"""
    img_np = np.array(image)
    if img_np.ndim != 3 or img_np.shape[2] < 3:
        return image
    gray = np.mean(img_np[:, :, :3], axis=2)
    mask = gray > tol
    if not np.any(mask):
        return image
    rs, cs = np.sum(mask, axis=1), np.sum(mask, axis=0)
    yi, xi = np.where(rs > 0)[0], np.where(cs > 0)[0]
    if len(yi) == 0 or len(xi) == 0:
        return image
    y0, y1, x0, x1 = yi[0], yi[-1], xi[0], xi[-1]
    side = max(y1 - y0, x1 - x0)
    cy, cx = (y0 + y1) // 2, (x0 + x1) // 2
    a = max(0, cy - side // 2)
    b = min(img_np.shape[0], cy + side // 2)
    c = max(0, cx - side // 2)
    d = min(img_np.shape[1], cx + side // 2)
    cropped = img_np[a:b, c:d]
    return Image.fromarray(cropped) if cropped.size > 0 else image


def get_tta_transforms(img_size):
    """10-view TTA for maximum accuracy."""
    norm = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    base = lambda extra: transforms.Compose([
        transforms.Resize((img_size, img_size)),
        *extra,
        transforms.ToTensor(), norm,
    ])
    return [
        transforms.Compose([transforms.Resize((img_size, img_size)),
                            transforms.ToTensor(), norm]),          # 1: Original
        base([transforms.RandomHorizontalFlip(p=1.0)]),             # 2: H-flip
        base([transforms.RandomVerticalFlip(p=1.0)]),               # 3: V-flip
        base([transforms.RandomRotation(10),
              transforms.CenterCrop(img_size)]),                    # 4: Rotate
        transforms.Compose([
            transforms.RandomResizedCrop(img_size, scale=(0.9, 1.0)),
            transforms.ToTensor(), norm]),                          # 5: Zoom
        base([transforms.ColorJitter(brightness=0.15)]),            # 6: Bright+
        base([transforms.ColorJitter(brightness=-0.1)]),            # 7: Bright-
        base([transforms.ColorJitter(contrast=0.15)]),              # 8: Contrast+
        base([transforms.RandomHorizontalFlip(p=1.0),
              transforms.RandomRotation(5)]),                       # 9: Combo
        transforms.Compose([
            transforms.RandomResizedCrop(img_size, scale=(0.85, 0.95)),
            transforms.ToTensor(), norm]),                          # 10: Wide zoom
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# GROUND TRUTH EXTRACTION FROM FILENAMES
# ═══════════════════════════════════════════════════════════════════════════════

def extract_ground_truth(filename):
    """
    Extract the true disease label from the filename.
    
    Handles formats like:
      - Bilateral_OD_Cataract_01.jpg
      - Cataract_Test_1.jpg  
      - DiabRet_Test_3.jpg
      - Normal_Retina_Test_4.jpg
      - Bilateral_OS_Glaucoma_02.jpg
      - Bilateral_OD_DiabeticRetinopathy_01.jpg
    """
    name = filename.lower()
    
    if 'cataract' in name:
        return 3, 'Cataract'
    elif 'diabeticretinopathy' in name or 'diabret' in name or 'diabetic' in name or 'dr_' in name:
        return 1, 'Diabetic_Retinopathy'
    elif 'glaucoma' in name:
        return 2, 'Glaucoma'
    elif 'normal' in name or 'healthy' in name:
        return 0, 'Normal'
    else:
        return -1, 'Unknown'


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN TEST
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print('=' * 80)
    print('  RETFound Fine-Tuned Model — Sample Image Test')
    print('=' * 80)
    print(f'  Checkpoint: {CHECKPOINT_PATH}')
    print(f'  Test Dir:   {TEST_DIR}')
    print(f'  Device:     {DEVICE}')
    print('=' * 80)

    # ── 1. Verify paths ──────────────────────────────────────────────────────
    if not os.path.exists(CHECKPOINT_PATH):
        print(f'\n❌ ERROR: Checkpoint not found at: {CHECKPOINT_PATH}')
        print('  → Run training first, then copy retfound_classifier.pth here.')
        sys.exit(1)

    if not os.path.exists(TEST_DIR):
        print(f'\n❌ ERROR: Test directory not found at: {TEST_DIR}')
        sys.exit(1)

    # ── 2. Load checkpoint ───────────────────────────────────────────────────
    print('\n📦 Loading checkpoint...')
    ckpt = torch.load(CHECKPOINT_PATH, map_location='cpu')
    num_classes = ckpt.get('num_classes', 4)
    img_size = ckpt.get('img_size', 224)
    val_acc = ckpt.get('val_acc', 0)
    epoch = ckpt.get('epoch', 0)
    arch = ckpt.get('architecture', 'unknown')

    print(f'   Architecture: {arch}')
    print(f'   Trained epochs: {epoch}')
    print(f'   Val accuracy: {val_acc:.2f}%')
    print(f'   Image size: {img_size}px')
    print(f'   Classes: {ckpt.get("classes", CLASS_NAMES)}')

    # ── 3. Build model ───────────────────────────────────────────────────────
    print('\n🔧 Building model...')
    
    # Try official RETFound architecture first, fall back to timm
    try:
        backbone = vit_large_patch16(
            num_classes=num_classes,
            drop_path_rate=0.0,  # No dropout at inference
            global_pool=False,
        )
    except Exception:
        backbone = timm.create_model(
            'vit_large_patch16_224',
            pretrained=False,
            num_classes=0,
            global_pool='',
        )

    model = RETFoundClassifier(backbone, num_classes=num_classes)
    
    # Load weights
    missing, unexpected = model.load_state_dict(ckpt['model_state_dict'], strict=False)
    backbone_missing = [k for k in missing if 'head' not in k]
    if len(backbone_missing) > 5:
        print(f'   ⚠️ WARNING: {len(backbone_missing)} backbone keys missing!')
    else:
        print(f'   ✅ Weights loaded ({len(missing)} missing, {len(unexpected)} unexpected)')
    
    model.to(DEVICE)
    model.eval()

    id2label = ckpt.get('id2label', {str(i): n for i, n in enumerate(CLASS_NAMES)})
    id2label = {int(k): v for k, v in id2label.items()}

    # ── 4. Collect test images ───────────────────────────────────────────────
    exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    test_files = sorted([
        f for f in os.listdir(TEST_DIR)
        if os.path.splitext(f)[1].lower() in exts
    ])
    
    if not test_files:
        print(f'\n❌ No images found in {TEST_DIR}')
        sys.exit(1)

    print(f'\n📸 Found {len(test_files)} test images\n')

    # ── 5. Run predictions with 10-view TTA ──────────────────────────────────
    tta_transforms = get_tta_transforms(img_size)
    results = []

    print('─' * 80)
    print(f'  {"Filename":<45s} {"True Label":<22s} {"Predicted":<22s} {"Conf":<8s} {"✓/✗"}')
    print('─' * 80)

    for fname in test_files:
        fpath = os.path.join(TEST_DIR, fname)
        true_idx, true_label = extract_ground_truth(fname)

        # Load and preprocess
        try:
            img = Image.open(fpath).convert('RGB')
            img = crop_retina_circle(img)
        except Exception as e:
            print(f'  ⚠️ Error loading {fname}: {e}')
            continue

        # 10-view TTA
        all_probs = []
        with torch.no_grad():
            for t in tta_transforms:
                tensor = t(img).unsqueeze(0).to(DEVICE)
                logits = model(tensor)
                probs = F.softmax(logits, dim=-1)[0].cpu().float().numpy()
                all_probs.append(probs)

        avg_probs = np.mean(all_probs, axis=0)
        pred_idx = int(np.argmax(avg_probs))
        pred_label = id2label.get(pred_idx, f'Class_{pred_idx}')
        confidence = float(avg_probs[pred_idx]) * 100

        correct = pred_idx == true_idx if true_idx >= 0 else None
        mark = '✅' if correct else ('❌' if correct is not None else '❓')

        results.append({
            'filename': fname,
            'true_idx': true_idx,
            'true_label': true_label,
            'pred_idx': pred_idx,
            'pred_label': pred_label,
            'confidence': confidence,
            'correct': correct,
            'all_probs': avg_probs,
        })

        print(f'  {fname:<45s} {true_label:<22s} {pred_label:<22s} {confidence:5.1f}%  {mark}')

    print('─' * 80)

    # ── 6. Summary ───────────────────────────────────────────────────────────
    known = [r for r in results if r['correct'] is not None]
    correct_count = sum(1 for r in known if r['correct'])
    total_known = len(known)
    
    print(f'\n{"=" * 80}')
    print(f'  RESULTS SUMMARY')
    print(f'{"=" * 80}')
    
    if total_known > 0:
        accuracy = correct_count / total_known * 100
        print(f'  Overall: {correct_count}/{total_known} correct ({accuracy:.1f}%)')
    
    # Per-class breakdown
    for cls_idx, cls_name in enumerate(CLASS_NAMES):
        cls_samples = [r for r in known if r['true_idx'] == cls_idx]
        if cls_samples:
            cls_correct = sum(1 for r in cls_samples if r['correct'])
            cls_acc = cls_correct / len(cls_samples) * 100
            avg_conf = np.mean([r['confidence'] for r in cls_samples])
            print(f'  {cls_name:<25s}: {cls_correct}/{len(cls_samples)} ({cls_acc:.0f}%)  avg conf: {avg_conf:.1f}%')

    # Show incorrect predictions in detail
    incorrect = [r for r in known if not r['correct']]
    if incorrect:
        print(f'\n  ❌ MISCLASSIFICATIONS ({len(incorrect)}):')
        for r in incorrect:
            print(f'    {r["filename"]}')
            print(f'      True: {r["true_label"]}, Predicted: {r["pred_label"]} ({r["confidence"]:.1f}%)')
            probs_str = ', '.join(f'{CLASS_NAMES[i]}={r["all_probs"][i]*100:.1f}%' for i in range(len(CLASS_NAMES)))
            print(f'      All probs: {probs_str}')
    else:
        if total_known > 0:
            print(f'\n  🎉 PERFECT — All {total_known} images classified correctly!')
    
    # ── 7. Confidence distribution ───────────────────────────────────────────
    if results:
        confs = [r['confidence'] for r in results]
        print(f'\n  Confidence stats:')
        print(f'    Min: {min(confs):.1f}%  Max: {max(confs):.1f}%  Mean: {np.mean(confs):.1f}%')
        low_conf = [r for r in results if r['confidence'] < 50]
        if low_conf:
            print(f'    ⚠️ {len(low_conf)} images with confidence < 50%:')
            for r in low_conf:
                print(f'      {r["filename"]}: {r["pred_label"]} ({r["confidence"]:.1f}%)')

    # ── 8. Class distribution check ──────────────────────────────────────────
    pred_counts = Counter(r['pred_idx'] for r in results)
    print(f'\n  Prediction distribution:')
    for cls_idx in range(len(CLASS_NAMES)):
        cnt = pred_counts.get(cls_idx, 0)
        pct = cnt / len(results) * 100
        bar = '█' * int(pct / 2)
        collapsed = ' ⚠️ POSSIBLE COLLAPSE' if cnt == len(results) else ''
        print(f'    {CLASS_NAMES[cls_idx]:<25s}: {cnt:3d} ({pct:5.1f}%) {bar}{collapsed}')

    print(f'\n{"=" * 80}')
    return results


if __name__ == '__main__':
    main()
