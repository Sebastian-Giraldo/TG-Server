from fastapi import APIRouter
from typing import List

router = APIRouter()

@router.get("/")
def list_locations():
    return [{"id": 1, "name": "Ubicación de prueba"}]
