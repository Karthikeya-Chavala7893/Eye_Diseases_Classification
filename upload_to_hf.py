"""
upload_to_hf.py
───────────────
Helper script to upload the trained ensemble classifier checkpoint and model card
to Hugging Face Model Hub (100% Free).

Usage:
    python upload_to_hf.py --repo-id "YOUR_HF_USERNAME/visionai-retinal-ensemble" --token "YOUR_HF_WRITE_TOKEN"

Or simply run without arguments to be prompted interactively:
    python upload_to_hf.py
"""

import os
import sys
import argparse
from huggingface_hub import HfApi, create_repo

def upload_model(repo_id: str, token: str | None = None, is_private: bool = False):
    ckpt_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend", "models", "ensemble_classifier.pth"))
    readme_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend", "models", "README.md"))

    if not os.path.isfile(ckpt_path):
        print(f"❌ Error: Model checkpoint not found at: {ckpt_path}")
        sys.exit(1)

    print(f"📦 Model Checkpoint Found: {ckpt_path} ({os.path.getsize(ckpt_path) / (1024*1024):.1f} MB)")
    print(f"🚀 Target Hugging Face Repo: {repo_id}")

    api = HfApi(token=token)

    # 1. Create repo if it doesn't already exist
    print("\n[1/3] Ensuring repository exists on Hugging Face...")
    try:
        repo_url = create_repo(repo_id=repo_id, token=token, repo_type="model", private=is_private, exist_ok=True)
        print(f"  ✅ Repository ready: {repo_url}")
    except Exception as e:
        print(f"  ⚠️ Note on create_repo: {e}")

    # 2. Upload README / Model Card
    if os.path.isfile(readme_path):
        print("\n[2/3] Uploading Model Card (README.md)...")
        api.upload_file(
            path_or_fileobj=readme_path,
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="model",
            token=token,
        )
        print("  ✅ README.md uploaded successfully!")
    else:
        print("\n[2/3] Skipping README (not found).")

    # 3. Upload ensemble_classifier.pth
    print("\n[3/3] Uploading ensemble_classifier.pth (~276 MB)... This may take 1-2 minutes depending on your internet upload speed.")
    api.upload_file(
        path_or_fileobj=ckpt_path,
        path_in_repo="ensemble_classifier.pth",
        repo_id=repo_id,
        repo_type="model",
        token=token,
    )
    print("\n🎉 SUCCESS! Your model is now hosted on Hugging Face Model Hub!")
    print(f"🔗 View it at: https://huggingface.co/{repo_id}")
    print("\nYou can now proceed to Step 2 (Backend on Render)!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload ensemble model to Hugging Face Hub")
    parser.add_argument("--repo-id", help="Hugging Face repo ID (e.g. username/visionai-retinal-ensemble)")
    parser.add_argument("--token", help="Hugging Face Write Token (from https://huggingface.co/settings/tokens)")
    parser.add_argument("--private", action="store_true", help="Make repository private (default is public)")

    args = parser.parse_args()

    repo_id = args.repo_id or os.environ.get("HF_MODEL_REPO")
    token = args.token or os.environ.get("HF_TOKEN")

    if not repo_id:
        print("="*65)
        print("🤗 VisionAI — Upload Ensemble Model to Hugging Face Hub")
        print("="*65)
        repo_id = input("\nEnter your Hugging Face repo ID (e.g. Karthikeya-Chavala7893/visionai-retinal-ensemble): ").strip()
        if not repo_id:
            print("❌ Repo ID is required. Exiting.")
            sys.exit(1)

    if not token:
        token = input("Enter your Hugging Face Write Token (hidden or leave empty if already logged in via huggingface-cli): ").strip()
        if not token:
            token = None

    upload_model(repo_id=repo_id, token=token, is_private=args.private)
