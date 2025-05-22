from fastapi import APIRouter

router = APIRouter()

@router.get("/check")
def check_auth():
    return {"message": "Ruta de autenticación funcionando"}
