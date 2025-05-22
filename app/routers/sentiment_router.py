# TG-Server/app/routers/sentiment_router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from transformers import pipeline

router = APIRouter()

# 1) Carga el pipeline desde HF Hub
sentiment_pipe = pipeline(
    "text-classification",
    model="SebastianGiraldo/TG-Modelo-Final",     
    tokenizer="SebastianGiraldo/TG-Modelo-Final", 
    device=0,
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
    texto_limpio = clean_text(text)
    if len(texto_limpio.strip()) < min_len:
        return {"label": "No sensible", "score": None}
    result = sentiment_pipe(texto_limpio)[0]
    label, score = result["label"], result["score"]
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
