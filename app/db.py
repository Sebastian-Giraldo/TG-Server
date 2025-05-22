# app/db.py
from app.config.firebase import init_firebase
from firebase_admin import firestore

# inicializa una sola vez
init_firebase()
db = firestore.client()

def save_code(email: str, code: str):
    # guarda con sello de tiempo
    doc = db.collection("email_verifications").document(email)
    doc.set({
        "code": code,
        "created_at": firestore.SERVER_TIMESTAMP
    })

def check_code(email: str, code: str) -> bool:
    doc_ref = db.collection("email_verifications").document(email)
    doc = doc_ref.get()
    if not doc.exists or doc.to_dict().get("code") != code:
        return False
    doc_ref.delete()
    return True
