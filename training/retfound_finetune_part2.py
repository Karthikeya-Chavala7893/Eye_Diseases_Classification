"""
RETFound ViT-Large Fine-Tuning — Part 2 (v3 — Accuracy-Boosted)
=================================================================
v3 Accuracy Boosts:
  [Boost 1] 384px resolution with interpolated position embeddings
  [Boost 2] LoRA rank 32 for more expressive adaptation
  [Boost 3] Focal Loss replaces CrossEntropy for hard-example mining
  [Boost 4] Progressive resize: 224px warmup then 384px refinement
  [Boost 5] 10-view TTA (up from 5-view)

All v2 fixes still applied:
  [Bug 2] Official RETFound VisionTransformer + interpolate_pos_embed
  [Bug 3] Gradient accumulation (effective batch=32 from batch=2 * accum=16)
  [Bug 4] AMP (torch.cuda.amp) — float16 for 2x speed
  [Bug 5] LoRA on both QKV and proj
  [Bug 6] EMA tracks only trainable params
  [Bug 7] Unfreezes backbone LayerNorm layers
  [Bug 8] Validates that pretrained weight loading didn't silently fail
"""

from retfound_finetune_part1 import *


# ═══════════════════════════════════════════════════════════════════════════════
# LoRA IMPLEMENTATION
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
    """
    [Bug 5 fix] Inject LoRA into QKV AND output projection (proj).
    LoRA on proj gives the model control over how attention outputs
    are combined — important for disease-specific feature routing.
    """
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


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL CREATION
# ═══════════════════════════════════════════════════════════════════════════════

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
        # RETFound with global_pool=False returns [B, N, D]; take CLS token
        if features.dim() == 3:
            features = features[:, 0, :]
        return self.classifier(features)


def create_model():
    """
    Build RETFound ViT-Large with all critique fixes:
    - [Bug 2] Official architecture + weight loading
    - [Bug 5] LoRA on QKV + proj
    - [Bug 7] Unfrozen LayerNorms
    - [Bug 8] Validated weight loading
    """
    # Step 1: Create backbone with OFFICIAL RETFound architecture
    backbone = vit_large_patch16(
        num_classes=cfg.NUM_CLASSES,
        drop_path_rate=cfg.DROP_PATH_RATE,
        global_pool=False,  # Use CLS token (matches backend/model.py)
    )

    # Step 2: Load pretrained weights with proper key handling
    if os.path.exists(cfg.RETFOUND_WEIGHTS):
        logger.info(f'Loading RETFound weights: {cfg.RETFOUND_WEIGHTS}')
        ckpt = torch.load(cfg.RETFOUND_WEIGHTS, map_location='cpu')
        ckpt_model = ckpt.get('model', ckpt)

        # Remove head keys (we have our own classifier)
        state_dict = backbone.state_dict()
        for k in ['head.weight', 'head.bias']:
            if k in ckpt_model and (k not in state_dict or
                                     ckpt_model[k].shape != state_dict[k].shape):
                del ckpt_model[k]

        # Remove decoder/mask keys (MAE pretraining artifacts)
        ckpt_model = {k: v for k, v in ckpt_model.items()
                      if not any(x in k for x in ['decoder', 'mask_token'])}

        # Interpolate positional embedding if needed
        interpolate_pos_embed(backbone, ckpt_model)

        # [Bug 8 fix] Load and VALIDATE
        missing, unexpected = backbone.load_state_dict(ckpt_model, strict=False)
        # Only head keys should be missing. If backbone keys are missing, something is wrong.
        backbone_missing = [k for k in missing if 'head' not in k and 'fc_norm' not in k]
        if len(backbone_missing) > 5:
            logger.error(f'WARNING: {len(backbone_missing)} backbone keys NOT loaded! '
                         f'First 5: {backbone_missing[:5]}')
            logger.error('The pretrained weights may not match this architecture.')
            raise RuntimeError(f'{len(backbone_missing)} backbone keys missing — '
                               'weight format incompatible.')
        else:
            logger.info(f'RETFound weights loaded. Missing: {len(missing)} '
                        f'(backbone: {len(backbone_missing)}), Unexpected: {len(unexpected)}')
    else:
        logger.warning('RETFound weights NOT FOUND. Training from scratch (NOT recommended).')
        logger.warning('Download: https://github.com/rmaphoh/RETFound_MAE/releases')

    # Step 3: Wrap in classifier
    model = RETFoundClassifier(backbone, num_classes=cfg.NUM_CLASSES)

    # Step 4: Freeze everything first
    for p in model.parameters():
        p.requires_grad = False

    # Step 5: Inject LoRA (creates trainable params in backbone)
    inject_lora(model.backbone)

    # Step 6: [Bug 7 fix] Unfreeze backbone LayerNorms
    norm_count = 0
    for name, param in model.backbone.named_parameters():
        if 'norm' in name or 'ln' in name:
            param.requires_grad = True
            norm_count += 1

    # Step 7: Unfreeze classifier head
    for p in model.classifier.parameters():
        p.requires_grad = True

    # Report
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f'Params: {total:,} total, {trainable:,} trainable ({trainable/total*100:.2f}%)')
    logger.info(f'  LoRA: {cfg.LORA_TARGETS}, LayerNorms unfrozen: {norm_count} params')

    return model


# ═══════════════════════════════════════════════════════════════════════════════
# [Bug 6 fix] EMA — ONLY tracks trainable parameters
# ═══════════════════════════════════════════════════════════════════════════════

class EMAModel:
    """EMA of trainable params only — saves 1.2 GB vs full model copy."""
    def __init__(self, model, decay=0.9998):
        self.decay = decay
        # Store only trainable parameter copies
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
        """Temporarily apply EMA weights for evaluation."""
        backup = {}
        for name, param in model.named_parameters():
            if name in self.shadow:
                backup[name] = param.data.clone()
                param.data.copy_(self.shadow[name])
        return backup

    def restore(self, model, backup):
        """Restore original weights after EMA evaluation."""
        for name, param in model.named_parameters():
            if name in backup:
                param.data.copy_(backup[name])


# ═══════════════════════════════════════════════════════════════════════════════
# COSINE WARMUP LR + EARLY STOPPING
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
# [Bug 3+4 fix] TRAINING LOOP with AMP + Gradient Accumulation
# ═══════════════════════════════════════════════════════════════════════════════

def train_one_epoch(model, loader, criterion, optimizer, scaler, ema, device, epoch):
    model.train()
    running_loss, correct, total = 0.0, 0, 0
    optimizer.zero_grad()

    for batch_idx, (images, labels) in enumerate(loader):
        images, labels = images.to(device), labels.to(device)

        use_mix = random.random() < cfg.MIXUP_PROB
        use_cut = random.random() < cfg.CUTMIX_PROB and not use_mix

        # [Bug 4 fix] AMP autocast
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

            # [Bug 3 fix] Scale loss for gradient accumulation
            loss = loss / cfg.GRAD_ACCUM_STEPS

        # AMP backward
        scaler.scale(loss).backward()

        # Track accuracy
        _, preds = torch.max(out, 1)
        correct += (lam * preds.eq(ya).sum().item() + (1 - lam) * preds.eq(yb).sum().item())
        total += labels.size(0)
        running_loss += loss.item() * labels.size(0) * cfg.GRAD_ACCUM_STEPS

        # [Bug 3 fix] Step optimizer every GRAD_ACCUM_STEPS
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

    # Handle leftover batches
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


# ═══════════════════════════════════════════════════════════════════════════════
# MERGE LoRA -> CHECKPOINT (compatible with backend/model.py)
# ═══════════════════════════════════════════════════════════════════════════════

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
        'img_size': sz,  # Store resolution for inference
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
# TRAINING PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def train_model(model, train_paths, train_labels, val_paths, val_labels, device):
    model = model.to(device)

    # [Bug 7 fix] Three param groups: LoRA, LayerNorms, Head
    lora_p = [p for n, p in model.named_parameters() if p.requires_grad and 'lora' in n]
    norm_p = [p for n, p in model.named_parameters()
              if p.requires_grad and 'lora' not in n and ('norm' in n or 'ln' in n)
              and 'classifier' not in n]
    head_p = [p for n, p in model.named_parameters()
              if p.requires_grad and 'classifier' in n]

    optimizer = torch.optim.AdamW([
        {'params': lora_p, 'lr': cfg.LORA_LR, 'weight_decay': cfg.WEIGHT_DECAY},
        {'params': norm_p, 'lr': cfg.NORM_LR, 'weight_decay': 0.0},  # No WD for norms
        {'params': head_p, 'lr': cfg.HEAD_LR, 'weight_decay': cfg.WEIGHT_DECAY},
    ])

    # [Boost 3] Focal Loss with class-balanced weights
    class_weights = compute_class_weights(train_labels)
    criterion = FocalLoss(
        gamma=cfg.FOCAL_GAMMA,
        alpha=class_weights,
        label_smoothing=cfg.LABEL_SMOOTHING,
        num_classes=cfg.NUM_CLASSES,
    )
    # Keep regular CE for validation (cleaner metric)
    val_criterion = nn.CrossEntropyLoss()

    scheduler = CosineWarmupScheduler(optimizer, cfg.WARMUP_EPOCHS, cfg.EPOCHS, cfg.MIN_LR)
    early_stop = EarlyStopping(cfg.PATIENCE)
    ema = EMAModel(model, cfg.EMA_DECAY)
    scaler = GradScaler(enabled=cfg.USE_AMP)

    best_acc, best_f1, best_state = 0.0, 0.0, None
    hist = {'tr_loss': [], 'tr_acc': [], 'va_loss': [], 'va_acc': [], 'va_f1': [], 'lr': []}
    current_img_size = cfg.IMG_SIZE_WARMUP  # [Boost 4] Start at 224

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
            # Clear VRAM from old resolution
            gc.collect()
            torch.cuda.empty_cache()

        scheduler.step(epoch)
        lr = scheduler.get_lr()

        trm = train_one_epoch(model, train_loader, criterion, optimizer, scaler, ema, device, epoch)
        vam = validate(model, val_loader, val_criterion, device)

        # Also validate with EMA weights
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
# FINAL EVALUATION WITH TTA
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
    fig.suptitle('RETFound + LoRA (v3 — 384px + Focal Loss)', fontsize=16, fontweight='bold')
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
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print('=' * 70)
    print('RETFound ViT-Large + LoRA Fine-Tuning (v3 — Accuracy-Boosted)')
    print(f'Device: {cfg.DEVICE}')
    if torch.cuda.is_available():
        g = torch.cuda.get_device_properties(0)
        print(f'GPU: {torch.cuda.get_device_name(0)} ({g.total_mem/1024**3:.1f} GB)')
    print(f'Boosts: 384px | LoRA r={cfg.LORA_RANK} | Focal Loss (gamma={cfg.FOCAL_GAMMA}) | Progressive Resize')
    print('=' * 70)

    # 1. Load
    paths, labels = load_dataset_from_folders(cfg.DATASET_DIR)
    if not paths:
        raise RuntimeError(f'No images in {cfg.DATASET_DIR}')
    splits = create_splits(paths, labels)

    # 2. Get split data (loaders created inside train_model for progressive resize)
    tr_p, tr_l = splits['train']
    va_p, va_l = splits['val']
    te_p, te_l = splits['test']

    # 3. Model
    model = create_model()

    # 4. Train (passes raw paths/labels for progressive resize dataloader rebuilding)
    result = train_model(model, tr_p, tr_l, va_p, va_l, cfg.DEVICE)

    # 5. TTA evaluation at final resolution (384px)
    test_res = evaluate_tta(result['model'], te_p, te_l, cfg.DEVICE, img_size=cfg.IMG_SIZE)

    # 6. Plots
    plot_results(result['history'], test_res['cm'], cfg.OUTPUT_DIR)

    # 7. Collapse check
    pred_counts = Counter(test_res['preds'])
    for ci in range(cfg.NUM_CLASSES):
        cnt = pred_counts.get(ci, 0)
        pct = cnt / len(test_res['preds']) * 100
        flag = 'OK' if pct > 5 else 'COLLAPSED!'
        logger.info(f'  {cfg.CLASS_NAMES[ci]:>25s}: {cnt} ({pct:.1f}%) {flag}')

    print('\n' + '=' * 70)
    print(f'Best Val: {result["best_acc"]:.2f}% acc, {result["best_f1"]:.2f}% F1')
    print(f'Test TTA: {test_res["acc"]:.2f}% acc, {test_res["f1"]:.2f}% F1')
    print(f'Checkpoint: {cfg.OUTPUT_DIR}/retfound_classifier.pth')
    print(f'Deploy: Copy to backend/models/retfound_classifier.pth')
    print('=' * 70)
    return result, test_res

if __name__ == '__main__':
    main()
