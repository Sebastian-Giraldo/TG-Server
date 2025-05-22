# app/routers/sentiment_router.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os

# 👇 cliente de HF más moderno (reemplaza a InferenceApi)
from huggingface_hub.inference import InferenceClient

router = APIRouter()

# ———————————————— CONFIGURACIÓN HF ————————————————
# Tienes que definir HF_API_TOKEN en las env vars de Render
HF_TOKEN = os.getenv("HF_API_TOKEN")
if not HF_TOKEN:
    raise RuntimeError("🔒 La variable de entorno HF_API_TOKEN no está definida")

# Inicializamos el cliente
hf = InferenceClient(
    token=HF_TOKEN,
    # opcionalmente especificas la URL base si la cambiaste:
    # endpoint="https://api-inference.huggingface.co"
)

REPO_ID = "SebastianGiraldo/TG-Modelo-Final"
TASK    = "text-classification"

# ———————————————— LÓGICA DE ANÁLISIS ————————————————
def clean_text(text: str) -> str:
    return (
        text.replace(".", "")
            .replace(",", "")
            .replace("*", "")
            .replace("[", "")
            .replace("]", "")
            .replace("{", "")
            .replace("}", "")
            .replace("~", "")
            .replace("`", "")
    ).strip()

def analyze_sentiment(text: str, threshold: float = 0.51, min_len: int = 3):
    texto = clean_text(text)
    if len(texto) < min_len:
        return {"label": "No sensible", "score": None}

    # llamamos al endpoint remoto
    try:
        # para InfereneceClient hay que pasar repo_id + task en el dict
        response = hf.text_classification(
            inputs=texto,
            model=REPO_ID,
            task=TASK
        )
    except Exception as err:
        # si quieres debug, imprímelo en logs:
        raise RuntimeError(f"Error llamando a HF Inference API: {err}")

    # la respuesta es una lista de dicts
    out   = response[0]
    label = out.get("label")
    score = out.get("score")

    # si es “Sensible” pero con poca confianza, lo marcamos “No sensible”
    if label == "Sensible" and score is not None and score < threshold:
        label = "No sensible"

    return {"label": label, "score": score}

# ———————————————— ESQUEMA y ENDPOINT ————————————————
class SentimentInput(BaseModel):
    text: str

@router.post("/predict", summary="Analiza si un texto revela información sensible")
def predict_sentiment(input_data: SentimentInput):
    try:
        result = analyze_sentiment(input_data.text)
        return {"result": result}
    except RuntimeError as e:
        # errores de llamada a HF
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        # otros fallos internos
        raise HTTPException(status_code=500, detail=str(e))
