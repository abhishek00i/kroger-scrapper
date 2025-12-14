from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import threading
import uuid
from datetime import datetime
from scraper.kroger_scraper import KrogerScraper
from database.models import Database, JobManager, DealManager

# Initialize router and database
router = APIRouter()
db = Database()
job_manager = JobManager(db)
deal_manager = DealManager(db)

@router.get("/scrape-kroger-deals")
def start_scrape(limit: int = 1000):
    """Start a new scraping job"""
    # Check if there's already a job running
    current_job = job_manager.get_current_job()
    if current_job:
        return JSONResponse(content={
            "success": False,
            "job_id": current_job["job_id"],
            "status": "running",
            "message": "A scraping job is already in progress.",
            "check_status_url": f"http://127.0.0.1:8080/status/{current_job['job_id']}"
        }, status_code=409)

    # Create new job
    job_id = str(uuid.uuid4())
    scraper = KrogerScraper(job_id, limit)
    threading.Thread(target=scraper.scrape, args=(), daemon=True).start()

    return JSONResponse(content={
        "success": True,
        "job_id": job_id,
        "status": "started",
        "message": "Scraping job started successfully in background!",
        "started_at": datetime.now().isoformat(),
        "check_status_url": f"http://127.0.0.1:8080/status/{job_id}"
    }, status_code=202)

@router.get("/status/{job_id}")
def get_status(job_id: str):
    """Get the status of a scraping job"""
    job_info = job_manager.get_job_status(job_id)
    
    if not job_info:
        raise HTTPException(status_code=404, detail={
            "success": False,
            "job_id": job_id,
            "status": "not_found",
            "message": "Job ID not found. It may have expired or never existed."
        })

    response = {
        "success": True,
        "job_id": job_id,
        "status": job_info["status"],
        "started_at": job_info["started_at"],
        "total_cards": job_info["total_cards"],
        "successful_scrapes": job_info["successful_scrapes"],
        "failed_scrapes": job_info["failed_scrapes"]
    }

    if job_info["status"] == "completed":
        response["completed_at"] = job_info["completed_at"]
    elif job_info["status"] == "failed":
        response["error"] = job_info["error"]
        response["success"] = False
        return JSONResponse(content=response, status_code=500)

    return response

@router.get("/get-data/{job_id}")
def get_data(job_id: str):
    """Get the scraped deals for a job"""
    job_info = job_manager.get_job_status(job_id)
    
    if not job_info:
        raise HTTPException(status_code=404, detail={
            "success": False,
            "job_id": job_id,
            "message": "Job ID not found."
        })

    if job_info["status"] != "completed":
        return JSONResponse(content={
            "success": False,
            "job_id": job_id,
            "status": job_info["status"],
            "message": "Job is not completed yet."
        }, status_code=400)

    deals = deal_manager.get_deals(job_id)
    return {
        "success": True,
        "job_id": job_id,
        "status": "completed",
        "completed_at": job_info["completed_at"],
        "total_deals": len(deals),
        "deals": deals
    }

@router.get("/")
def root():
    """Root endpoint with API information"""
    return {
        "success": True,
        "message": "Kroger Weekly Deals Async Scraper API",
        "version": "3.0",
        "endpoints": {
            "start_scraping": "GET /scrape-kroger-deals?limit=500",
            "check_status": "GET /status/{job_id}",
            "get_data": "GET /get-data/{job_id}"
        },
        "status": "running"
    }

# Initialize FastAPI app
app = FastAPI(
    title="Kroger Scraper API",
    description="API for scraping Kroger weekly deals",
    version="3.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include router
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
