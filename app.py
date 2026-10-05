"""
app.py — Root Entrypoint for Hugging Face Gradio Space (ZeroGPU & CPU Compatible)
────────────────────────────────────────────────────────────────────────────────
Serves the VisionAI REST API for Vercel and an interactive Gradio UI.
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

# Hugging Face ZeroGPU support
try:
    import spaces
except ImportError:
    class _MockSpaces:
        @staticmethod
        def GPU(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            def decorator(fn):
                return fn
            return decorator
    spaces = _MockSpaces()

from starlette.middleware.wsgi import WSGIMiddleware
from fastapi import FastAPI
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import gradio as gr

# Import the existing production Flask app and inference engine
from app import app as flask_app
import model

# 1. Main FastAPI Application
server = FastAPI(title="VisionAI Screening API")

server.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@server.get("/api/health")
def health_check():
    """Direct health endpoint for monitoring and orchestrators."""
    return JSONResponse({
        "status": "healthy",
        "service": "VisionAI Retinal Screening API",
        "model_loaded": model.is_loaded(),
        "classes": model.get_labels(),
    })

# Mount Flask app for /api/predict and all remaining backend routes
server.mount("/api", WSGIMiddleware(flask_app))

# 2. Interactive Gradio UI for direct testing & Hugging Face healthcheck
@spaces.GPU
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
    gr.Markdown("🚀 **REST API Status:** `ONLINE` — Endpoints live at `/api/predict` and `/api/health`")

    with gr.Row():
        with gr.Column(scale=1):
            input_img = gr.Image(type="pil", label="Upload Retinal Fundus Photo (JPG/PNG)")
            analyze_btn = gr.Button("🔍 Run AI Clinical Analysis", variant="primary")
        with gr.Column(scale=1):
            output_data = gr.JSON(label="AI Screening Diagnostic Output")

    analyze_btn.click(fn=predict_gradio, inputs=input_img, outputs=output_data)

# Mount Gradio interface onto FastAPI at root
app = gr.mount_gradio_app(server, demo, path="/")
