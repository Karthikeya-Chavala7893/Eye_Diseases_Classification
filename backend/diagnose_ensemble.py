"""
Diagnostic script to debug ensemble predictions.
Checks: label mapping, raw probabilities from each sub-model, crop_retina_circle effect.
"""
import os, sys, json
import torch
import torch.nn.functional as F
import timm
import numpy as np
from PIL import Image
from torchvision import transforms

# ── Load checkpoint ──────────────────────────────────────────────────────────
CKPT_PATH = os.path.join(os.path.dirname(__file__), 'models', 'ensemble_classifier.pth')
TEST_DIR = r'C:\Users\chkar\Desktop\Eye_Diseases_Classification\Test images\sample_fundus_tests'

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

print("=" * 80)
print("ENSEMBLE DIAGNOSTIC TOOL")
print("=" * 80)

# ── 1. Inspect checkpoint metadata ──────────────────────────────────────────
print("\n[1] CHECKPOINT METADATA")
print("-" * 40)
ckpt = torch.load(CKPT_PATH, map_location='cpu', weights_only=False)

print(f"  Top-level keys: {list(ckpt.keys())}")
print(f"  ensemble_type:  {ckpt.get('ensemble_type')}")
print(f"  num_models:     {ckpt.get('num_models')}")
print(f"  num_classes:    {ckpt.get('num_classes')}")
print(f"  classes:        {ckpt.get('classes')}")
print(f"  id2label:       {ckpt.get('id2label')}")
print(f"  ensemble_acc:   {ckpt.get('ensemble_accuracy')}")
print(f"  ensemble_f1:    {ckpt.get('ensemble_f1')}")

id2label = ckpt.get('id2label', {})
classes = ckpt.get('classes', [])
print(f"\n  id2label mapping:")
for k, v in sorted(id2label.items(), key=lambda x: int(x[0])):
    print(f"    Index {k} → '{v}'")

# ── 2. Check what the TRAINING script used as class order ────────────────────
print("\n[2] TRAINING CLASS ORDER vs CHECKPOINT CLASS ORDER")
print("-" * 40)
# The training script used: CLASS_NAMES = ['Normal', 'Diabetic_Retinopathy', 'Glaucoma', 'Cataract']
# But discover_dataset() sorted the folder names alphabetically first:
# sorted(['Normal', 'Diabetic_Retinopathy', 'Glaucoma', 'Cataract']) 
# would depend on the actual folder names in the dataset.

# Let's check what the ACTUAL folder names in the dataset are.
# The gunavenkatdoddi dataset typically has: cataract, diabetic_retinopathy, glaucoma, normal
# When sorted alphabetically: cataract(0), diabetic_retinopathy(1), glaucoma(2), normal(3)
# But Cfg.CLASS_NAMES was: ['Normal'(0), 'Diabetic_Retinopathy'(1), 'Glaucoma'(2), 'Cataract'(3)]

# The discover_dataset function maps folders to CLASS_NAMES indices like this:
# folder_to_idx maps each folder name to the Cfg.CLASS_NAMES index
# So if folder is "cataract" → maps to index 3 (Cataract in CLASS_NAMES)
# If folder is "glaucoma" → maps to index 2 (Glaucoma in CLASS_NAMES)
# etc.

# The id2label from checkpoint should tell us:
print(f"  Checkpoint id2label: {id2label}")
print(f"  Checkpoint classes:  {classes}")
print()

# ── 3. Load models and run inference ────────────────────────────────────────
print("\n[3] LOADING SUB-MODELS")
print("-" * 40)

device = torch.device('cpu')
models_data = ckpt.get('models', {})
loaded_models = {}

for model_name, model_data in models_data.items():
    timm_name = model_data['timm_name']
    img_size = model_data.get('img_size', 224)
    state_dict = model_data['model_state_dict']
    num_classes = ckpt.get('num_classes', 4)

    sub_model = timm.create_model(timm_name, pretrained=False, num_classes=num_classes)
    sub_model.load_state_dict(state_dict)
    sub_model.eval()
    
    loaded_models[model_name] = (sub_model, img_size)
    print(f"  ✅ {model_name}: timm={timm_name}, img_size={img_size}")


# ── 4. Test each image ─────────────────────────────────────────────────────
print("\n[4] INFERENCE ON TEST IMAGES")
print("=" * 80)

test_images = [
    'Bilateral_OD_Cataract_01.jpg',     # Expected: Cataract
    'Bilateral_OS_Normal_01.jpg',        # Expected: Normal
    'Bilateral_OS_Cataract_01.jpg',      # Expected: Cataract
    'DiabRet_Test_3.jpg',                # Expected: Diabetic Retinopathy
    'Normal_Retina_Test_4.jpg',          # Expected: Normal
]

for fname in test_images:
    fpath = os.path.join(TEST_DIR, fname)
    if not os.path.isfile(fpath):
        print(f"\n  ⚠️  File not found: {fpath}")
        continue
    
    img = Image.open(fpath).convert('RGB')
    print(f"\n{'─'*80}")
    print(f"  Image: {fname}")
    print(f"  Original size: {img.size}")
    
    # Test with AND without crop_retina_circle
    for use_crop in [False, True]:
        if use_crop:
            # Apply the same cropping as model.py
            img_np = np.array(img)
            gray = np.mean(img_np[:, :, :3], axis=2)
            mask = gray > 15
            if np.any(mask):
                row_sum = np.sum(mask, axis=1)
                col_sum = np.sum(mask, axis=0)
                y_idx = np.where(row_sum > 0)[0]
                x_idx = np.where(col_sum > 0)[0]
                if len(y_idx) > 0 and len(x_idx) > 0:
                    y_min, y_max = y_idx[0], y_idx[-1]
                    x_min, x_max = x_idx[0], x_idx[-1]
                    side = max(y_max - y_min, x_max - x_min)
                    cy, cx = (y_min + y_max) // 2, (x_min + x_max) // 2
                    y1 = max(0, cy - side // 2)
                    y2 = min(img_np.shape[0], cy + side // 2)
                    x1 = max(0, cx - side // 2)
                    x2 = min(img_np.shape[1], cx + side // 2)
                    test_img = Image.fromarray(img_np[y1:y2, x1:x2])
                else:
                    test_img = img
            else:
                test_img = img
            crop_label = "WITH crop"
        else:
            test_img = img
            crop_label = "NO crop  "
        
        # Run each sub-model
        all_probs = []
        for model_name, (sub_model, img_size) in loaded_models.items():
            t = transforms.Compose([
                transforms.Resize((img_size, img_size)),
                transforms.ToTensor(),
                transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            ])
            tensor = t(test_img).unsqueeze(0)
            
            with torch.no_grad():
                logits = sub_model(tensor)
                probs = F.softmax(logits, dim=-1)[0].numpy()
            
            all_probs.append(probs)
            pred_idx = np.argmax(probs)
            pred_label = id2label.get(str(pred_idx), f'Class_{pred_idx}')
            
            prob_str = "  ".join([
                f"{id2label.get(str(i), f'C{i}')}:{probs[i]*100:.1f}%"
                for i in range(len(probs))
            ])
            print(f"    [{crop_label}] {model_name:25s} → {pred_label:25s} | {prob_str}")
        
        # Ensemble
        ensemble_probs = np.mean(all_probs, axis=0)
        ens_pred_idx = np.argmax(ensemble_probs)
        ens_pred_label = id2label.get(str(ens_pred_idx), f'Class_{ens_pred_idx}')
        ens_conf = ensemble_probs[ens_pred_idx] * 100
        
        prob_str = "  ".join([
            f"{id2label.get(str(i), f'C{i}')}:{ensemble_probs[i]*100:.1f}%"
            for i in range(len(ensemble_probs))
        ])
        print(f"    [{crop_label}] {'★ ENSEMBLE':25s} → {ens_pred_label:25s} | {prob_str}")

print(f"\n{'='*80}")
print("DIAGNOSTIC COMPLETE")
print(f"{'='*80}")
