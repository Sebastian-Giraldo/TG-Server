from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import time
from huggingface_hub import InferenceClient
from tenacity import retry, stop_after_attempt, wait_exponential

router = APIRouter()

# ——— Configuración de Hugging Face ———
HF_TOKEN = os.getenv("HF_API_TOKEN")
MODEL_ID = "SebastianGiraldo/TG-Modelo-Final"

if not HF_TOKEN:
    raise RuntimeError("🔒 La variable de entorno HF_API_TOKEN no está definida")

# El InferenceClient usará automáticamente api-inference.huggingface.co
hf = InferenceClient(token=HF_TOKEN)

# ——— Función con reintentos automáticos ———
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def analyze_with_retry(text: str):
    try:
        return hf.text_classification(model=MODEL_ID, inputs=text)
    except Exception as err:
        raise RuntimeError(f"Error en API de Hugging Face: {err}")

# ——— Lógica de análisis de sentimiento ———
def analyze_sentiment(text: str, threshold: float = 0.51, min_len: int = 3):
    cleaned_text = text.strip()
    if len(cleaned_text) < min_len:
        return {"label": "No sensible", "score": None}

    try:
        result = analyze_with_retry(cleaned_text)[0]
        # Si la confianza es baja, forzamos “No sensible”
        if result["label"] == "Sensible" and result["score"] < threshold:
            return {"label": "No sensible", "score": result["score"]}
        return {"label": result["label"], "score": result["score"]}

    except RuntimeError as err:
        # Manejo del loading delay
        if "loading" in str(err).lower():
            time.sleep(20)
            return analyze_sentiment(text, threshold, min_len)
        raise

# ——— Esquema de entrada ———
class SentimentInput(BaseModel):
    text: str

# ——— Endpoint POST /predict ———
@router.post("/predict")
def predict_sentiment(input_data: SentimentInput):
    try:
        result = analyze_sentiment(input_data.text)
        return {"result": result}

    except RuntimeError as e:
        msg = str(e)
        if "loading" in msg.lower():
            # 503 = Service Unavailable cuando el modelo aún esté cargando
            raise HTTPException(status_code=503,
                                detail="El modelo está cargando, inténtalo de nuevo en 30 s")
        raise HTTPException(status_code=500, detail=msg)
