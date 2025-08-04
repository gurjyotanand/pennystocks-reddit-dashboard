#!/usr/bin/env python3
"""
Standalone scheduler service for production deployments
"""

import os
import sys
import time
import logging
import subprocess
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_scraper():
    """Run the Reddit scraper"""
    logger.info("🕐 Starting scheduled Reddit scraper...")
    
    try:
        result = subprocess.run([
            sys.executable, 'update_data.py'
        ], capture_output=True, text=True, timeout=1800)
        
        if result.returncode == 0:
            logger.info("✅ Scheduled scraper completed successfully")
        else:
            logger.error(f"❌ Scheduled scraper failed: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logger.error("⏰ Scheduled scraper timed out")
    except Exception as e:
        logger.error(f"💥 Scheduled scraper error: {str(e)}")

if __name__ == '__main__':
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    scheduler = BlockingScheduler()
    
    # Add job to run every 30 minutes
    scheduler.add_job(
        run_scraper,
        'interval',
        minutes=30,
        id='reddit_scraper'
    )
    
    logger.info("🚀 Scheduler service starting - will run every 30 minutes")
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("👋 Scheduler service stopped")
