"""Growth Garden FastAPI app entry — SKELETON.

Only the health endpoint exists so the pipeline's integration smoke check passes.
Real routers (auth, diary, garden, events) are added under routers/ and registered here.
See CLAUDE.md for the package rules.
"""

from fastapi import FastAPI

app = FastAPI(title="Growth Garden API", version="0.0.0-skeleton")


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok"}


# Register routers here as they are built, e.g.:
# from routers import auth, diary, garden, events
# app.include_router(auth.router, prefix="/api/v1")
