"""
RETFound ViT-Large Fine-Tuning — KAGGLE NOTEBOOK (v3 — Accuracy-Boosted)
=========================================================================
Target: Kaggle T4 x2 / P100 GPU (16 GB VRAM)
Dataset: ODIR-5K 4-Class (Normal, DR, Glaucoma, Cataract)

v3 Accuracy Boosts:
  [Boost 1] 384px resolution — optic disc detail for glaucoma (+2-3%)
  [Boost 2] LoRA rank 32 — more expressive adaptation (+0.5-1%)
  [Boost 3] Focal Loss — hard-example mining for weak classes (+0.5-1.5%)
  [Boost 4] Progressive resize — 224px warmup then 384px refinement
  [Boost 5] 10-view TTA (up from 5-view)

Previous v2 fixes still applied:
  [Bug 1] NO CLAHE — matches backend inference pipeline
  [Bug 3] Gradient accumulation — batch=2 * accum=16 = effective 32
  [Bug 4] AMP (float16)
  [Bug 5] LoRA on QKV + proj
  [Bug 7] Unfreezes backbone LayerNorms

KAGGLE SETUP:
  1. Add dataset: "gunavenkatdoddi/eye-diseases-classification"
  2. Enable GPU: Settings → Accelerator → GPU T4 x2
  3. (Optional) Upload test images as a separate dataset
  4. Run all cells
"""

# ═══════════════════════════════════════════════════════════════════════════════
# CELL 1: INSTALL & SETUP
# ═══════════════════════════════════════════════════════════════════════════════

import subprocess, sys

def install(pkg):
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', pkg])

# timm is usually pre-installed on Kaggle, but ensure latest
try:
    import timm
    print(f'timm already installed: {timm.__version__}')
except ImportError:
    install('timm')
    import timm

# Download RETFound pretrained weights
import os
RETFOUND_WEIGHTS = '/kaggle/working/RETFound_cfp_weights.pth'
if not os.path.exists(RETFOUND_WEIGHTS):
    print('Downloading RETFound pretrained weights...')
    os.system(
        'wget -q -O /kaggle/working/RETFound_cfp_weights.pth '
        '"https://github.com/rmaphoh/RETFound_MAE/releases/download/v0.1/RETFound_cfp_weights.pth"'
    )
    if os.path.exists(RETFOUND_WEIGHTS):
        sz = os.path.getsize(RETFOUND_WEIGHTS) / (1024**2)
        print(f'Downloaded: {sz:.0f} MB')
    else:
        raise RuntimeError('Failed to download RETFound weights')
else:
    print(f'RETFound weights already present')


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 2: IMPORTS & CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

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


class Cfg:
    # ── Paths (KAGGLE-SPECIFIC) ──────────────────────────────────────────────
    # Kaggle mounts datasets at /kaggle/input/<dataset-slug>/
    # The eye diseases dataset has structure: /kaggle/input/eye-diseases-classification/dataset/
    DATASET_DIR      = '/kaggle/input/eye-diseases-classification/dataset'
    OUTPUT_DIR       = '/kaggle/working/retfound_output'
    RETFOUND_WEIGHTS = '/kaggle/working/RETFound_cfp_weights.pth'

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
    LORA_TARGETS = ['qkv', 'proj']

    # ── Training ─────────────────────────────────────────────────────────────
    EPOCHS              = 30
    WARMUP_RESIZE_EPOCHS = 5   # [Boost 4] Train at 224px for first N epochs
    # [Boost 1] batch=2 for 384px (fits T4/P100), accum=16 for effective=32
    BATCH_SIZE          = 2
    GRAD_ACCUM_STEPS    = 16    # effective_batch = 2 * 16 = 32
    NUM_WORKERS         = 2

    # ── Optimizer ────────────────────────────────────────────────────────────
    HEAD_LR      = 3e-4
    LORA_LR      = 1e-4
    NORM_LR      = 5e-5
    WEIGHT_DECAY = 0.05

    # ── Schedule ─────────────────────────────────────────────────────────────
    WARMUP_EPOCHS = 3
    MIN_LR        = 1e-6

    # ── Regularization ───────────────────────────────────────────────────────
    DROP_PATH_RATE  = 0.15  # Slightly less aggressive for medical images
    LABEL_SMOOTHING = 0.1
    MIXUP_ALPHA     = 0.2
    CUTMIX_ALPHA    = 1.0
    MIXUP_PROB      = 0.5
    CUTMIX_PROB     = 0.3
    GRAD_CLIP       = 1.0
    # [Boost 3] Focal Loss params
    FOCAL_GAMMA     = 2.0
    FOCAL_ALPHA     = None  # Computed from class frequencies

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
    USE_AMP    = True

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

# ── Auto-detect dataset path on Kaggle ───────────────────────────────────────
# Different versions of the dataset may have slightly different folder structures
def find_dataset_dir():
    """Auto-detect the correct dataset directory on Kaggle."""
    candidates = [
        '/kaggle/input/eye-diseases-classification/dataset',
        '/kaggle/input/eye-diseases-classification',
        '/kaggle/input/eye-diseases-classification/dataset/train',
    ]
    for c in candidates:
        if os.path.isdir(c):
            subdirs = os.listdir(c)
            # Check if class folders are directly here
            class_keywords = ['normal', 'glaucoma', 'cataract', 'diabetic']
            if any(any(kw in sd.lower() for kw in class_keywords) for sd in subdirs):
                print(f'✅ Dataset found at: {c}')
                print(f'   Subdirectories: {subdirs}')
                return c
            # Check one level deeper
            for sd in subdirs:
                deeper = os.path.join(c, sd)
                if os.path.isdir(deeper):
                    deeper_subs = os.listdir(deeper)
                    if any(any(kw in s.lower() for kw in class_keywords) for s in deeper_subs):
                        print(f'✅ Dataset found at: {deeper}')
                        return deeper
    
    # Last resort: scan entire /kaggle/input/
    for root, dirs, files in os.walk('/kaggle/input/'):
        if any(any(kw in d.lower() for kw in ['normal', 'glaucoma']) for d in dirs):
            print(f'✅ Dataset found at: {root}')
            return root
    
    raise RuntimeError('Could not find dataset. Make sure "eye-diseases-classification" is added.')

cfg.DATASET_DIR = find_dataset_dir()


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 3: MODEL ARCHITECTURE
# ═══════════════════════════════════════════════════════════════════════════════

class RETFoundViT(timm.models.vision_transformer.VisionTransformer):
    """Official RETFound ViT architecture from models_vit.py"""
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
# CELL 4: DATASET & AUGMENTATION
# ═══════════════════════════════════════════════════════════════════════════════

def crop_retina_circle(image, tol=15):
    """Identical to backend/model.py:crop_retina_circle — NO CLAHE."""
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
# CELL 5: FOCAL LOSS + MIXUP/CUTMIX
# ═══════════════════════════════════════════════════════════════════════════════

class FocalLoss(nn.Module):
    """
    Focal Loss: FL(p) = -alpha * (1-p)^gamma * log(p)
    Down-weights easy examples, focuses on hard cases like glaucoma.
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
    s = sum(weights)
    weights = [w * num_classes / s for w in weights]
    logger.info(f'Focal Loss class weights: {[f"{w:.3f}" for w in weights]}')
    return weights


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


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 6: LoRA + MODEL CREATION
# ═══════════════════════════════════════════════════════════════════════════════

class LoRALinear(nn.Module):
    """LoRA: y = Wx + (alpha/r) * x @ A @ B. Original W is frozen."""
    def __init__(self, original, rank=16, alpha=32, dropout=0.1):
        super().__init__()
        self.original = original
        self.scaling = alpha / rank
        original.weight.requires_grad = False
        if original.bias is not None:
            original.bias.requires_grad = False
        inf, outf = original.in_features, original.out_features
        self.lora_A = nn.Parameter(torch.zeros(inf, rank))
        self.lora_B = nn.Parameter(torch.zeros(rank, outf))
        self.lora_drop = nn.Dropout(p=dropout)
        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
        nn.init.zeros_(self.lora_B)

    def forward(self, x):
        return self.original(x) + (self.lora_drop(x) @ self.lora_A @ self.lora_B) * self.scaling


def inject_lora(model):
    count = 0
    for name, module in model.named_modules():
        for target in cfg.LORA_TARGETS:
            if hasattr(module, target) and isinstance(getattr(module, target), nn.Linear):
                orig = getattr(module, target)
                setattr(module, target, LoRALinear(
                    orig, rank=cfg.LORA_RANK, alpha=cfg.LORA_ALPHA, dropout=cfg.LORA_DROPOUT))
                count += 1
    logger.info(f'Injected LoRA (rank={cfg.LORA_RANK}) into {count} layers '
                f'(targets: {cfg.LORA_TARGETS})')
    return model


class RETFoundClassifier(nn.Module):
    """RETFound backbone + classification head. Matches backend/model.py."""
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
        for m in self.classifier.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x):
        features = self.backbone.forward_features(x)
        if features.dim() == 3:
            features = features[:, 0, :]
        return self.classifier(features)


def create_model():
    """Build RETFound ViT-Large with all v3 boosts."""
    # Step 1: Create backbone
    backbone = vit_large_patch16(
        num_classes=cfg.NUM_CLASSES,
        drop_path_rate=cfg.DROP_PATH_RATE,
        global_pool=False,
    )

    # Step 2: Load pretrained weights
    if os.path.exists(cfg.RETFOUND_WEIGHTS):
        logger.info(f'Loading RETFound weights: {cfg.RETFOUND_WEIGHTS}')
        ckpt = torch.load(cfg.RETFOUND_WEIGHTS, map_location='cpu')
        ckpt_model = ckpt.get('model', ckpt)

        state_dict = backbone.state_dict()
        for k in ['head.weight', 'head.bias']:
            if k in ckpt_model and (k not in state_dict or
                                     ckpt_model[k].shape != state_dict[k].shape):
                del ckpt_model[k]

        ckpt_model = {k: v for k, v in ckpt_model.items()
                      if not any(x in k for x in ['decoder', 'mask_token'])}

        interpolate_pos_embed(backbone, ckpt_model)

        missing, unexpected = backbone.load_state_dict(ckpt_model, strict=False)
        backbone_missing = [k for k in missing if 'head' not in k and 'fc_norm' not in k]
        if len(backbone_missing) > 5:
            logger.error(f'WARNING: {len(backbone_missing)} backbone keys NOT loaded!')
            raise RuntimeError(f'{len(backbone_missing)} backbone keys missing')
        else:
            logger.info(f'RETFound weights loaded. Missing: {len(missing)} '
                        f'(backbone: {len(backbone_missing)}), Unexpected: {len(unexpected)}')
    else:
        logger.warning('RETFound weights NOT FOUND — training from scratch!')

    # Step 3: Wrap in classifier
    model = RETFoundClassifier(backbone, num_classes=cfg.NUM_CLASSES)

    # Step 4: Freeze everything
    for p in model.parameters():
        p.requires_grad = False

    # Step 5: Inject LoRA
    inject_lora(model.backbone)

    # Step 6: Unfreeze backbone LayerNorms
    norm_count = 0
    for name, param in model.backbone.named_parameters():
        if 'norm' in name or 'ln' in name:
            param.requires_grad = True
            norm_count += 1

    # Step 7: Unfreeze classifier head
    for p in model.classifier.parameters():
        p.requires_grad = True

    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f'Params: {total:,} total, {trainable:,} trainable ({trainable/total*100:.2f}%)')

    return model


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 7: EMA + SCHEDULER + TRAINING LOOP
# ═══════════════════════════════════════════════════════════════════════════════

class EMAModel:
    """EMA of trainable params only."""
    def __init__(self, model, decay=0.9998):
        self.decay = decay
        self.shadow = {}
        for name, param in model.named_parameters():
            if param.requires_grad:
                self.shadow[name] = param.data.clone()

    @torch.no_grad()
    def update(self, model):
        for name, param in model.named_parameters():
            if param.requires_grad and name in self.shadow:
                self.shadow[name].mul_(self.decay).add_(param.data, alpha=1 - self.decay)

    def apply(self, model):
        backup = {}
        for name, param in model.named_parameters():
            if name in self.shadow:
                backup[name] = param.data.clone()
                param.data.copy_(self.shadow[name])
        return backup

    def restore(self, model, backup):
        for name, param in model.named_parameters():
            if name in backup:
                param.data.copy_(backup[name])


class CosineWarmupScheduler:
    def __init__(self, optimizer, warmup, total, min_lr=1e-6):
        self.opt, self.warmup, self.total, self.min_lr = optimizer, warmup, total, min_lr
        self.base_lrs = [g['lr'] for g in optimizer.param_groups]
    def step(self, epoch):
        s = (epoch + 1) / self.warmup if epoch < self.warmup else \
            0.5 * (1 + math.cos(math.pi * (epoch - self.warmup) / (self.total - self.warmup)))
        for g, blr in zip(self.opt.param_groups, self.base_lrs):
            g['lr'] = max(self.min_lr, blr * s)
    def get_lr(self):
        return [g['lr'] for g in self.opt.param_groups]

class EarlyStopping:
    def __init__(self, patience=10, min_delta=1e-4):
        self.patience, self.min_delta = patience, min_delta
        self.counter, self.best = 0, float('inf')
        self.stop = False
    def __call__(self, val_loss):
        if val_loss < self.best - self.min_delta:
            self.best, self.counter = val_loss, 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.stop = True
                logger.info(f'Early stopping after {self.patience} epochs.')
        return self.stop


def train_one_epoch(model, loader, criterion, optimizer, scaler, ema, device, epoch):
    model.train()
    running_loss, correct, total = 0.0, 0, 0
    optimizer.zero_grad()

    for batch_idx, (images, labels) in enumerate(loader):
        images, labels = images.to(device), labels.to(device)

        use_mix = random.random() < cfg.MIXUP_PROB
        use_cut = random.random() < cfg.CUTMIX_PROB and not use_mix

        with autocast(enabled=cfg.USE_AMP):
            if use_mix:
                images, ya, yb, lam = mixup_data(images, labels, cfg.MIXUP_ALPHA)
                out = model(images)
                loss = mixup_criterion(criterion, out, ya, yb, lam)
            elif use_cut:
                images, ya, yb, lam = cutmix_data(images, labels, cfg.CUTMIX_ALPHA)
                out = model(images)
                loss = mixup_criterion(criterion, out, ya, yb, lam)
            else:
                out = model(images)
                loss = criterion(out, labels)
                ya, yb, lam = labels, labels, 1.0

            loss = loss / cfg.GRAD_ACCUM_STEPS

        scaler.scale(loss).backward()

        _, preds = torch.max(out, 1)
        correct += (lam * preds.eq(ya).sum().item() + (1 - lam) * preds.eq(yb).sum().item())
        total += labels.size(0)
        running_loss += loss.item() * labels.size(0) * cfg.GRAD_ACCUM_STEPS

        if (batch_idx + 1) % cfg.GRAD_ACCUM_STEPS == 0:
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.GRAD_CLIP)
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad()
            ema.update(model)

        if (batch_idx + 1) % 40 == 0:
            logger.info(f'  Epoch {epoch+1} | Batch {batch_idx+1}/{len(loader)} | '
                        f'Loss: {loss.item() * cfg.GRAD_ACCUM_STEPS:.4f}')

    if len(loader) % cfg.GRAD_ACCUM_STEPS != 0:
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.GRAD_CLIP)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad()

    return {'loss': running_loss / total, 'accuracy': correct / total * 100}


@torch.no_grad()
def validate(model, loader, criterion, device):
    model.eval()
    running_loss, correct, total = 0.0, 0, 0
    all_preds, all_labels = [], []

    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        with autocast(enabled=cfg.USE_AMP):
            out = model(images)
            loss = criterion(out, labels)
        _, preds = torch.max(out, 1)
        correct += preds.eq(labels).sum().item()
        total += labels.size(0)
        running_loss += loss.item() * labels.size(0)
        all_preds.extend(preds.cpu().numpy())
        all_labels.extend(labels.cpu().numpy())

    prec, rec, f1, sup = precision_recall_fscore_support(
        all_labels, all_preds, average=None, labels=range(cfg.NUM_CLASSES), zero_division=0)
    per_class = {cfg.CLASS_NAMES[i]: {'P': prec[i]*100, 'R': rec[i]*100,
                 'F1': f1[i]*100, 'n': int(sup[i])} for i in range(cfg.NUM_CLASSES)}
    mf1 = f1_score(all_labels, all_preds, average='macro', zero_division=0) * 100

    return {'loss': running_loss / total, 'acc': correct / total * 100,
            'f1': mf1, 'per_class': per_class, 'preds': all_preds, 'labels': all_labels}


def merge_lora(model):
    merged = copy.deepcopy(model)
    for name, module in merged.named_modules():
        for target in cfg.LORA_TARGETS:
            if hasattr(module, target) and isinstance(getattr(module, target), LoRALinear):
                lora = getattr(module, target)
                orig = lora.original
                delta = (lora.lora_A @ lora.lora_B).T * lora.scaling
                orig.weight.data += delta
                orig.weight.requires_grad = True
                if orig.bias is not None:
                    orig.bias.requires_grad = True
                setattr(module, target, orig)
    return merged


def save_checkpoint(model, val_acc, epoch, history, img_size=None):
    merged = merge_lora(model)
    sz = img_size or cfg.IMG_SIZE
    ckpt = {
        'model_state_dict': merged.state_dict(),
        'num_classes': cfg.NUM_CLASSES,
        'classes': cfg.CLASS_NAMES,
        'id2label': {str(i): n for i, n in enumerate(cfg.CLASS_NAMES)},
        'label2id': {n: i for i, n in enumerate(cfg.CLASS_NAMES)},
        'val_acc': val_acc,
        'epoch': epoch + 1,
        'img_size': sz,
        'architecture': 'RETFound_ViT_Large_4Class_LoRA_v3',
        'history': history,
        'lora_rank': cfg.LORA_RANK,
        'focal_gamma': cfg.FOCAL_GAMMA,
    }
    path = os.path.join(cfg.OUTPUT_DIR, 'retfound_classifier.pth')
    torch.save(ckpt, path)
    logger.info(f'Checkpoint: {path} (img_size={sz})')
    return path


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 8: TRAINING PIPELINE WITH PROGRESSIVE RESIZE
# ═══════════════════════════════════════════════════════════════════════════════

def train_model(model, train_paths, train_labels, val_paths, val_labels, device):
    model = model.to(device)

    lora_p = [p for n, p in model.named_parameters() if p.requires_grad and 'lora' in n]
    norm_p = [p for n, p in model.named_parameters()
              if p.requires_grad and 'lora' not in n and ('norm' in n or 'ln' in n)
              and 'classifier' not in n]
    head_p = [p for n, p in model.named_parameters()
              if p.requires_grad and 'classifier' in n]

    optimizer = torch.optim.AdamW([
        {'params': lora_p, 'lr': cfg.LORA_LR, 'weight_decay': cfg.WEIGHT_DECAY},
        {'params': norm_p, 'lr': cfg.NORM_LR, 'weight_decay': 0.0},
        {'params': head_p, 'lr': cfg.HEAD_LR, 'weight_decay': cfg.WEIGHT_DECAY},
    ])

    # [Boost 3] Focal Loss
    class_weights = compute_class_weights(train_labels)
    criterion = FocalLoss(
        gamma=cfg.FOCAL_GAMMA,
        alpha=class_weights,
        label_smoothing=cfg.LABEL_SMOOTHING,
        num_classes=cfg.NUM_CLASSES,
    )
    val_criterion = nn.CrossEntropyLoss()

    scheduler = CosineWarmupScheduler(optimizer, cfg.WARMUP_EPOCHS, cfg.EPOCHS, cfg.MIN_LR)
    early_stop = EarlyStopping(cfg.PATIENCE)
    ema = EMAModel(model, cfg.EMA_DECAY)
    scaler = GradScaler(enabled=cfg.USE_AMP)

    best_acc, best_f1, best_state = 0.0, 0.0, None
    hist = {'tr_loss': [], 'tr_acc': [], 'va_loss': [], 'va_acc': [], 'va_f1': [], 'lr': []}
    current_img_size = cfg.IMG_SIZE_WARMUP  # Start at 224

    logger.info('=' * 70)
    logger.info(f'Training: {cfg.EPOCHS} ep, BS={cfg.BATCH_SIZE}x{cfg.GRAD_ACCUM_STEPS}='
                f'{cfg.BATCH_SIZE*cfg.GRAD_ACCUM_STEPS}, LoRA r={cfg.LORA_RANK} '
                f'targets={cfg.LORA_TARGETS}, AMP={cfg.USE_AMP}')
    logger.info(f'Focal Loss: gamma={cfg.FOCAL_GAMMA}, alpha={[f"{w:.2f}" for w in class_weights]}')
    logger.info(f'Progressive Resize: {cfg.IMG_SIZE_WARMUP}px (ep 1-{cfg.WARMUP_RESIZE_EPOCHS}) '
                f'-> {cfg.IMG_SIZE}px (ep {cfg.WARMUP_RESIZE_EPOCHS+1}+)')
    logger.info('=' * 70)

    # Build initial dataloaders at warmup resolution
    tr_ds = RetinalDataset(train_paths, train_labels, get_train_transforms(current_img_size))
    va_ds = RetinalDataset(val_paths, val_labels, get_val_transforms(current_img_size))
    train_loader = DataLoader(tr_ds, batch_size=cfg.BATCH_SIZE,
                              sampler=get_balanced_sampler(train_labels),
                              num_workers=cfg.NUM_WORKERS, pin_memory=True, drop_last=True)
    val_loader = DataLoader(va_ds, batch_size=cfg.BATCH_SIZE, shuffle=False,
                            num_workers=cfg.NUM_WORKERS, pin_memory=True)

    for epoch in range(cfg.EPOCHS):
        # [Boost 4] Progressive resize: switch to 384 after warmup
        if epoch == cfg.WARMUP_RESIZE_EPOCHS and current_img_size != cfg.IMG_SIZE:
            current_img_size = cfg.IMG_SIZE
            logger.info(f'\n{"="*70}')
            logger.info(f'PROGRESSIVE RESIZE: Switching to {current_img_size}px')
            logger.info(f'{"="*70}')
            tr_ds = RetinalDataset(train_paths, train_labels, get_train_transforms(current_img_size))
            va_ds = RetinalDataset(val_paths, val_labels, get_val_transforms(current_img_size))
            train_loader = DataLoader(tr_ds, batch_size=cfg.BATCH_SIZE,
                                      sampler=get_balanced_sampler(train_labels),
                                      num_workers=cfg.NUM_WORKERS, pin_memory=True, drop_last=True)
            val_loader = DataLoader(va_ds, batch_size=cfg.BATCH_SIZE, shuffle=False,
                                    num_workers=cfg.NUM_WORKERS, pin_memory=True)
            gc.collect()
            torch.cuda.empty_cache()

        scheduler.step(epoch)
        lr = scheduler.get_lr()

        trm = train_one_epoch(model, train_loader, criterion, optimizer, scaler, ema, device, epoch)
        vam = validate(model, val_loader, val_criterion, device)

        backup = ema.apply(model)
        ema_m = validate(model, val_loader, val_criterion, device)
        ema.restore(model, backup)

        use_ema = ema_m['acc'] > vam['acc']
        best_m = ema_m if use_ema else vam

        hist['tr_loss'].append(trm['loss']); hist['tr_acc'].append(trm['accuracy'])
        hist['va_loss'].append(best_m['loss']); hist['va_acc'].append(best_m['acc'])
        hist['va_f1'].append(best_m['f1']); hist['lr'].append(lr[0])

        res_tag = f' [{current_img_size}px]'
        tag = ' [EMA]' if use_ema else ''
        logger.info(f'Ep {epoch+1}/{cfg.EPOCHS}{res_tag} | Tr: {trm["loss"]:.4f}/{trm["accuracy"]:.1f}% | '
                    f'Va: {best_m["loss"]:.4f}/{best_m["acc"]:.1f}% | F1: {best_m["f1"]:.1f}%{tag}')
        for cn, cm in best_m['per_class'].items():
            logger.info(f'  {cn:>25s}: P={cm["P"]:.1f}% R={cm["R"]:.1f}% F1={cm["F1"]:.1f}% (n={cm["n"]})')

        if best_m['acc'] > best_acc or (best_m['acc'] == best_acc and best_m['f1'] > best_f1):
            best_acc, best_f1 = best_m['acc'], best_m['f1']
            best_state = copy.deepcopy(model.state_dict())
            if use_ema:
                backup2 = ema.apply(model)
                save_checkpoint(model, best_acc, epoch, hist, current_img_size)
                ema.restore(model, backup2)
            else:
                save_checkpoint(model, best_acc, epoch, hist, current_img_size)
            logger.info(f'  ★ Best! Acc={best_acc:.2f}% F1={best_f1:.2f}%')

        if early_stop(best_m['loss']):
            break

    if best_state:
        model.load_state_dict(best_state)
    return {'model': model, 'history': hist, 'best_acc': best_acc, 'best_f1': best_f1}


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 9: TTA EVALUATION + PLOTTING
# ═══════════════════════════════════════════════════════════════════════════════

@torch.no_grad()
def evaluate_tta(model, test_paths, test_labels, device, img_size=None):
    model.eval()
    model = model.to(device)
    sz = img_size or cfg.IMG_SIZE
    tta = get_tta_transforms(sz)
    all_preds, all_confs = [], []

    for idx, (path, _) in enumerate(zip(test_paths, test_labels)):
        try:
            img = Image.open(path).convert('RGB')
            img = crop_retina_circle(img)
        except Exception:
            all_preds.append(0); all_confs.append(0.0); continue

        probs = []
        for t in tta:
            with autocast(enabled=cfg.USE_AMP):
                tensor = t(img).unsqueeze(0).to(device)
                p = F.softmax(model(tensor), dim=-1)[0].cpu().float().numpy()
            probs.append(p)
        avg_probs = np.mean(probs, axis=0)
        all_preds.append(int(np.argmax(avg_probs)))
        all_confs.append(float(np.max(avg_probs)))

        if (idx + 1) % 50 == 0:
            logger.info(f'TTA ({len(tta)}-view): {idx+1}/{len(test_paths)}')

    cm = confusion_matrix(test_labels, all_preds, labels=range(cfg.NUM_CLASSES))
    acc = np.mean(np.array(all_preds) == np.array(test_labels)) * 100
    mf1 = f1_score(test_labels, all_preds, average='macro', zero_division=0) * 100

    print('\n' + '=' * 70)
    print(f'TEST RESULTS ({len(tta)}-view TTA @ {sz}px)')
    print('=' * 70)
    print(classification_report(test_labels, all_preds, target_names=cfg.CLASS_NAMES, digits=4))
    print(f'Accuracy: {acc:.2f}% | Macro F1: {mf1:.2f}%')
    return {'acc': acc, 'f1': mf1, 'cm': cm, 'preds': all_preds, 'confs': all_confs}


def plot_results(hist, cm, save_dir):
    epochs = range(1, len(hist['tr_loss']) + 1)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('RETFound + LoRA (v3 — 384px + Focal Loss) [Kaggle]', fontsize=16, fontweight='bold')
    axes[0,0].plot(epochs, hist['tr_loss'], 'b-', lw=2, label='Train')
    axes[0,0].plot(epochs, hist['va_loss'], 'r-', lw=2, label='Val')
    axes[0,0].set_title('Loss'); axes[0,0].legend(); axes[0,0].grid(alpha=0.3)
    axes[0,1].plot(epochs, hist['tr_acc'], 'b-', lw=2, label='Train')
    axes[0,1].plot(epochs, hist['va_acc'], 'r-', lw=2, label='Val')
    axes[0,1].set_title('Accuracy (%)'); axes[0,1].legend(); axes[0,1].grid(alpha=0.3)
    axes[1,0].plot(epochs, hist['va_f1'], 'g-', lw=2)
    axes[1,0].set_title('Macro F1 (%)'); axes[1,0].grid(alpha=0.3)
    axes[1,1].plot(epochs, hist['lr'], 'purple', lw=2)
    axes[1,1].set_title('LR'); axes[1,1].set_yscale('log'); axes[1,1].grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, 'history.png'), dpi=150, bbox_inches='tight')
    plt.show()

    fig, ax = plt.subplots(1, 2, figsize=(16, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=cfg.CLASS_NAMES, yticklabels=cfg.CLASS_NAMES, ax=ax[0])
    ax[0].set_title('Counts')
    cm_pct = cm.astype(float) / cm.sum(axis=1, keepdims=True) * 100
    sns.heatmap(cm_pct, annot=True, fmt='.1f', cmap='RdYlGn', vmin=0, vmax=100,
                xticklabels=cfg.CLASS_NAMES, yticklabels=cfg.CLASS_NAMES, ax=ax[1])
    ax[1].set_title('% per class')
    plt.tight_layout()
    plt.savefig(os.path.join(save_dir, 'confusion.png'), dpi=150, bbox_inches='tight')
    plt.show()


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 10: SAMPLE IMAGE TESTING
# ═══════════════════════════════════════════════════════════════════════════════

def extract_ground_truth(filename):
    """Extract the true disease label from the filename."""
    name = filename.lower()
    if 'cataract' in name:
        return 3, 'Cataract'
    elif 'diabeticretinopathy' in name or 'diabret' in name or 'diabetic' in name:
        return 1, 'Diabetic_Retinopathy'
    elif 'glaucoma' in name:
        return 2, 'Glaucoma'
    elif 'normal' in name or 'healthy' in name:
        return 0, 'Normal'
    else:
        return -1, 'Unknown'


def test_sample_images(model, test_dir, device, img_size=None):
    """Test the trained model on your sample fundus images."""
    model.eval()
    model = model.to(device)
    sz = img_size or cfg.IMG_SIZE

    exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    test_files = sorted([
        f for f in os.listdir(test_dir)
        if os.path.splitext(f)[1].lower() in exts
    ])

    if not test_files:
        print(f'No images found in {test_dir}')
        return

    tta = get_tta_transforms(sz)
    results = []

    print('\n' + '=' * 80)
    print(f'  SAMPLE IMAGE TEST ({len(test_files)} images, {len(tta)}-view TTA @ {sz}px)')
    print('=' * 80)
    print(f'  {"Filename":<45s} {"True":<22s} {"Predicted":<22s} {"Conf":<8s} {"✓/✗"}')
    print('─' * 80)

    for fname in test_files:
        fpath = os.path.join(test_dir, fname)
        true_idx, true_label = extract_ground_truth(fname)

        try:
            img = Image.open(fpath).convert('RGB')
            img = crop_retina_circle(img)
        except Exception as e:
            print(f'  ⚠️ Error loading {fname}: {e}')
            continue

        all_probs = []
        with torch.no_grad():
            for t in tta:
                tensor = t(img).unsqueeze(0).to(device)
                with autocast(enabled=cfg.USE_AMP):
                    logits = model(tensor)
                probs = F.softmax(logits, dim=-1)[0].cpu().float().numpy()
                all_probs.append(probs)

        avg_probs = np.mean(all_probs, axis=0)
        pred_idx = int(np.argmax(avg_probs))
        pred_label = cfg.CLASS_NAMES[pred_idx]
        confidence = float(avg_probs[pred_idx]) * 100

        correct = pred_idx == true_idx if true_idx >= 0 else None
        mark = '✅' if correct else ('❌' if correct is not None else '❓')

        results.append({
            'filename': fname, 'true_idx': true_idx, 'true_label': true_label,
            'pred_idx': pred_idx, 'pred_label': pred_label,
            'confidence': confidence, 'correct': correct, 'all_probs': avg_probs,
        })

        print(f'  {fname:<45s} {true_label:<22s} {pred_label:<22s} {confidence:5.1f}%  {mark}')

    print('─' * 80)

    known = [r for r in results if r['correct'] is not None]
    correct_count = sum(1 for r in known if r['correct'])
    if known:
        print(f'\n  Overall: {correct_count}/{len(known)} correct ({correct_count/len(known)*100:.1f}%)')

    incorrect = [r for r in known if not r['correct']]
    if incorrect:
        print(f'\n  ❌ MISCLASSIFICATIONS ({len(incorrect)}):')
        for r in incorrect:
            probs_str = ', '.join(f'{cfg.CLASS_NAMES[i]}={r["all_probs"][i]*100:.1f}%'
                                  for i in range(cfg.NUM_CLASSES))
            print(f'    {r["filename"]}: True={r["true_label"]}, '
                  f'Pred={r["pred_label"]} ({r["confidence"]:.1f}%) | {probs_str}')
    elif known:
        print(f'\n  🎉 PERFECT — All {len(known)} images classified correctly!')

    print('=' * 80)
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 11: MAIN — RUN EVERYTHING
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print('=' * 70)
    print('RETFound ViT-Large + LoRA Fine-Tuning (v3 — Kaggle)')
    print(f'Device: {cfg.DEVICE}')
    if torch.cuda.is_available():
        g = torch.cuda.get_device_properties(0)
        print(f'GPU: {torch.cuda.get_device_name(0)} ({g.total_mem/1024**3:.1f} GB)')
    print(f'Boosts: 384px | LoRA r={cfg.LORA_RANK} | Focal Loss (γ={cfg.FOCAL_GAMMA}) | Progressive Resize')
    print(f'Dataset: {cfg.DATASET_DIR}')
    print('=' * 70)

    # 1. Load dataset
    paths, labels = load_dataset_from_folders(cfg.DATASET_DIR)
    if not paths:
        raise RuntimeError(f'No images in {cfg.DATASET_DIR}')
    splits = create_splits(paths, labels)

    tr_p, tr_l = splits['train']
    va_p, va_l = splits['val']
    te_p, te_l = splits['test']

    # 2. Model
    model = create_model()

    # 3. Train
    result = train_model(model, tr_p, tr_l, va_p, va_l, cfg.DEVICE)

    # 4. TTA evaluation on ODIR-5K test split
    test_res = evaluate_tta(result['model'], te_p, te_l, cfg.DEVICE, img_size=cfg.IMG_SIZE)

    # 5. Plots
    plot_results(result['history'], test_res['cm'], cfg.OUTPUT_DIR)

    # 6. Collapse check
    pred_counts = Counter(test_res['preds'])
    for ci in range(cfg.NUM_CLASSES):
        cnt = pred_counts.get(ci, 0)
        pct = cnt / len(test_res['preds']) * 100
        flag = 'OK' if pct > 5 else 'COLLAPSED!'
        logger.info(f'  {cfg.CLASS_NAMES[ci]:>25s}: {cnt} ({pct:.1f}%) {flag}')

    # 7. Test on sample images if available
    # ── Option A: Upload as Kaggle dataset (recommended) ──
    sample_dirs = [
        '/kaggle/input/sample-fundus-tests',           # If uploaded as separate dataset
        '/kaggle/input/sample-fundus-tests/sample_fundus_tests',
        '/kaggle/working/sample_fundus_tests',          # If uploaded to working dir
    ]
    for sd in sample_dirs:
        if os.path.isdir(sd) and len(os.listdir(sd)) > 0:
            print(f'\n📸 Found sample test images at: {sd}')
            test_sample_images(result['model'], sd, cfg.DEVICE, img_size=cfg.IMG_SIZE)
            break
    else:
        print('\n📌 To test on your sample images:')
        print('   Upload them as a Kaggle dataset named "sample-fundus-tests"')
        print('   Or upload to /kaggle/working/sample_fundus_tests/')

    print('\n' + '=' * 70)
    print(f'Best Val: {result["best_acc"]:.2f}% acc, {result["best_f1"]:.2f}% F1')
    print(f'Test TTA: {test_res["acc"]:.2f}% acc, {test_res["f1"]:.2f}% F1')
    print(f'Checkpoint: {cfg.OUTPUT_DIR}/retfound_classifier.pth')
    print(f'\n📥 Download from Output tab → retfound_output/retfound_classifier.pth')
    print(f'   Then place at: backend/models/retfound_classifier.pth')
    print('=' * 70)
    return result, test_res


# ── RUN ──
if __name__ == '__main__':
    result, test_res = main()
else:
    # When pasted in notebook cells, just call main() in the last cell
    pass
