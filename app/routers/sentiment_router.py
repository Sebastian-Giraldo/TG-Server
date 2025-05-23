from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from huggingface_hub import InferenceClient  # Importación actualizada

router = APIRouter()

# ———————————————— CONFIGURACIÓN HF ————————————————
HF_TOKEN = os.getenv("HF_API_TOKEN")
if not HF_TOKEN:
    raise RuntimeError("🔒 La variable de entorno HF_API_TOKEN no está definida")

REPO_ID = "SebastianGiraldo/TG-Modelo-Final"

# Inicializamos el cliente con el modelo directamente
hf = InferenceClient(
    model=REPO_ID,
    token=HF_TOKEN
)

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
            .replace("", "")
    ).strip()

def analyze_sentiment(text: str, threshold: float = 0.51, min_len: int = 3):
    texto = clean_text(text)
    if len(texto) < min_len:
        return {"label": "No sensible", "score": None}

    try:
        # Llamada simplificada
        response = hf.text_classification(texto)
    except Exception as err:
        raise RuntimeError(f"Error llamando a HF Inference API: {err}")

    # Procesamiento de respuesta
    out = response[0]
    label = out.get("label")
    score = out.get("score")

    if label == "Sensible" and score is not None and score < threshold:
        label = "No sensible"

    return {"label": label, "score": score}

# ———————————————— ESQUEMA y ENDPOINT ————————————————
class SentimentInput(BaseModel):
    text: str

@router.post("/predict")
def predict_sentiment(input_data: SentimentInput):
    try:
        result = analyze_sentiment(input_data.text)
        return {"result": result}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))