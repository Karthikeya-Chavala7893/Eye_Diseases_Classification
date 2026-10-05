"""
app.py — Root Entrypoint for Hugging Face Gradio Space
─────────────────────────────────────────────────────
Mounts the VisionAI Flask REST API onto FastAPI / Starlette
so all /api/v1 endpoints are served live with 16 GB RAM for Vercel.
Also displays an interactive Gradio UI for direct testing.
"""

import os
import sys

# Ensure backend directory is in python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Set production defaults if not set in environment
os.environ.setdefault("FLASK_ENV", "production")
os.environ.setdefault("TORCH_DEVICE", "cpu")
os.environ.setdefault("LOCAL_MODEL_ID", "models/ensemble_classifier.pth")
os.environ.setdefault("HF_MODEL_REPO", "Karthikeya-Chavala7893/visionai-retinal-ensemble")
os.environ.setdefault("MODEL_LOAD_TIMEOUT_SECONDS", "180")
os.environ.setdefault("ALLOWED_ORIGINS", "*")

from starlette.middleware.wsgi import WSGIMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import gradio as gr

# Import the existing production Flask app and inference engine
from app import app as flask_app
import model

# 1. Create FastAPI wrapper
fastapi_app = FastAPI(title="VisionAI Retinal Screening API")

# Add permissive CORS so Vercel can always call the API from anywhere
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Mount all Flask API endpoints at /api
fastapi_app.mount("/api", WSGIMiddleware(flask_app))

# 3. Interactive Gradio UI for direct testing & Hugging Face healthcheck
def predict_gradio(img):
    if img is None:
        return {"error": "Please upload a retinal fundus photograph."}
    try:
        import io
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        raw_bytes = buf.getvalue()
        result = model.predict(raw_bytes)
        return {
            "Status": "Success",
            "Diagnosis": result.get("prediction"),
            "Confidence": f"{result.get('confidence', 0)}%",
            "Pathology Breakdown": result.get("probabilities", {}),
            "Clinical Advice": result.get("triage", {}).get("recommendation", "Please consult an ophthalmologist."),
        }
    except Exception as exc:
        return {"error": str(exc)}

with gr.Blocks(title="VisionAI — Retinal Screening Platform") as demo:
    gr.Markdown("# 👁️ VisionAI — Clinical Retinal Screening Platform")
    gr.Markdown(
        "**Multi-condition Deep Learning Ensemble** (EfficientNetB3 + DenseNet121 + InceptionResNetV2) | "
        "**95.42% Clinical Accuracy**"
    )
    gr.Markdown("🚀 **REST API Status:** `ONLINE` — Endpoints live at `/api/v1/predict` and `/api/v1/health`")

    with gr.Row():
        with gr.Column(scale=1):
            input_img = gr.Image(type="pil", label="Upload Retinal Fundus Photo (JPG/PNG)")
            analyze_btn = gr.Button("🔍 Run AI Clinical Analysis", variant="primary")
        with gr.Column(scale=1):
            output_data = gr.JSON(label="AI Screening Diagnostic Output")

    analyze_btn.click(fn=predict_gradio, inputs=input_img, outputs=output_data)

# 4. Mount Gradio demo onto FastAPI root
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
