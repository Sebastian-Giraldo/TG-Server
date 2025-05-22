import os
import re
import time
from datetime import datetime
from typing import List, Dict, Any
import instaloader
from dotenv import load_dotenv
from transformers import pipeline
import firebase_admin
from firebase_admin import credentials, firestore


load_dotenv()
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")

# 1) Leemos las credenciales desde variables de entorno
firebase_creds = {
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    # reemplazamos los "\n" literales con saltos de línea reales
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL"),
}

if not all([IG_USERNAME, IG_PASSWORD, firebase_creds["private_key"]]):
    raise RuntimeError("🔒 Faltan variables de entorno en .env")

# ———————— 2. Inicializar modelo HuggingFace ————————
sentiment_pipe = pipeline(
    "text-classification",
    model="SebastianGiraldo/TG-Modelo-Final",
    tokenizer="SebastianGiraldo/TG-Modelo-Final",
    device=0,
)

# ———————— 3. Inicializar Firebase Admin ————————
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_creds)
    firebase_admin.initialize_app(cred)
db = firestore.client()

class InstagramVerifier:
    # Detecta números de teléfono (7–15 dígitos seguidos)
    PHONE_RE = re.compile(r"(?:\d[\s\.-]?){7,15}")


    # Palabras clave “financieras”
    FIN_KEYWORDS = ["bancolombia","nequi", "daviplata", "bancolombia", "davivienda", "bogotá", "bbva", "popular", "av villas", "caja social", "banco de occidente", "banco agrario", "bancoomeva", "banco pichincha", "banco falabella", "banco w", "banco caja social", "banco santander", "banco itaú", "banco gnb sudameris", "banco serfinanza", "banco cooperativo coopcentral", "banco procredit", "banco mundo mujer", "banco finandina", "banco vivienda", "banco credifinanciera", "banco union", "lulo bank", "nubank", "tyba", "movii", "albo", "uala", "bru bank", "bold", "lemon", "tpaga", "confiar cooperativa financiera", "coomeva cooperativa", "coofinep cooperativa", "coofamiliar cooperativa", "cooperativa financiera de antioquia", "cotrafa cooperativa", "cootraep cooperativa", "cootrecam cooperativa", "scotiabank colpatria", "banco plaza", "banco seguridad", "banco credencial", "cc", "tarjeta", "nit", ]

    # Salud / discapacidad / genéticos
    HEALTH_KEYWORDS = [
    # Enfermedades físicas comunes
    "gastroenteritis", "infección respiratoria", "gripe", "faringitis", "migraña", 
    "cefalea", "ojo seco", "fatiga visual", "conjuntivitis", "covid",
    
    # Salud mental (prioridad en universitarios)
    "ansiedad", "depresión", "estrés", "insomnio", "trastorno sueño", 
    "ataque de pánico", "burnout", "trastorno alimenticio", "anorexia", 
    "bulimia", "autolesión", "suicidio", 
    
    # ETS y salud sexual
    "VIH", "ETS", "VPH", "herpes", "clamidia", "gonorrea", "sífilis",
    "embarazo no planeado", "anticonceptivos", 
    
    # Enfermedades crónicas/graves
    "cáncer", "diabetes", "hipertensión", "asma", "epilepsia", 
    "enfermedad cardíaca", "tiroides", "autoinmune", 
    
    # Discapacidades y condiciones neurológicas
    "discapacidad", "TDAH", "autismo", "dislexia", "bipolaridad",
    "esquizofrenia", "TOC", 
    
    # Hábitos de riesgo
    "alcoholismo", "drogas", "tabaquismo", "adicción", "sedentarismo",
    "obesidad", "desnutrición", 
    
    # Términos genéricos
    "enfermedad", "genético", "diagnóstico", "tratamiento", "hospitalización",
    "urgencias", "terapia", "psiquiatría", "medicamento"
]

    # Ideología / política / sindicatos
    POL_KEYWORDS = [
        "partido", "sindicato", "oposición", "ideología", "política", "Centro Democrático", "Partido Liberal", "Polo Democrático", "Alianza Verde", "Pacto Histórico", "Partido Conservador",
            "Cambio Radical", "Partido MIRA", "Colombia Humana", "Partido Comunes", "11.	MAIS (Movimiento Alternativo Indígena y Social)",
            "ASI (Alianza Social Independiente)", "Colombia Justa", "Alianza Democrática Amplia",
            "Unión Patriótica", "Autoridades Indígenas de Colombia"
    ]

    #  Religión / convicciones
    RELIGIOUS_KEYWORDS = [
        "cristianismo", "católico", "budista", "musulmán", "ateo", "religión"
    ]

    #  Domicilio (calle, avenida, carrera…)
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

    def scrape_posts(self, profile: instaloader.Profile) -> List[Dict[str,Any]]:
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

    def classify_profile(self, text: str) -> Dict[str,Any]:
        out = sentiment_pipe(text or "")[0]
        return {"label": out["label"], "score": float(out["score"])}

    def extract_reasons(self, posts: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
        reasons = []
        seen = set()

        for p in posts:
            cap = p["caption"] or ""
            cap_low = cap.lower()

            # 1) Teléfonos mejorados
            for raw in self.PHONE_RE.findall(cap):
                # normalizar a solo dígitos:
                digits = re.sub(r"[^\d]", "", raw)
                key = ("phone", digits)
                if key not in seen:
                    seen.add(key)
                    reasons.append({
                        "type": "phone",
                        "detail": f"Número detectado: {digits}"
                    })

            # 2) Palabras clave financieras
            for kw in self.FIN_KEYWORDS:
                if kw in cap_low:
                    key = ("fin", kw)
                    if key not in seen:
                        seen.add(key)
                        reasons.append({
                            "type": "financial",
                            "detail": f"Mención de «{kw}»"
                        })

            # 3) Salud / discapacidad
            for kw in self.HEALTH_KEYWORDS:
                if kw in cap_low:
                    key = ("health", kw)
                    if key not in seen:
                        seen.add(key)
                        reasons.append({
                            "type": "health",
                            "detail": f"Mención de «{kw}»"
                        })

            # 4) Política / ideología / sindicatos
            for kw in self.POL_KEYWORDS:
                if kw.lower() in cap_low:
                    key = ("political", kw)
                    if key not in seen:
                        seen.add(key)
                        reasons.append({
                            "type": "political",
                            "detail": f"Mención de «{kw}»"
                        })

            # 5) Religión / convicciones
            for kw in self.RELIGIOUS_KEYWORDS:
                if kw in cap_low:
                    key = ("religion", kw)
                    if key not in seen:
                        seen.add(key)
                        reasons.append({
                            "type": "religion",
                            "detail": f"Mención de «{kw}»"
                        })

            # 6) Dirección
            for match in self.ADDRESS_RE.finditer(cap):
                dir_text = match.group(0)
                key = ("address", dir_text)
                if key not in seen:
                    seen.add(key)
                    reasons.append({
                        "type": "address",
                        "detail": f"Domicilio detectado: {dir_text}"
                    })

            # 7) Ubicación geolocalizada
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
        self, username: str,
        classification: Dict[str,Any],
        reasons: List[Dict[str,Any]],
        posts: List[Dict[str,Any]]
    ):
        doc = db.collection("profiles").document(username)
        doc.set({
            "checkedAt": firestore.SERVER_TIMESTAMP,
            "classification": classification,
            "reasons": reasons,
            "posts": posts,
        })

    def verify(self, raw_username: str) -> Dict[str,Any]:
        self.login()
        profile = self.fetch_profile(raw_username)
        uname = profile.username

        posts = self.scrape_posts(profile)
        all_captions = " ".join(p["caption"] for p in posts)
        classification = self.classify_profile(all_captions)
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
