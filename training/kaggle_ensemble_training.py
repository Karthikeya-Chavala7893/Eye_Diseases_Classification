"""
Ensemble Eye Disease Classifier — KAGGLE NOTEBOOK
===================================================
Target: Kaggle T4 x2 / P100 GPU (16 GB VRAM)
Dataset: gunavenkatdoddi/eye-diseases-classification (4,217 images, 4 classes)

Models:
  [1] EfficientNetB3  (~12M params, 300×300)  — best single-model accuracy
  [2] DenseNet121     (~8M params, 224×224)   — fast, complementary features
  [3] InceptionResNetV2 (~55M params, 299×299) — strongest feature extractor

Ensemble Strategy:
  - Train each model independently with model-specific hyperparameters
  - Soft voting (average probabilities) at inference time
  - 5-view TTA (Test-Time Augmentation) per model

Key Techniques:
  - Albumentations-based augmentation (CLAHE, flips, elastic, color jitter)
  - Cosine annealing LR with warmup
  - Label smoothing (0.1)
  - Weighted sampling for class balance
  - Early stopping on validation F1

KAGGLE SETUP:
  1. Add dataset: "gunavenkatdoddi/eye-diseases-classification"
  2. Enable GPU: Settings → Accelerator → GPU T4 x2
  3. (Optional) Upload test images as a separate dataset named "sample-fundus-tests"
  4. Paste this entire file into Cell 1, then run main() in Cell 2
"""

# ═══════════════════════════════════════════════════════════════════════════════
# CELL 1: INSTALL & SETUP
# ═══════════════════════════════════════════════════════════════════════════════

import subprocess, sys

def install(pkg):
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', pkg])

# Ensure required packages
for pkg in ['albumentations', 'timm']:
    try:
        __import__(pkg)
    except ImportError:
        install(pkg)

# ═══════════════════════════════════════════════════════════════════════════════
# CELL 2: IMPORTS & CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

import os, gc, copy, math, random, warnings, logging, json, time
from collections import Counter
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
# AMP — use new torch.amp API (torch.cuda.amp is deprecated in PyTorch 2.x)
try:
    from torch.amp import GradScaler, autocast
    _AMP_DEVICE = 'cuda'
except ImportError:  # PyTorch < 2.0 fallback
    from torch.cuda.amp import GradScaler, autocast  # type: ignore[no-redef]
    _AMP_DEVICE = None
from torchvision import transforms, models as tv_models
from PIL import Image
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, confusion_matrix,
    f1_score, precision_recall_fscore_support, accuracy_score,
)
import timm
import albumentations as A
from albumentations.pytorch import ToTensorV2

warnings.filterwarnings('ignore', category=UserWarning)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('ensemble_ft')


class Cfg:
    # ── Paths (KAGGLE-SPECIFIC) ──────────────────────────────────────────────
    DATASET_DIR      = '/kaggle/input/eye-diseases-classification/dataset'
    OUTPUT_DIR       = '/kaggle/working/ensemble_output'
    SAMPLE_TEST_DIR  = '/kaggle/input/sample-fundus-tests'

    # ── Model ────────────────────────────────────────────────────────────────
    NUM_CLASSES = 4
    CLASS_NAMES = ['Normal', 'Diabetic_Retinopathy', 'Glaucoma', 'Cataract']

    # ── Per-model configs ────────────────────────────────────────────────────
    MODELS = {
        'efficientnet_b3': {
            'timm_name': 'efficientnet_b3',
            'img_size': 300,
            'batch_size': 16,
            'lr': 3e-4,
            'epochs': 25,
            'weight_decay': 0.01,
            'drop_rate': 0.3,
        },
        'densenet121': {
            'timm_name': 'densenet121',
            'img_size': 224,
            'batch_size': 32,
            'lr': 3e-4,
            'epochs': 25,
            'weight_decay': 0.01,
            'drop_rate': 0.3,
        },
        'inception_resnet_v2': {
            'timm_name': 'inception_resnet_v2',
            'img_size': 299,
            'batch_size': 12,
            'lr': 1e-4,
            'epochs': 25,
            'weight_decay': 0.02,
            'drop_rate': 0.4,
        },
    }

    # ── Training shared ──────────────────────────────────────────────────────
    NUM_WORKERS       = 2
    WARMUP_EPOCHS     = 3
    MIN_LR            = 1e-6
    LABEL_SMOOTHING   = 0.1
    GRAD_CLIP         = 1.0

    # ── Early Stopping ───────────────────────────────────────────────────────
    PATIENCE  = 8
    MIN_DELTA = 1e-4

    # ── TTA ──────────────────────────────────────────────────────────────────
    TTA_VIEWS = 5

    # ── ImageNet normalization ───────────────────────────────────────────────
    MEAN = [0.485, 0.456, 0.406]
    STD  = [0.229, 0.224, 0.225]


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 3: DATASET
# ═══════════════════════════════════════════════════════════════════════════════

def discover_dataset(dataset_dir: str) -> tuple:
    """Walk the dataset directory and return (paths, labels, class_names)."""
    paths, labels = [], []
    class_dirs = sorted([
        d for d in os.listdir(dataset_dir)
        if os.path.isdir(os.path.join(dataset_dir, d))
    ])

    # Map folder names to our canonical class names
    folder_to_idx = {}
    for folder in class_dirs:
        fl = folder.lower().replace(' ', '_')
        for i, cn in enumerate(Cfg.CLASS_NAMES):
            if cn.lower() in fl or fl in cn.lower():
                folder_to_idx[folder] = i
                break
        if folder not in folder_to_idx:
            # Try partial matches
            if 'normal' in fl:
                folder_to_idx[folder] = 0
            elif 'diab' in fl or 'retin' in fl or 'dr' == fl:
                folder_to_idx[folder] = 1
            elif 'glauc' in fl:
                folder_to_idx[folder] = 2
            elif 'catar' in fl:
                folder_to_idx[folder] = 3

    logger.info(f"Class mapping: {folder_to_idx}")

    for folder, idx in folder_to_idx.items():
        folder_path = os.path.join(dataset_dir, folder)
        for fname in os.listdir(folder_path):
            ext = fname.lower().split('.')[-1]
            if ext in ('jpg', 'jpeg', 'png', 'bmp', 'tiff', 'webp'):
                paths.append(os.path.join(folder_path, fname))
                labels.append(idx)

    logger.info(f"Loaded {len(paths)} images")
    for i, cn in enumerate(Cfg.CLASS_NAMES):
        count = labels.count(i)
        logger.info(f"  {cn}: {count}")

    return paths, labels


class EyeDiseaseDataset(Dataset):
    """Dataset with Albumentations augmentation pipeline."""

    def __init__(self, paths, labels, img_size, augment=False):
        self.paths = paths
        self.labels = labels
        self.img_size = img_size

        if augment:
            self.transform = A.Compose([
                A.Resize(img_size, img_size),
                A.HorizontalFlip(p=0.5),
                A.VerticalFlip(p=0.3),
                A.RandomRotate90(p=0.3),
                A.ShiftScaleRotate(
                    shift_limit=0.1, scale_limit=0.15, rotate_limit=30,
                    border_mode=0, p=0.5
                ),
                A.OneOf([
                    A.ElasticTransform(alpha=60, sigma=60 * 0.05, p=1.0),
                    A.GridDistortion(p=1.0),
                    A.OpticalDistortion(distort_limit=0.1, p=1.0),
                ], p=0.3),
                A.OneOf([
                    A.CLAHE(clip_limit=3.0, p=1.0),
                    A.RandomBrightnessContrast(
                        brightness_limit=0.2, contrast_limit=0.2, p=1.0
                    ),
                    A.ColorJitter(
                        brightness=0.15, contrast=0.15, saturation=0.15, hue=0.05, p=1.0
                    ),
                ], p=0.5),
                A.GaussNoise(var_limit=(5.0, 25.0), p=0.2),
                A.CoarseDropout(
                    max_holes=4, max_height=img_size // 10, max_width=img_size // 10,
                    min_holes=1, p=0.3
                ),
                A.Normalize(mean=Cfg.MEAN, std=Cfg.STD),
                ToTensorV2(),
            ])
        else:
            self.transform = A.Compose([
                A.Resize(img_size, img_size),
                A.Normalize(mean=Cfg.MEAN, std=Cfg.STD),
                ToTensorV2(),
            ])

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        img = Image.open(self.paths[idx]).convert('RGB')
        img_np = np.array(img)
        augmented = self.transform(image=img_np)
        tensor = augmented['image']
        label = self.labels[idx]
        return tensor, label


def get_tta_transforms(img_size: int) -> list:
    """Return a list of TTA transforms for evaluation."""
    base_norm = A.Compose([
        A.Resize(img_size, img_size),
        A.Normalize(mean=Cfg.MEAN, std=Cfg.STD),
        ToTensorV2(),
    ])
    tta_list = [base_norm]

    tta_list.append(A.Compose([
        A.Resize(img_size, img_size),
        A.HorizontalFlip(p=1.0),
        A.Normalize(mean=Cfg.MEAN, std=Cfg.STD),
        ToTensorV2(),
    ]))
    tta_list.append(A.Compose([
        A.Resize(img_size, img_size),
        A.VerticalFlip(p=1.0),
        A.Normalize(mean=Cfg.MEAN, std=Cfg.STD),
        ToTensorV2(),
    ]))
    tta_list.append(A.Compose([
        A.Resize(int(img_size * 1.1), int(img_size * 1.1)),
        A.CenterCrop(img_size, img_size),
        A.Normalize(mean=Cfg.MEAN, std=Cfg.STD),
        ToTensorV2(),
    ]))
    tta_list.append(A.Compose([
        A.Resize(img_size, img_size),
        A.HorizontalFlip(p=1.0),
        A.RandomRotate90(p=1.0),
        A.Normalize(mean=Cfg.MEAN, std=Cfg.STD),
        ToTensorV2(),
    ]))

    return tta_list


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 4: MODEL CREATION
# ═══════════════════════════════════════════════════════════════════════════════

def create_model(model_name: str, model_cfg: dict, num_classes: int) -> nn.Module:
    """Create a timm model with pretrained ImageNet weights and custom head."""
    model = timm.create_model(
        model_cfg['timm_name'],
        pretrained=True,
        num_classes=num_classes,
        drop_rate=model_cfg['drop_rate'],
    )
    logger.info(
        f"Created {model_name}: "
        f"{sum(p.numel() for p in model.parameters()):,} total params, "
        f"{sum(p.numel() for p in model.parameters() if p.requires_grad):,} trainable"
    )
    return model


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 5: TRAINING LOOP
# ═══════════════════════════════════════════════════════════════════════════════

def get_class_weights(labels: list) -> torch.Tensor:
    """Compute inverse-frequency class weights for balanced sampling."""
    counter = Counter(labels)
    total = len(labels)
    weights = torch.zeros(Cfg.NUM_CLASSES)
    for cls_idx in range(Cfg.NUM_CLASSES):
        if counter[cls_idx] > 0:
            weights[cls_idx] = total / (Cfg.NUM_CLASSES * counter[cls_idx])
    return weights


def get_weighted_sampler(labels: list) -> WeightedRandomSampler:
    """Create a WeightedRandomSampler for balanced batches."""
    counter = Counter(labels)
    class_weight = {c: len(labels) / count for c, count in counter.items()}
    sample_weights = [class_weight[l] for l in labels]
    return WeightedRandomSampler(sample_weights, len(sample_weights), replacement=True)


def train_one_model(
    model_name: str,
    model_cfg: dict,
    train_paths: list,
    train_labels: list,
    val_paths: list,
    val_labels: list,
    device: torch.device,
) -> tuple:
    """Train a single model. Returns (best_model_state_dict, best_metrics)."""

    logger.info(f"\n{'='*70}")
    logger.info(f"TRAINING: {model_name}")
    logger.info(f"{'='*70}")

    img_size = model_cfg['img_size']
    batch_size = model_cfg['batch_size']
    epochs = model_cfg['epochs']

    # ── Datasets & DataLoaders ───────────────────────────────────────────
    train_ds = EyeDiseaseDataset(train_paths, train_labels, img_size, augment=True)
    val_ds = EyeDiseaseDataset(val_paths, val_labels, img_size, augment=False)

    sampler = get_weighted_sampler(train_labels)
    train_loader = DataLoader(
        train_ds, batch_size=batch_size, sampler=sampler,
        num_workers=Cfg.NUM_WORKERS, pin_memory=True, drop_last=True,
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size * 2, shuffle=False,
        num_workers=Cfg.NUM_WORKERS, pin_memory=True,
    )

    # ── Model ────────────────────────────────────────────────────────────
    model = create_model(model_name, model_cfg, Cfg.NUM_CLASSES)
    model.to(device)

    # ── Loss with class weights ──────────────────────────────────────────
    class_weights = get_class_weights(train_labels).to(device)
    criterion = nn.CrossEntropyLoss(
        weight=class_weights, label_smoothing=Cfg.LABEL_SMOOTHING
    )

    # ── Optimizer ────────────────────────────────────────────────────────
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=model_cfg['lr'],
        weight_decay=model_cfg['weight_decay'],
    )

    # ── LR Scheduler (cosine with warmup) ────────────────────────────────
    total_steps = epochs * len(train_loader)
    warmup_steps = Cfg.WARMUP_EPOCHS * len(train_loader)

    def lr_lambda(step):
        if step < warmup_steps:
            return step / max(1, warmup_steps)
        progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        return max(Cfg.MIN_LR / model_cfg['lr'], 0.5 * (1 + math.cos(math.pi * progress)))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

    # ── AMP ──────────────────────────────────────────────────────────────
    _device_str = 'cuda' if torch.cuda.is_available() else 'cpu'
    scaler = GradScaler(_device_str) if _AMP_DEVICE else GradScaler()

    # ── Training Loop ────────────────────────────────────────────────────
    best_f1 = 0.0
    best_acc = 0.0
    best_state = None
    patience_counter = 0
    history = {'train_loss': [], 'train_acc': [], 'val_loss': [], 'val_acc': [], 'val_f1': []}

    for epoch in range(1, epochs + 1):
        # ── Train ────────────────────────────────────────────────────────
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for batch_idx, (images, targets) in enumerate(train_loader):
            images, targets = images.to(device), targets.to(device)

            optimizer.zero_grad(set_to_none=True)
            _ac_ctx = autocast(_device_str) if _AMP_DEVICE else autocast()
            with _ac_ctx:
                outputs = model(images)
                loss = criterion(outputs, targets)

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(model.parameters(), Cfg.GRAD_CLIP)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()

            train_loss += loss.item() * images.size(0)
            preds = outputs.argmax(dim=1)
            train_correct += (preds == targets).sum().item()
            train_total += targets.size(0)

        train_loss /= train_total
        train_acc = train_correct / train_total

        # ── Validate ─────────────────────────────────────────────────────
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        all_preds = []
        all_targets = []

        with torch.no_grad():
            for images, targets in val_loader:
                images, targets = images.to(device), targets.to(device)
                _ac_ctx2 = autocast(_device_str) if _AMP_DEVICE else autocast()
                with _ac_ctx2:
                    outputs = model(images)
                    loss = criterion(outputs, targets)

                val_loss += loss.item() * images.size(0)
                preds = outputs.argmax(dim=1)
                val_correct += (preds == targets).sum().item()
                val_total += targets.size(0)
                all_preds.extend(preds.cpu().numpy())
                all_targets.extend(targets.cpu().numpy())

        val_loss /= val_total
        val_acc = val_correct / val_total
        val_f1 = f1_score(all_targets, all_preds, average='macro')

        history['train_loss'].append(train_loss)
        history['train_acc'].append(train_acc)
        history['val_loss'].append(val_loss)
        history['val_acc'].append(val_acc)
        history['val_f1'].append(val_f1)

        # ── Logging ──────────────────────────────────────────────────────
        lr_now = optimizer.param_groups[0]['lr']
        improved = ''
        if val_f1 > best_f1 + Cfg.MIN_DELTA:
            best_f1 = val_f1
            best_acc = val_acc
            best_state = copy.deepcopy(model.state_dict())
            patience_counter = 0
            improved = '  ★ Best!'
        else:
            patience_counter += 1

        logger.info(
            f"  [{model_name}] Ep {epoch:02d}/{epochs} | "
            f"Tr: {train_loss:.4f}/{train_acc*100:.1f}% | "
            f"Va: {val_loss:.4f}/{val_acc*100:.1f}% | "
            f"F1: {val_f1*100:.1f}% | "
            f"LR: {lr_now:.1e}{improved}"
        )

        # ── Early stopping ───────────────────────────────────────────────
        if patience_counter >= Cfg.PATIENCE:
            logger.info(f"  [{model_name}] Early stopping at epoch {epoch}")
            break

    # Clean up
    del model, optimizer, scheduler, scaler
    gc.collect()
    torch.cuda.empty_cache()

    return best_state, {
        'model_name': model_name,
        'best_acc': best_acc,
        'best_f1': best_f1,
        'history': history,
        'img_size': img_size,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 6: EVALUATION & TTA
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_single_model(
    model: nn.Module,
    model_name: str,
    img_size: int,
    test_paths: list,
    test_labels: list,
    device: torch.device,
    use_tta: bool = True,
) -> tuple:
    """Evaluate a single model with optional TTA. Returns (predictions, probabilities)."""
    model.eval()

    if use_tta:
        tta_transforms = get_tta_transforms(img_size)
    else:
        tta_transforms = [A.Compose([
            A.Resize(img_size, img_size),
            A.Normalize(mean=Cfg.MEAN, std=Cfg.STD),
            ToTensorV2(),
        ])]

    all_probs = []

    with torch.no_grad():
        for path in test_paths:
            img = Image.open(path).convert('RGB')
            img_np = np.array(img)

            view_probs = []
            _dev_str = 'cuda' if torch.cuda.is_available() else 'cpu'
            for t in tta_transforms:
                tensor = t(image=img_np)['image'].unsqueeze(0).to(device)
                _ac = autocast(_dev_str) if _AMP_DEVICE else autocast()
                with _ac:
                    output = model(tensor)
                prob = F.softmax(output, dim=1)[0].cpu().numpy()
                view_probs.append(prob)

            # Average across TTA views
            avg_prob = np.mean(view_probs, axis=0)
            all_probs.append(avg_prob)

    all_probs = np.array(all_probs)
    predictions = np.argmax(all_probs, axis=1)

    return predictions, all_probs


def ensemble_evaluate(
    models_dict: dict,
    test_paths: list,
    test_labels: list,
    device: torch.device,
) -> dict:
    """Evaluate the ensemble using soft voting."""

    logger.info(f"\n{'='*70}")
    logger.info(f"ENSEMBLE EVALUATION ({len(models_dict)} models, {Cfg.TTA_VIEWS}-view TTA)")
    logger.info(f"{'='*70}")

    all_model_probs = []
    individual_results = {}

    for model_name, (model, img_size) in models_dict.items():
        logger.info(f"\n  Evaluating {model_name} (TTA={Cfg.TTA_VIEWS})...")
        preds, probs = evaluate_single_model(
            model, model_name, img_size, test_paths, test_labels, device
        )

        acc = accuracy_score(test_labels, preds)
        f1 = f1_score(test_labels, preds, average='macro')
        logger.info(f"  {model_name}: Acc={acc*100:.2f}% | F1={f1*100:.2f}%")

        report = classification_report(
            test_labels, preds,
            target_names=Cfg.CLASS_NAMES, digits=4, output_dict=True
        )
        individual_results[model_name] = {
            'accuracy': acc,
            'f1': f1,
            'predictions': preds,
            'probabilities': probs,
            'report': report,
        }
        all_model_probs.append(probs)

    # ── Soft voting ensemble ─────────────────────────────────────────────
    ensemble_probs = np.mean(all_model_probs, axis=0)
    ensemble_preds = np.argmax(ensemble_probs, axis=1)

    ensemble_acc = accuracy_score(test_labels, ensemble_preds)
    ensemble_f1 = f1_score(test_labels, ensemble_preds, average='macro')

    logger.info(f"\n{'─'*70}")
    logger.info(f"  ENSEMBLE (soft voting): Acc={ensemble_acc*100:.2f}% | F1={ensemble_f1*100:.2f}%")
    logger.info(f"{'─'*70}")

    # Detailed report
    print("\n" + classification_report(
        test_labels, ensemble_preds,
        target_names=Cfg.CLASS_NAMES, digits=4
    ))

    return {
        'individual': individual_results,
        'ensemble_acc': ensemble_acc,
        'ensemble_f1': ensemble_f1,
        'ensemble_preds': ensemble_preds,
        'ensemble_probs': ensemble_probs,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 7: SAMPLE IMAGE TESTING
# ═══════════════════════════════════════════════════════════════════════════════

def extract_label_from_filename(fname: str) -> str:
    """Extract the expected class from the test image filename."""
    fl = fname.lower()
    if 'cataract' in fl:
        return 'Cataract'
    elif 'diabeticretinopathy' in fl or 'diabret' in fl or 'diab_ret' in fl:
        return 'Diabetic_Retinopathy'
    elif 'glaucoma' in fl:
        return 'Glaucoma'
    elif 'normal' in fl:
        return 'Normal'
    return 'Unknown'


def test_on_sample_images(
    models_dict: dict,
    sample_dir: str,
    device: torch.device,
) -> dict:
    """Test ensemble on user-provided sample fundus images."""

    if not os.path.isdir(sample_dir):
        logger.info(f"Sample test directory not found: {sample_dir}")
        return {}

    image_files = sorted([
        f for f in os.listdir(sample_dir)
        if f.lower().split('.')[-1] in ('jpg', 'jpeg', 'png', 'bmp', 'tiff', 'webp')
    ])

    if not image_files:
        logger.info("No sample test images found.")
        return {}

    logger.info(f"\n{'='*70}")
    logger.info(f"SAMPLE IMAGE TEST ({len(image_files)} images, ensemble + {Cfg.TTA_VIEWS}-view TTA)")
    logger.info(f"{'='*70}")

    correct = 0
    total = 0
    results = []

    for fname in image_files:
        fpath = os.path.join(sample_dir, fname)
        expected = extract_label_from_filename(fname)
        img = Image.open(fpath).convert('RGB')
        img_np = np.array(img)

        # Ensemble prediction
        model_probs = []
        for model_name, (model, img_size) in models_dict.items():
            model.eval()
            tta_transforms = get_tta_transforms(img_size)
            view_probs = []

            _dev_str2 = 'cuda' if torch.cuda.is_available() else 'cpu'
            with torch.no_grad():
                for t in tta_transforms:
                    tensor = t(image=img_np)['image'].unsqueeze(0).to(device)
                    _ac2 = autocast(_dev_str2) if _AMP_DEVICE else autocast()
                    with _ac2:
                        output = model(tensor)
                    prob = F.softmax(output, dim=1)[0].cpu().numpy()
                    view_probs.append(prob)

            avg_prob = np.mean(view_probs, axis=0)
            model_probs.append(avg_prob)

        # Soft voting
        ensemble_prob = np.mean(model_probs, axis=0)
        pred_idx = np.argmax(ensemble_prob)
        pred_label = Cfg.CLASS_NAMES[pred_idx]
        confidence = ensemble_prob[pred_idx] * 100

        is_correct = pred_label == expected
        if expected != 'Unknown':
            total += 1
            if is_correct:
                correct += 1

        status = '✅' if is_correct else '❌'
        results.append({
            'file': fname,
            'expected': expected,
            'predicted': pred_label,
            'confidence': confidence,
            'correct': is_correct,
        })

        logger.info(
            f"  {fname:50s} Expected: {expected:25s} → "
            f"Predicted: {pred_label:25s} ({confidence:.1f}%) {status}"
        )

    if total > 0:
        sample_acc = correct / total * 100
        logger.info(f"\n{'─'*70}")
        logger.info(f"  Sample Test Accuracy: {correct}/{total} = {sample_acc:.1f}%")
        logger.info(f"{'─'*70}")

    return {
        'results': results,
        'correct': correct,
        'total': total,
        'accuracy': correct / total * 100 if total > 0 else 0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 8: VISUALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

def plot_training_history(all_histories: dict, output_dir: str):
    """Plot training curves for all models."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Ensemble Training History', fontsize=16, fontweight='bold')

    colors = {'efficientnet_b3': '#2196F3', 'densenet121': '#4CAF50', 'inception_resnet_v2': '#FF9800'}

    for model_name, metrics in all_histories.items():
        color = colors.get(model_name, '#9E9E9E')
        history = metrics['history']
        epochs = range(1, len(history['train_loss']) + 1)

        axes[0, 0].plot(epochs, history['train_loss'], '-', color=color, label=f'{model_name} (train)')
        axes[0, 0].plot(epochs, history['val_loss'], '--', color=color, label=f'{model_name} (val)')

        axes[0, 1].plot(epochs, [a * 100 for a in history['train_acc']], '-', color=color, label=f'{model_name} (train)')
        axes[0, 1].plot(epochs, [a * 100 for a in history['val_acc']], '--', color=color, label=f'{model_name} (val)')

        axes[1, 0].plot(epochs, [f * 100 for f in history['val_f1']], '-o', color=color, label=model_name, markersize=3)

    axes[0, 0].set_title('Loss'); axes[0, 0].set_xlabel('Epoch'); axes[0, 0].set_ylabel('Loss')
    axes[0, 0].legend(fontsize=7); axes[0, 0].grid(True, alpha=0.3)
    axes[0, 1].set_title('Accuracy'); axes[0, 1].set_xlabel('Epoch'); axes[0, 1].set_ylabel('Accuracy (%)')
    axes[0, 1].legend(fontsize=7); axes[0, 1].grid(True, alpha=0.3)
    axes[1, 0].set_title('Validation F1 Score'); axes[1, 0].set_xlabel('Epoch'); axes[1, 0].set_ylabel('F1 (%)')
    axes[1, 0].legend(fontsize=8); axes[1, 0].grid(True, alpha=0.3)

    # Model comparison bar chart
    model_names = list(all_histories.keys())
    accs = [all_histories[m]['best_acc'] * 100 for m in model_names]
    f1s = [all_histories[m]['best_f1'] * 100 for m in model_names]
    x = np.arange(len(model_names))
    w = 0.35
    axes[1, 1].bar(x - w/2, accs, w, label='Accuracy', color='#2196F3', alpha=0.8)
    axes[1, 1].bar(x + w/2, f1s, w, label='F1 Score', color='#FF9800', alpha=0.8)
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels([n.replace('_', '\n') for n in model_names], fontsize=8)
    axes[1, 1].set_title('Individual Model Performance')
    axes[1, 1].set_ylabel('%')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'training_history.png'), dpi=150, bbox_inches='tight')
    plt.show()
    plt.close()


def plot_confusion_matrix(y_true, y_pred, title, output_dir, filename='confusion_matrix.png'):
    """Plot and save confusion matrix."""
    cm = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(8, 7))
    sns.heatmap(
        cm, annot=True, fmt='d', cmap='Blues',
        xticklabels=Cfg.CLASS_NAMES, yticklabels=Cfg.CLASS_NAMES, ax=ax
    )
    ax.set_xlabel('Predicted', fontsize=12)
    ax.set_ylabel('Actual', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, filename), dpi=150, bbox_inches='tight')
    plt.show()
    plt.close()


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 9: SAVE ENSEMBLE CHECKPOINT
# ═══════════════════════════════════════════════════════════════════════════════

def save_ensemble_checkpoint(
    model_states: dict,
    model_configs: dict,
    metrics: dict,
    output_dir: str,
):
    """Save all three model weights in a single ensemble checkpoint."""
    os.makedirs(output_dir, exist_ok=True)

    # Save individual models
    for model_name, state_dict in model_states.items():
        path = os.path.join(output_dir, f'{model_name}.pth')
        torch.save({
            'model_state_dict': state_dict,
            'model_name': model_name,
            'timm_name': model_configs[model_name]['timm_name'],
            'img_size': model_configs[model_name]['img_size'],
            'num_classes': Cfg.NUM_CLASSES,
            'classes': Cfg.CLASS_NAMES,
            'id2label': {str(i): c for i, c in enumerate(Cfg.CLASS_NAMES)},
        }, path)
        size_mb = os.path.getsize(path) / (1024**2)
        logger.info(f"  Saved {model_name}: {path} ({size_mb:.1f} MB)")

    # Save combined ensemble checkpoint (all 3 in one file)
    ensemble_path = os.path.join(output_dir, 'ensemble_classifier.pth')
    ensemble_ckpt = {
        'ensemble_type': 'soft_voting',
        'num_models': len(model_states),
        'num_classes': Cfg.NUM_CLASSES,
        'classes': Cfg.CLASS_NAMES,
        'id2label': {str(i): c for i, c in enumerate(Cfg.CLASS_NAMES)},
        'models': {},
    }
    for model_name, state_dict in model_states.items():
        ensemble_ckpt['models'][model_name] = {
            'model_state_dict': state_dict,
            'timm_name': model_configs[model_name]['timm_name'],
            'img_size': model_configs[model_name]['img_size'],
        }
    if metrics:
        ensemble_ckpt['ensemble_accuracy'] = metrics.get('ensemble_acc', 0)
        ensemble_ckpt['ensemble_f1'] = metrics.get('ensemble_f1', 0)
        ensemble_ckpt['individual_metrics'] = {
            name: {'accuracy': r['accuracy'], 'f1': r['f1']}
            for name, r in metrics.get('individual', {}).items()
        }

    torch.save(ensemble_ckpt, ensemble_path)
    size_mb = os.path.getsize(ensemble_path) / (1024**2)
    logger.info(f"\n  ★ Saved ENSEMBLE checkpoint: {ensemble_path} ({size_mb:.1f} MB)")

    # Save metrics JSON
    metrics_json = {
        'ensemble_accuracy': metrics.get('ensemble_acc', 0) if metrics else 0,
        'ensemble_f1': metrics.get('ensemble_f1', 0) if metrics else 0,
        'individual': {},
    }
    if metrics and 'individual' in metrics:
        for name, r in metrics['individual'].items():
            metrics_json['individual'][name] = {
                'accuracy': float(r['accuracy']),
                'f1': float(r['f1']),
            }
    with open(os.path.join(output_dir, 'metrics.json'), 'w') as f:
        json.dump(metrics_json, f, indent=2)

    return ensemble_path


# ═══════════════════════════════════════════════════════════════════════════════
# CELL 10: MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main training and evaluation pipeline."""
    start_time = time.time()

    # ── Setup ────────────────────────────────────────────────────────────
    os.makedirs(Cfg.OUTPUT_DIR, exist_ok=True)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"Device: {device}")
    if torch.cuda.is_available():
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
        logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    # ── Seed ─────────────────────────────────────────────────────────────
    seed = 42
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    # ── Discover dataset ─────────────────────────────────────────────────
    # Smart path discovery: walk the Kaggle input tree and find whichever
    # directory actually contains the class sub-folders (Normal / cataract /
    # diabetic_retinopathy / glaucoma).  This works regardless of how Kaggle
    # structures the mounted dataset (flat, nested, differently named root).
    CLASS_KEYWORDS = ['normal', 'diab', 'glauc', 'catar', 'retin', 'dr']

    def _has_class_dirs(path: str) -> bool:
        """Return True if path contains ≥2 subdirectories matching class keywords."""
        try:
            subdirs = [d.lower() for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
        except PermissionError:
            return False
        matches = sum(1 for d in subdirs if any(kw in d for kw in CLASS_KEYWORDS))
        return matches >= 2

    def _find_dataset_dir(root: str, max_depth: int = 4) -> str | None:
        """Recursively search root up to max_depth for the directory containing class folders."""
        if _has_class_dirs(root):
            return root
        if max_depth == 0:
            return None
        try:
            for entry in os.scandir(root):
                if entry.is_dir():
                    found = _find_dataset_dir(entry.path, max_depth - 1)
                    if found:
                        return found
        except PermissionError:
            pass
        return None

    # Print Kaggle input tree to help debug if needed
    kaggle_input = '/kaggle/input'
    logger.info(f"Searching for dataset inside {kaggle_input} ...")
    try:
        for top in os.listdir(kaggle_input):
            top_path = os.path.join(kaggle_input, top)
            if os.path.isdir(top_path):
                logger.info(f"  Found mounted dataset: {top_path}/")
                for sub in os.listdir(top_path)[:8]:  # show first 8 entries
                    logger.info(f"    └── {sub}")
    except Exception:
        pass

    dataset_dir = _find_dataset_dir(kaggle_input)

    if not dataset_dir:
        raise FileNotFoundError(
            "Could not locate class folders (Normal/cataract/glaucoma/diabetic_retinopathy) "
            f"anywhere under {kaggle_input}. "
            "Make sure you have added 'gunavenkatdoddi/eye-diseases-classification' "
            "as a Kaggle dataset in the right sidebar → Add Data."
        )
    logger.info(f"✅ Dataset found at: {dataset_dir}")

    paths, labels = discover_dataset(dataset_dir)

    # ── Train/Val/Test Split (70/15/15) ──────────────────────────────────
    train_paths, temp_paths, train_labels, temp_labels = train_test_split(
        paths, labels, test_size=0.30, random_state=seed, stratify=labels
    )
    val_paths, test_paths, val_labels, test_labels = train_test_split(
        temp_paths, temp_labels, test_size=0.50, random_state=seed, stratify=temp_labels
    )

    logger.info(f"\nSplit: Train={len(train_paths)} | Val={len(val_paths)} | Test={len(test_paths)}")
    logger.info(f"Train distribution: {Counter(train_labels)}")
    logger.info(f"Val   distribution: {Counter(val_labels)}")
    logger.info(f"Test  distribution: {Counter(test_labels)}")

    # ── Train all models ─────────────────────────────────────────────────
    model_states = {}
    all_histories = {}

    for model_name, model_cfg in Cfg.MODELS.items():
        state_dict, metrics = train_one_model(
            model_name, model_cfg,
            train_paths, train_labels,
            val_paths, val_labels,
            device,
        )
        model_states[model_name] = state_dict
        all_histories[model_name] = metrics
        logger.info(
            f"\n  ✅ {model_name} training complete: "
            f"Acc={metrics['best_acc']*100:.2f}% | F1={metrics['best_f1']*100:.2f}%"
        )

    # ── Plot training history ────────────────────────────────────────────
    plot_training_history(all_histories, Cfg.OUTPUT_DIR)

    # ── Load best models for evaluation ──────────────────────────────────
    models_for_eval = {}
    for model_name, model_cfg in Cfg.MODELS.items():
        model = create_model(model_name, model_cfg, Cfg.NUM_CLASSES)
        model.load_state_dict(model_states[model_name])
        model.to(device)
        model.eval()
        models_for_eval[model_name] = (model, model_cfg['img_size'])

    # ── Evaluate on test set ─────────────────────────────────────────────
    eval_results = ensemble_evaluate(models_for_eval, test_paths, test_labels, device)

    # ── Confusion matrices ───────────────────────────────────────────────
    plot_confusion_matrix(
        test_labels, eval_results['ensemble_preds'],
        f"Ensemble Confusion Matrix (Acc={eval_results['ensemble_acc']*100:.2f}%)",
        Cfg.OUTPUT_DIR, 'ensemble_confusion_matrix.png'
    )
    for model_name, res in eval_results['individual'].items():
        plot_confusion_matrix(
            test_labels, res['predictions'],
            f"{model_name} (Acc={res['accuracy']*100:.2f}%)",
            Cfg.OUTPUT_DIR, f'{model_name}_confusion_matrix.png'
        )

    # ── Save checkpoint ──────────────────────────────────────────────────
    ensemble_path = save_ensemble_checkpoint(
        model_states, Cfg.MODELS, eval_results, Cfg.OUTPUT_DIR
    )

    # ── Test on sample images ────────────────────────────────────────────
    sample_test_dir = Cfg.SAMPLE_TEST_DIR
    if not os.path.isdir(sample_test_dir):
        # Try alternative paths
        alt_sample_paths = [
            '/kaggle/input/sample-fundus-tests',
            '/kaggle/input/sample-fundus-tests/sample_fundus_tests',
        ]
        for alt in alt_sample_paths:
            if os.path.isdir(alt):
                sample_test_dir = alt
                break

    sample_results = test_on_sample_images(models_for_eval, sample_test_dir, device)

    # ── Final Summary ────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    logger.info(f"\n{'═'*70}")
    logger.info(f"  FINAL SUMMARY")
    logger.info(f"{'═'*70}")
    logger.info(f"  Total training time: {elapsed/60:.1f} minutes")
    logger.info(f"")
    logger.info(f"  Individual Model Results:")
    for model_name, res in eval_results['individual'].items():
        logger.info(f"    {model_name:30s} Acc={res['accuracy']*100:.2f}%  F1={res['f1']*100:.2f}%")
    logger.info(f"")
    logger.info(f"  ★ ENSEMBLE Result:             Acc={eval_results['ensemble_acc']*100:.2f}%  F1={eval_results['ensemble_f1']*100:.2f}%")
    if sample_results:
        logger.info(f"  ★ Sample Image Test:           {sample_results.get('correct', 0)}/{sample_results.get('total', 0)} = {sample_results.get('accuracy', 0):.1f}%")
    logger.info(f"")
    logger.info(f"  Checkpoint saved to: {ensemble_path}")
    logger.info(f"{'═'*70}")

    # Clean up GPU memory
    for model_name in list(models_for_eval.keys()):
        del models_for_eval[model_name]
    gc.collect()
    torch.cuda.empty_cache()

    return eval_results, sample_results


# ═══════════════════════════════════════════════════════════════════════════════
# RUN: In Cell 2, just do: result, test_res = main()
# ═══════════════════════════════════════════════════════════════════════════════
