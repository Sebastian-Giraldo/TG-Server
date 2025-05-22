# TG-Server/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# importacion de router
from app.routers.auth_router      import router as auth_router
from app.routers.location_router  import router as location_router
from app.routers.sentiment_router import router as sentiment_router
from app.routers.verify_router import router as verify_router
from app.routers.verify_email import router as verify_email_router

load_dotenv()
app = FastAPI()

# Lee, divide y limpia espacios/trailing-slashes
origins_raw = os.getenv("ALLOWED_ORIGINS", "")
origins = [
    origin.strip().rstrip("/") 
    for origin in origins_raw.split(",") 
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# routers existentes
app.include_router(auth_router,      prefix="/auth",      tags=["Auth"])
app.include_router(location_router,  prefix="/locations", tags=["Locations"])
app.include_router(sentiment_router, prefix="/sentiment", tags=["Sentiment"])
app.include_router(verify_router, prefix="/api", tags=["Verificación"])
app.include_router(verify_email_router, prefix="/verify-email", tags=["Verify Email"])

@app.get("/")
def read_root():
    return {"message": "🚀 API TG-Server funcionando correctamente"}
