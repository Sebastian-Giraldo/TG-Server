import os
import re
import time
from datetime import datetime
from typing import List, Dict, Any
import instaloader
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
import firebase_admin
from firebase_admin import credentials, firestore

# Cargar variables de entorno
load_dotenv()

# Configuración de credenciales
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
HF_TOKEN = os.getenv("HF_API_TOKEN")  # Token de Hugging Face

# Validar variables críticas
if not all([IG_USERNAME, IG_PASSWORD, HF_TOKEN]):
    raise RuntimeError("🔒 Faltan variables de entorno esenciales en .env")

# Configuración de Firebase
firebase_creds = {
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL"),
}

# Inicializar Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_creds)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Cliente de Hugging Face
hf_client = InferenceClient(
    model="SebastianGiraldo/TG-Modelo-Final",
    token=HF_TOKEN
)

class InstagramVerifier:
    # Expresiones regulares y listas de palabras clave
    PHONE_RE = re.compile(r"(?:\d[\s\.-]?){7,15}")
    
    FIN_KEYWORDS = [
        "bancolombia", "nequi", "daviplata", "bancolombia", "davivienda", 
        "bbva", "popular", "av villas", "caja social", "banco de occidente",
        # ... (lista completa de palabras financieras)
    ]
    
    HEALTH_KEYWORDS = [
        "ansiedad", "depresión", "estrés", "insomnio", "cáncer", "diabetes",
        # ... (lista completa de palabras de salud)
    ]
    
    POL_KEYWORDS = [
        "partido", "sindicato", "oposición", "Centro Democrático", 
        "Partido Liberal", "Polo Democrático",
        # ... (lista completa de palabras políticas)
    ]
    
    RELIGIOUS_KEYWORDS = [
        "cristianismo", "católico", "budista", "musulmán", "ateo", "religión"
    ]
    
    ADDRESS_RE = re.compile(r"\b(calle|av(enida)?|cra|trans|cll)\s+\d+\b", re.IGNORECASE)

    def __init__(self, delay_between_posts: int = 2, max_posts: int = 10):
        self.loader = instaloader.Instaloader()
        self.delay = delay_between_posts
        self.max_posts = max_posts

    def login(self):
        try:
            self.loader.login(IG_USERNAME, IG_PASSWORD)
        except Exception as e:
            raise RuntimeError(f"❌ Falló login Instagram: {e}")

    @staticmethod
    def clean_username(raw: str) -> str:
        return raw.strip().lstrip("@")

    def fetch_profile(self, username: str) -> instaloader.Profile:
        uname = self.clean_username(username)
        try:
            return instaloader.Profile.from_username(self.loader.context, uname)
        except instaloader.exceptions.ProfileNotExistsException:
            raise ValueError(f"❌ Usuario '{uname}' no existe o es privado")
        except Exception as e:
            raise RuntimeError(f"❌ Error fetch_profile: {e}")

    def scrape_posts(self, profile: instaloader.Profile) -> List[Dict[str, Any]]:
        posts_data = []
        for i, post in enumerate(profile.get_posts()):
            if i >= self.max_posts:
                break
            posts_data.append({
                "date": post.date_utc.isoformat(),
                "caption": post.caption or "",
                "location": post.location.name if post.location else None,
                "comments": [
                    {"user": c.owner.username, "text": c.text}
                    for c in post.get_comments()[:5]
                ]
            })
            time.sleep(self.delay)
        return posts_data

    def classify_text(self, text: str) -> Dict[str, Any]:
        if not text.strip():
            return {"label": "No sensible", "score": 0.0}
        
        try:
            response = hf_client.text_classification(text)
            result = response[0]
            return {
                "label": result["label"],
                "score": float(result["score"])
            }
        except Exception as e:
            raise RuntimeError(f"Error en la API de Hugging Face: {str(e)}")

    def extract_reasons(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        reasons = []
        seen = set()

        for p in posts:
            cap = p["caption"] or ""
            cap_low = cap.lower()

            # Detección de números de teléfono
            for raw in self.PHONE_RE.findall(cap):
                digits = re.sub(r"[^\d]", "", raw)
                key = ("phone", digits)
                if key not in seen:
                    seen.add(key)
                    reasons.append({
                        "type": "phone",
                        "detail": f"Número detectado: {digits}"
                    })

            # Detección de palabras clave por categoría
            categories = {
                "financial": self.FIN_KEYWORDS,
                "health": self.HEALTH_KEYWORDS,
                "political": self.POL_KEYWORDS,
                "religion": self.RELIGIOUS_KEYWORDS
            }

            for cat, keywords in categories.items():
                for kw in keywords:
                    if kw.lower() in cap_low:
                        key = (cat, kw)
                        if key not in seen:
                            seen.add(key)
                            reasons.append({
                                "type": cat,
                                "detail": f"Mención de «{kw}»"
                            })

            # Detección de direcciones
            for match in self.ADDRESS_RE.finditer(cap):
                dir_text = match.group(0)
                key = ("address", dir_text)
                if key not in seen:
                    seen.add(key)
                    reasons.append({
                        "type": "address",
                        "detail": f"Domicilio detectado: {dir_text}"
                    })

            # Detección de ubicaciones geográficas
            if p["location"]:
                loc = p["location"]
                key = ("location", loc)
                if key not in seen:
                    seen.add(key)
                    reasons.append({
                        "type": "location",
                        "detail": f"Ubicación mostrada: {loc}",
                        "map_link": f"https://maps.google.com?q={loc.replace(' ','+')}"
                    })

        return reasons

    def save_to_firebase(
        self, 
        username: str,
        classification: Dict[str, Any],
        reasons: List[Dict[str, Any]],
        posts: List[Dict[str, Any]]
    ):
        doc = db.collection("profiles").document(username)
        doc.set({
            "checkedAt": firestore.SERVER_TIMESTAMP,
            "classification": classification,
            "reasons": reasons,
            "posts": posts,
        })

    def verify(self, raw_username: str) -> Dict[str, Any]:
        self.login()
        profile = self.fetch_profile(raw_username)
        uname = profile.username

        posts = self.scrape_posts(profile)
        all_captions = " ".join(p["caption"] for p in posts if p["caption"])
        classification = self.classify_text(all_captions)
        reasons = self.extract_reasons(posts)

        self.save_to_firebase(uname, classification, reasons, posts)

        return {
            "username": uname,
            "classification": classification,
            "reasons": reasons,
            "posts": posts,
        }

if __name__ == "__main__":
    usr = input("👉 Perfil Instagram (@usuario): ")
    verifier = InstagramVerifier(delay_between_posts=1, max_posts=5)
    res = verifier.verify(usr)
    import json; print(json.dumps(res, indent=2, ensure_ascii=False))