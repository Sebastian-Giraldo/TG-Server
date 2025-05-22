# TG-Server/app/routers/sentiment_router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from huggingface_hub import InferenceApi

router = APIRouter()

HF_TOKEN = os.getenv("HF_API_TOKEN")   # lo defines en Render
hf = InferenceApi(
  repo_id="SebastianGiraldo/TG-Modelo-Final",
  token=HF_TOKEN
)

def clean_text(text: str) -> str:
    return (text.replace('.', '')
                .replace(',', '')
                .replace('*', '')
                .replace('[', '')
                .replace(']', '')
                .replace('{', '')
                .replace('}', '')
                .replace('~', '')
                .replace('`', ''))

def analyze_sentiment(text: str, threshold: float = 0.51, min_len: int = 3):
    t = clean_text(text).strip()
    if len(t) < min_len:
        return {"label": "No sensible", "score": None}

    # aquí preguntamos al servicio remoto
    out = hf(t)[0]
    label, score = out["label"], out["score"]
    if label == "Sensible" and score < threshold:
        label = "No sensible"
    return {"label": label, "score": score}

class SentimentInput(BaseModel):
    text: str

@router.post("/predict")
def predict_sentiment(input_data: SentimentInput):
    try:
        return {"result": analyze_sentiment(input_data.text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))