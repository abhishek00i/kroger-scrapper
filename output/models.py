from datetime import datetime
import sqlite3
from typing import Optional, List, Dict
import json

class Database:
    def __init__(self, db_path: str = "kroger_scraper.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    started_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    total_cards INTEGER,
                    successful_scrapes INTEGER DEFAULT 0,
                    failed_scrapes INTEGER DEFAULT 0,
                    error TEXT
                )
            """)
            
            # Create deals table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    price TEXT,
                    original_price TEXT,
                    discount TEXT,
                    description TEXT,
                    details JSON,
                    created_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs (job_id)
                )
            """)
            
            conn.commit()

class JobManager:
    def __init__(self, db: Database):
        self.db = db

    def create_job(self, job_id: str) -> None:
        """Create a new job record"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO jobs (job_id, status, started_at) VALUES (?, ?, ?)",
                (job_id, "running", datetime.now())
            )
            conn.commit()

    def update_job_status(self, job_id: str, status: str, error: Optional[str] = None) -> None:
        """Update job status and completion time"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if status == "completed" or status == "failed":
                cursor.execute(
                    "UPDATE jobs SET status = ?, completed_at = ?, error = ? WHERE job_id = ?",
                    (status, datetime.now(), error, job_id)
                )
            else:
                cursor.execute(
                    "UPDATE jobs SET status = ? WHERE job_id = ?",
                    (status, job_id)
                )
            conn.commit()

    def update_job_stats(self, job_id: str, total_cards: int, successful: int, failed: int) -> None:
        """Update job scraping statistics"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE jobs 
                   SET total_cards = ?, 
                       successful_scrapes = ?, 
                       failed_scrapes = ? 
                   WHERE job_id = ?""",
                (total_cards, successful, failed, job_id)
            )
            conn.commit()

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get job status and statistics"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT job_id, status, started_at, completed_at, 
                          total_cards, successful_scrapes, failed_scrapes, error 
                   FROM jobs WHERE job_id = ?""",
                (job_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
                
            return {
                "job_id": row[0],
                "status": row[1],
                "started_at": row[2],
                "completed_at": row[3],
                "total_cards": row[4],
                "successful_scrapes": row[5],
                "failed_scrapes": row[6],
                "error": row[7]
            }

    def get_current_job(self) -> Optional[Dict]:
        """Get currently running job if any"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT job_id, started_at 
                   FROM jobs 
                   WHERE status = 'running' 
                   ORDER BY started_at DESC 
                   LIMIT 1"""
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "job_id": row[0],
                "started_at": row[1]
            }

class DealManager:
    def __init__(self, db: Database):
        self.db = db

    def save_deals(self, job_id: str, deals: List[Dict]) -> None:
        """Save multiple deals for a job"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            for deal in deals:
                cursor.execute(
                    """INSERT INTO deals 
                       (job_id, product_name, price, original_price, 
                        discount, description, details, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        job_id,
                        deal.get("name", ""),
                        deal.get("price", ""),
                        deal.get("original_price", ""),
                        deal.get("discount", ""),
                        deal.get("description", ""),
                        json.dumps(deal.get("details", {})),
                        datetime.now()
                    )
                )
            conn.commit()

    def get_deals(self, job_id: str) -> List[Dict]:
        """Get all deals for a job"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT product_name, price, original_price, 
                          discount, description, details
                   FROM deals 
                   WHERE job_id = ?""",
                (job_id,)
            )
            deals = []
            for row in cursor.fetchall():
                deals.append({
                    "name": row[0],
                    "price": row[1],
                    "original_price": row[2],
                    "discount": row[3],
                    "description": row[4],
                    "details": json.loads(row[5])
                })
            return deals
