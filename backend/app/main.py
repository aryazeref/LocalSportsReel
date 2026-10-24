"""HTTP API. Try http://localhost:8000/docs for interactive API documentation."""
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from .agent import build_feed, create_story
from .data import CITIES
from .models import FeedResponse, Story



app = FastAPI(title="Local SportsReel API", version="0.1.0")
origins = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "dataset": "synthetic_demo", "version": "0.1.0"}


@app.get("/api/cities")
def cities():
    return {"cities": list(CITIES)}


@app.get("/api/feed", response_model=FeedResponse)
def feed(city: str = "Oulu", radius_km: int = Query(50, ge=5, le=500),
         sport: str = "All"):
    try:
        return build_feed(city=city, radius_km=radius_km, sport=sport)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/stories/{moment_id}", response_model=Story)
def story(moment_id: str):
    try:
        return create_story(moment_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    
# Import the router that communicates with the Liiga API.
from .liiga_api import router as liiga_router
# Register its endpoints with our existing FastAPI application.
app.include_router(liiga_router)