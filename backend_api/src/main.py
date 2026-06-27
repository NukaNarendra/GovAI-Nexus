import os
import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from src.core.config import settings
from src.api.v1.endpoints import auth, ai_gateway, hitl, audit, health, execution, ingestion, kyc, aml
from src.infrastructure.database.session import db_manager

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API ROUTERS ---
app.include_router(
    auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"]
)
app.include_router(
    ai_gateway.router, prefix=f"{settings.API_V1_STR}/gateway", tags=["AI Gateway"]
)
app.include_router(
    hitl.router, prefix=f"{settings.API_V1_STR}/hitl", tags=["Human-in-the-Loop"]
)
app.include_router(
    audit.router, prefix=f"{settings.API_V1_STR}/audit", tags=["WORM Audit Log"]
)
app.include_router(
    health.router, prefix=f"{settings.API_V1_STR}/health", tags=["System Health"]
)
app.include_router(
    execution.router,
    prefix=f"{settings.API_V1_STR}/execution",
    tags=["Core Banking Execution"],
)
app.include_router(
    ingestion.router,
    prefix=f"{settings.API_V1_STR}/ingestion",
    tags=["Data Integration & Ingestion"],
)
app.include_router(
    kyc.router,
    prefix=f"{settings.API_V1_STR}/kyc",
    tags=["KYC Profiles"],
)
app.include_router(
    aml.router,
    prefix=f"{settings.API_V1_STR}/aml",
    tags=["AML Watchlists"],
)

# --- SMART PATH CALCULATION ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR))
FRONTEND_DIR = os.path.join(WORKSPACE_DIR, "frontend_ui")
PUBLIC_DIR = os.path.join(FRONTEND_DIR, "public")

# --- MOUNT STATIC FILES (Supports both /js/ and /public/js/ to prevent < errors) ---
if os.path.exists(PUBLIC_DIR):
    app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public_full")

    js_dir = os.path.join(PUBLIC_DIR, "js")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

    css_dir = os.path.join(PUBLIC_DIR, "css")
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")


# Helper to automatically find HTML files even if they are in the wrong folder
def find_html(filename: str):
    paths_to_check = [
        os.path.join(FRONTEND_DIR, filename),
        os.path.join(PUBLIC_DIR, filename),
        os.path.join(WORKSPACE_DIR, filename),
    ]
    for p in paths_to_check:
        if os.path.exists(p):
            return p
    return None


# --- HTML PAGE ROUTES ---
@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
async def serve_index():
    path = find_html("index.html")
    if path:
        return FileResponse(path)
    return HTMLResponse(
        "<h1>Error: index.html not found! Did you create it?</h1>", status_code=404
    )


@app.get("/dashboard.html", include_in_schema=False)
async def serve_dashboard():
    path = find_html("dashboard.html")
    if path:
        return FileResponse(path)
    return HTMLResponse("<h1>Error: dashboard.html not found</h1>", status_code=404)


@app.get("/hitl-review.html", include_in_schema=False)
async def serve_hitl():
    path = find_html("hitl-review.html")
    if path:
        return FileResponse(path)
    return HTMLResponse("<h1>Error: hitl-review.html not found</h1>", status_code=404)


@app.get("/audit-logs.html", include_in_schema=False)
async def serve_audit():
    path = find_html("audit-logs.html")
    if path:
        return FileResponse(path)
    return HTMLResponse("<h1>Error: audit-logs.html not found</h1>", status_code=404)


# --- CATCH-ALL (Prevents HTML from being sent instead of JS) ---
@app.get("/{full_path:path}", include_in_schema=False)
async def catch_all(full_path: str):
    if full_path.endswith(".js") or full_path.endswith(".css"):
        return JSONResponse(
            status_code=404, content={"error": f"JS/CSS file '{full_path}' not found."}
        )
    
    # Try to serve the exact requested HTML file first
    if full_path.endswith(".html"):
        filename = os.path.basename(full_path)
        # Search for it in compliance directory too
        paths_to_check = [
            os.path.join(FRONTEND_DIR, full_path),
            os.path.join(PUBLIC_DIR, full_path),
            os.path.join(FRONTEND_DIR, "compliance", filename)
        ]
        for p in paths_to_check:
            if os.path.exists(p):
                return FileResponse(p)
                
    path = find_html("index.html")
    if path:
        return FileResponse(path)
    return JSONResponse(status_code=404, content={"error": "Not Found"})


@app.on_event("startup")
async def startup_event():
    await db_manager.check_connection()

