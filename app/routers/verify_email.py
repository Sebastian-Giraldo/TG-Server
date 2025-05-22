# app/routers/verify_email.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os, resend
from app.db import save_code, check_code

router = APIRouter()
resend.api_key = os.getenv("RESEND_API_KEY")


class EmailCode(BaseModel):
    email: str
    code: str


@router.post("/send-code")
def send_code(payload: EmailCode):
    # 1) Guarda el código en base de datos
    try:
        save_code(payload.email, payload.code)
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, detail=f"Error guardando código: {e}")

    # 2) Prepara el envío de correo
    params: resend.Emails.SendParams = {
        "from": "DataZeroApp <onboarding@resend.dev>",
        "to": [payload.email],
        "subject": "Tu código de verificación",
        "html": f"<p>Tu código es <strong>{payload.code}</strong></p>",
    }

    # 3) Envía y captura errores
    try:
        resp = resend.Emails.send(params)
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, detail=f"Error enviando correo: {e}")

    # 4) Asegúrate de que viene un id
    email_id = None
    if isinstance(resp, dict):
        email_id = resp.get("id") or (resp.get("data") or {}).get("id")
    else:
        email_id = getattr(resp, "id", None)

    if not email_id:
        raise HTTPException(500, detail="No se devolvió un id válido del envío")

    return {"ok": True, "id": email_id}


@router.post("/check-code")
def check_code_endpoint(payload: EmailCode):
    try:
        valid = check_code(payload.email, payload.code)
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, detail=f"Error comprobando código: {e}")
    return {"valid": valid}
