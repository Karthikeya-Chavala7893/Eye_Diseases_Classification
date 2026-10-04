"""
RETFound ViT-Large Fine-Tuning — Part 1 (v3 — Accuracy-Boosted)
=================================================================
Target: Google Colab T4 GPU (16 GB VRAM)
Dataset: ODIR-5K 4-Class (Normal, DR, Glaucoma, Cataract)

v3 Accuracy Boosts (on top of all v2 critique fixes):
  [Boost 1] 384px resolution — optic disc detail for glaucoma (+2-3%)
  [Boost 2] LoRA rank 32 — more expressive adaptation (+0.5-1%)
  [Boost 3] Focal Loss — hard-example mining for weak classes (+0.5-1.5%)
  [Boost 4] Progressive resize — 224px warmup then 384px refinement

Previous v2 fixes still applied:
  [Bug 1] NO CLAHE — matches backend inference pipeline
  [Bug 3] Gradient accumulation — batch=2 * accum=16 = effective 32
  [Bug 4] AMP (float16)
  [Bug 5] LoRA on QKV + proj
  [Bug 7] Unfreezes backbone LayerNorms
"""

import os, gc, copy, math, random, warnings, logging
from collections import Counter

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from torch.cuda.amp import GradScaler, autocast
from torchvision import transforms
from PIL import Image
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, confusion_matrix,
    f1_score, precision_recall_fscore_support,
)
from functools import partial
from timm.models.layers import trunc_normal_
import timm.models.vision_transformer

warnings.filterwarnings('ignore', category=UserWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('retfound_ft')


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

class Cfg:
    # ── Paths ────────────────────────────────────────────────────────────────
    DATASET_DIR      = '/content/dataset'
    OUTPUT_DIR       = '/content/retfound_output'
    RETFOUND_WEIGHTS = '/content/RETFound_cfp_weights.pth'
    KAGGLE_DATASET   = 'gunavenkatdoddi/eye-diseases-classification'

    # ── Model ────────────────────────────────────────────────────────────────
    NUM_CLASSES = 4
    CLASS_NAMES = ['Normal', 'Diabetic_Retinopathy', 'Glaucoma', 'Cataract']
    # [Boost 1] 384px — makes optic disc ~2x larger for glaucoma detection
    IMG_SIZE    = 384
    IMG_SIZE_WARMUP = 224  # [Boost 4] Progressive resize warmup resolution

    # ── LoRA ─────────────────────────────────────────────────────────────────
    # [Boost 2] Rank 32 — more expressive than 16, still only ~3% of params
    LORA_RANK    = 32
    LORA_ALPHA   = 64  # Keep alpha = 2*rank for stable scaling
    LORA_DROPOUT = 0.1
    # [Bug 5 fix] Target both QKV and output projection
    LORA_TARGETS = ['qkv', 'proj']

    # ── Training ─────────────────────────────────────────────────────────────
    EPOCHS              = 30
    WARMUP_RESIZE_EPOCHS = 5   # [Boost 4] Train at 224px for first N epochs
    # [Boost 1] batch=2 for 384px (fits T4), accum=16 for effective=32
    BATCH_SIZE          = 2
    GRAD_ACCUM_STEPS    = 16    # effective_batch = 2 * 16 = 32
    NUM_WORKERS         = 2

    # ── Optimizer ────────────────────────────────────────────────────────────
    HEAD_LR      = 3e-4
    LORA_LR      = 1e-4
    NORM_LR      = 5e-5    # [Bug 7 fix] Separate LR for unfrozen LayerNorms
    WEIGHT_DECAY = 0.05

    # ── Schedule ─────────────────────────────────────────────────────────────
    WARMUP_EPOCHS = 3
    MIN_LR        = 1e-6

    # ── Regularization ───────────────────────────────────────────────────────
    DROP_PATH_RATE  = 0.15  # Slightly less aggressive for medical images
    LABEL_SMOOTHING = 0.1
    MIXUP_ALPHA     = 0.2   # Reduced from 0.3 — less aggressive for medical
    CUTMIX_ALPHA    = 1.0
    MIXUP_PROB      = 0.5
    CUTMIX_PROB     = 0.3
    GRAD_CLIP       = 1.0
    # [Boost 3] Focal Loss params
    FOCAL_GAMMA     = 2.0   # Focus factor — higher = more focus on hard examples
    FOCAL_ALPHA     = None  # Will be computed from class frequencies

    # ── Early Stopping ───────────────────────────────────────────────────────
    PATIENCE  = 10
    MIN_DELTA = 1e-4

    # ── EMA ──────────────────────────────────────────────────────────────────
    EMA_DECAY = 0.9998

    # ── Splits ───────────────────────────────────────────────────────────────
    VAL_SPLIT  = 0.15
    TEST_SPLIT = 0.15
    SEED       = 42
    DEVICE     = 'cuda' if torch.cuda.is_available() else 'cpu'

    # [Bug 4 fix] AMP
    USE_AMP = True

cfg = Cfg()


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

seed_everything(cfg.SEED)
os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# [Bug 2 fix] OFFICIAL RETFound MODEL ARCHITECTURE
# Uses the exact same VisionTransformer subclass from rmaphoh/RETFound_MAE
# so that pretrained weights load with ZERO mismatched keys.
# ═══════════════════════════════════════════════════════════════════════════════

class RETFoundViT(timm.models.vision_transformer.VisionTransformer):
    """
    Official RETFound ViT architecture from models_vit.py
    (https://github.com/rmaphoh/RETFound_MAE/blob/main/models_vit.py)

    Difference from timm default: supports global_pool with fc_norm.
    """
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


def vit_large_patch16(**kwargs):
    """Create RETFound ViT-Large with the exact official config."""
    model = RETFoundViT(
        patch_size=16, embed_dim=1024, depth=24, num_heads=16,
        mlp_ratio=4, qkv_bias=True,
        norm_layer=partial(nn.LayerNorm, eps=1e-6), **kwargs
    )
    return model


def interpolate_pos_embed(model, checkpoint_model):
    """Official RETFound positional embedding interpolation."""
    if 'pos_embed' in checkpoint_model:
        pos_embed_ckpt = checkpoint_model['pos_embed']
        embedding_size = pos_embed_ckpt.shape[-1]
        num_patches = model.patch_embed.num_patches
        num_extra_tokens = model.pos_embed.shape[-2] - num_patches

        orig_size = int((pos_embed_ckpt.shape[-2] - num_extra_tokens) ** 0.5)
        new_size = int(num_patches ** 0.5)

        if orig_size != new_size:
            extra_tokens = pos_embed_ckpt[:, :num_extra_tokens]
            pos_tokens = pos_embed_ckpt[:, num_extra_tokens:]
            pos_tokens = pos_tokens.reshape(-1, orig_size, orig_size, embedding_size)
            pos_tokens = pos_tokens.permute(0, 3, 1, 2)
            pos_tokens = torch.nn.functional.interpolate(
                pos_tokens, size=(new_size, new_size),
                mode='bicubic', align_corners=False)
            pos_tokens = pos_tokens.permute(0, 2, 3, 1).flatten(1, 2)
            new_pos_embed = torch.cat((extra_tokens, pos_tokens), dim=1)
            checkpoint_model['pos_embed'] = new_pos_embed


# ═══════════════════════════════════════════════════════════════════════════════
# DATASET DOWNLOAD (uncomment in Colab)
# ═══════════════════════════════════════════════════════════════════════════════

def download_dataset():
    os.makedirs('/root/.kaggle', exist_ok=True)
    if os.path.exists('kaggle.json'):
        import shutil
        shutil.copy('kaggle.json', '/root/.kaggle/kaggle.json')
        os.chmod('/root/.kaggle/kaggle.json', 0o600)
    ret = os.system(f'kaggle datasets download -d {cfg.KAGGLE_DATASET} -p /content/ --unzip')
    if ret != 0:
        raise RuntimeError('Kaggle download failed. Upload kaggle.json first.')
    for c in ['/content/dataset', '/content/eye-diseases-classification', '/content']:
        if os.path.isdir(c):
            for sub in os.listdir(c):
                if sub.lower() in ('train', 'normal', 'glaucoma'):
                    cfg.DATASET_DIR = c
                    logger.info(f'Dataset dir: {cfg.DATASET_DIR}')
                    return

def download_retfound_weights():
    if not os.path.exists(cfg.RETFOUND_WEIGHTS):
        logger.info('Downloading RETFound pretrained weights...')
        ret = os.system(
            'wget -q -O /content/RETFound_cfp_weights.pth '
            '"https://github.com/rmaphoh/RETFound_MAE/releases/download/v0.1/RETFound_cfp_weights.pth"')
        if ret != 0 or not os.path.exists(cfg.RETFOUND_WEIGHTS):
            raise RuntimeError('Failed to download RETFound weights.')

# Uncomment in Colab:
# download_dataset()
# download_retfound_weights()


# ═══════════════════════════════════════════════════════════════════════════════
# RETINAL ROI CROPPING (matches backend/model.py EXACTLY)
# [Bug 1 fix] NO CLAHE — must match inference pipeline
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


# ═══════════════════════════════════════════════════════════════════════════════
# AUGMENTATION PIPELINES (NO CLAHE — matches inference)
# ═══════════════════════════════════════════════════════════════════════════════

def get_train_transforms(img_size=None):
    """Training augmentation. NO CLAHE to match backend inference."""
    sz = img_size or cfg.IMG_SIZE
    return transforms.Compose([
        transforms.RandomResizedCrop(sz, scale=(0.8, 1.0),
                                     interpolation=transforms.InterpolationMode.BICUBIC),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.2),
        transforms.RandomRotation(degrees=15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.1, hue=0.05),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

def get_val_transforms(img_size=None):
    """Validation transform. Resolution-aware."""
    sz = img_size or cfg.IMG_SIZE
    return transforms.Compose([
        transforms.Resize((sz, sz)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

def get_tta_transforms(img_size=None):
    """10-view TTA for maximum accuracy at test time."""
    sz = img_size or cfg.IMG_SIZE
    norm = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    base = lambda extra: transforms.Compose([
        transforms.Resize((sz, sz)),
        *extra,
        transforms.ToTensor(), norm,
    ])
    return [
        get_val_transforms(sz),                                          # 1: Original
        base([transforms.RandomHorizontalFlip(p=1.0)]),                  # 2: H-flip
        base([transforms.RandomVerticalFlip(p=1.0)]),                    # 3: V-flip
        base([transforms.RandomRotation(10),                             # 4: Rotate+crop
              transforms.CenterCrop(sz)]),
        transforms.Compose([                                             # 5: Slight zoom
            transforms.RandomResizedCrop(sz, scale=(0.9, 1.0)),
            transforms.ToTensor(), norm,
        ]),
        base([transforms.ColorJitter(brightness=0.15)]),                 # 6: Bright+
        base([transforms.ColorJitter(brightness=-0.1)]),                 # 7: Bright-
        base([transforms.ColorJitter(contrast=0.15)]),                   # 8: Contrast+
        base([transforms.RandomHorizontalFlip(p=1.0),                    # 9: H-flip+rotate
              transforms.RandomRotation(5)]),
        transforms.Compose([                                             # 10: Wider zoom
            transforms.RandomResizedCrop(sz, scale=(0.85, 0.95)),
            transforms.ToTensor(), norm,
        ]),
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# DATASET (NO CLAHE)
# ═══════════════════════════════════════════════════════════════════════════════

class RetinalDataset(Dataset):
    """Load image -> crop_retina_circle -> augment. No CLAHE."""
    def __init__(self, paths, labels, transform):
        self.paths, self.labels, self.transform = paths, labels, transform
    def __len__(self):
        return len(self.paths)
    def __getitem__(self, idx):
        try:
            img = Image.open(self.paths[idx]).convert('RGB')
        except Exception:
            img = Image.new('RGB', (cfg.IMG_SIZE, cfg.IMG_SIZE))
        img = crop_retina_circle(img)
        return self.transform(img), self.labels[idx]


def load_dataset_from_folders(root_dir):
    paths, labels = [], []
    cmap = {}
    for i, n in enumerate(cfg.CLASS_NAMES):
        cmap[n.lower()] = i
        cmap[n.lower().replace('_', ' ')] = i
    cmap.update({'healthy': 0, 'dr': 1, 'cataracts': 3})
    exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}

    def scan(d):
        for cls_dir in sorted(os.listdir(d)):
            p = os.path.join(d, cls_dir)
            if os.path.isdir(p) and cls_dir.lower().strip() in cmap:
                lbl = cmap[cls_dir.lower().strip()]
                for f in os.listdir(p):
                    if os.path.splitext(f)[1].lower() in exts:
                        paths.append(os.path.join(p, f))
                        labels.append(lbl)

    subdirs = [x for x in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, x))]
    if any(x.lower() in cmap for x in subdirs):
        scan(root_dir)
    else:
        for sd in subdirs:
            scan(os.path.join(root_dir, sd))

    logger.info(f'Loaded {len(paths)} images')
    for ci, cnt in sorted(Counter(labels).items()):
        logger.info(f'  {cfg.CLASS_NAMES[ci]}: {cnt}')
    return paths, labels


def create_splits(paths, labels):
    tv_p, te_p, tv_l, te_l = train_test_split(
        paths, labels, test_size=cfg.TEST_SPLIT, stratify=labels, random_state=cfg.SEED)
    adj = cfg.VAL_SPLIT / (1 - cfg.TEST_SPLIT)
    tr_p, va_p, tr_l, va_l = train_test_split(
        tv_p, tv_l, test_size=adj, stratify=tv_l, random_state=cfg.SEED)
    for name, p, l in [('train', tr_p, tr_l), ('val', va_p, va_l), ('test', te_p, te_l)]:
        c = Counter(l)
        logger.info(f'{name}: {len(p)} — ' +
                    ', '.join(f'{cfg.CLASS_NAMES[k]}={v}' for k, v in sorted(c.items())))
    return {'train': (tr_p, tr_l), 'val': (va_p, va_l), 'test': (te_p, te_l)}


def get_balanced_sampler(labels):
    counts = Counter(labels)
    total = len(labels)
    weights = [total / counts[l] for l in labels]
    return WeightedRandomSampler(weights, num_samples=total, replacement=True)


# ═══════════════════════════════════════════════════════════════════════════════
# [Boost 3] FOCAL LOSS — focuses training on hard examples
# ═══════════════════════════════════════════════════════════════════════════════

class FocalLoss(nn.Module):
    """
    Focal Loss: FL(p) = -alpha * (1-p)^gamma * log(p)
    
    Compared to CrossEntropy:
    - Easy examples (p > 0.9) get down-weighted by (1-0.9)^2 = 0.01x
    - Hard examples (p < 0.3) get full weight: (1-0.3)^2 = 0.49x
    This specifically helps glaucoma (hardest class) by making the model
    focus its learning on the cases it gets wrong.
    """
    def __init__(self, gamma=2.0, alpha=None, label_smoothing=0.0, num_classes=4):
        super().__init__()
        self.gamma = gamma
        self.num_classes = num_classes
        self.label_smoothing = label_smoothing
        if alpha is not None:
            if isinstance(alpha, (list, np.ndarray)):
                self.alpha = torch.tensor(alpha, dtype=torch.float32)
            else:
                self.alpha = alpha
        else:
            self.alpha = None

    def forward(self, logits, targets):
        # Apply label smoothing manually
        if self.label_smoothing > 0:
            with torch.no_grad():
                smooth = torch.full_like(logits, self.label_smoothing / (self.num_classes - 1))
                smooth.scatter_(1, targets.unsqueeze(1), 1.0 - self.label_smoothing)
            log_probs = F.log_softmax(logits, dim=-1)
            probs = torch.exp(log_probs)
            focal_weight = (1 - probs) ** self.gamma
            if self.alpha is not None:
                alpha_t = self.alpha.to(logits.device)[targets].unsqueeze(1)
                focal_weight = focal_weight * alpha_t
            loss = -focal_weight * smooth * log_probs
            return loss.sum(dim=-1).mean()
        else:
            ce = F.cross_entropy(logits, targets, reduction='none')
            pt = torch.exp(-ce)
            focal = ((1 - pt) ** self.gamma) * ce
            if self.alpha is not None:
                alpha_t = self.alpha.to(logits.device)[targets]
                focal = alpha_t * focal
            return focal.mean()


def compute_class_weights(labels):
    """Compute inverse-frequency alpha weights for Focal Loss."""
    counts = Counter(labels)
    total = len(labels)
    num_classes = len(counts)
    weights = [total / (num_classes * counts[i]) for i in range(num_classes)]
    # Normalize so they sum to num_classes
    s = sum(weights)
    weights = [w * num_classes / s for w in weights]
    logger.info(f'Focal Loss class weights: {[f"{w:.3f}" for w in weights]}')
    return weights


# ═══════════════════════════════════════════════════════════════════════════════
# MIXUP / CUTMIX
# ═══════════════════════════════════════════════════════════════════════════════

def mixup_data(x, y, alpha=0.2):
    lam = max(np.random.beta(alpha, alpha), 0.5)
    idx = torch.randperm(x.size(0), device=x.device)
    return lam * x + (1 - lam) * x[idx], y, y[idx], lam

def cutmix_data(x, y, alpha=1.0):
    lam = np.random.beta(alpha, alpha)
    idx = torch.randperm(x.size(0), device=x.device)
    _, _, H, W = x.shape
    r = np.sqrt(1.0 - lam)
    cw, ch = int(W * r), int(H * r)
    cx, cy = np.random.randint(W), np.random.randint(H)
    x1, y1 = np.clip(cx - cw // 2, 0, W), np.clip(cy - ch // 2, 0, H)
    x2, y2 = np.clip(cx + cw // 2, 0, W), np.clip(cy + ch // 2, 0, H)
    mx = x.clone()
    mx[:, :, y1:y2, x1:x2] = x[idx, :, y1:y2, x1:x2]
    lam = 1 - ((x2 - x1) * (y2 - y1)) / (W * H)
    return mx, y, y[idx], lam

def mixup_criterion(crit, pred, ya, yb, lam):
    return lam * crit(pred, ya) + (1 - lam) * crit(pred, yb)
