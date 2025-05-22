import os
import firebase_admin
from firebase_admin import credentials

def init_firebase():
    # Solo inicializa una vez
    if not firebase_admin._apps:
        # Montamos el dict de credenciales a partir de variables de entorno
        cred_dict = {
            "type": os.getenv("FIREBASE_TYPE"),
            "project_id": os.getenv("FIREBASE_PROJECT_ID"),
            "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
            # Reemplazamos los "\n" literales por saltos de línea reales
            "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
            "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
            "client_id": os.getenv("FIREBASE_CLIENT_ID"),
            "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
            "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
            "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_CERT_URL"),
            "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL"),
        }

        # Crea el objeto Certificate a partir del dict
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
