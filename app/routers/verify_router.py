# app/routers/verify_router.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.services.instagram_verifier import InstagramVerifier


router = APIRouter()

class ProfileRequest(BaseModel):
    username: str

@router.post("/verificar-perfil")
def verify_profile(
    req: ProfileRequest,
    # user = Depends(get_current_user)
):
    try:
        verifier = InstagramVerifier(delay_between_posts=1, max_posts=5)
        return verifier.verify(req.username)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
