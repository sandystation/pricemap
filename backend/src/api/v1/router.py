from fastapi import APIRouter

from src.api.v1 import geocode, health, properties, stats, valuations

api_v1_router = APIRouter()

api_v1_router.include_router(health.router, tags=["health"])
api_v1_router.include_router(valuations.router, prefix="/valuations", tags=["valuations"])
api_v1_router.include_router(properties.router, prefix="/properties", tags=["properties"])
api_v1_router.include_router(geocode.router, prefix="/geocode", tags=["geocode"])
api_v1_router.include_router(stats.router, prefix="/stats", tags=["stats"])
