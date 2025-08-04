#!/usr/bin/env python3
"""
Enhanced data update script with precise timestamp tracking
"""

import json
import os
import sys
import logging
from datetime import datetime
import subprocess

# Setup logging
log_filename = f"logs/data_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_backup(filename):
    """Create a backup of existing data file"""
    if os.path.exists(filename):
        backup_name = f"{filename}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            os.rename(filename, backup_name)
            logger.info(f"Created backup: {backup_name}")
            return backup_name
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None
    return None

def save_metadata(data_file, scrape_start_time, scrape_end_time, success=True, error_msg=None):
    """Save metadata about the scrape operation"""
    metadata = {
        'data_file': data_file,
        'scrape_start_time': scrape_start_time.isoformat(),
        'scrape_end_time': scrape_end_time.isoformat(),
        'scrape_duration_seconds': (scrape_end_time - scrape_start_time).total_seconds(),
        'success': success,
        'error_message': error_msg,
        'data_file_size': os.path.getsize(data_file) if os.path.exists(data_file) else 0,
        'update_script_version': '1.0'
    }

    # Also count comments if data file exists
    if success and os.path.exists(data_file):
        try:
            with open(data_file, 'r') as f:
                data = json.load(f)
                metadata['total_comments'] = len(data)
                metadata['comments_with_tickers'] = len([c for c in data if c.get('tickers')])
        except:
            pass

    # Save metadata
    metadata_file = 'data_metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Saved metadata to {metadata_file}")
    return metadata

def run_reddit_scraper():
    """Run the Reddit scraper and track timing"""
    data_file = 'lounge_thread_filtered_comments.json'
    scrape_start_time = datetime.now()

    logger.info("Starting Reddit data scrape...")
    logger.info(f"Scrape start time: {scrape_start_time}")

    # Create backup of existing data
    backup_file = create_backup(data_file)

    try:
        # Run the Reddit scraper
        result = subprocess.run([
            sys.executable, 'reddit_scrapper.py'
        ], capture_output=True, text=True, timeout=1800)  # 30 minute timeout

        scrape_end_time = datetime.now()
        duration = scrape_end_time - scrape_start_time

        if result.returncode == 0:
            logger.info(f"✅ Scrape completed successfully in {duration}")
            logger.info(f"Scrape end time: {scrape_end_time}")

            # Verify data file was created/updated
            if os.path.exists(data_file):
                file_size = os.path.getsize(data_file)
                logger.info(f"Data file size: {file_size} bytes")

                # Save successful metadata
                metadata = save_metadata(data_file, scrape_start_time, scrape_end_time, success=True)

                # Remove backup if scrape was successful
                if backup_file and os.path.exists(backup_file):
                    os.remove(backup_file)
                    logger.info("Removed backup file (scrape successful)")

                return True, metadata
            else:
                error_msg = "Data file was not created"
                logger.error(f"❌ {error_msg}")
                save_metadata(data_file, scrape_start_time, scrape_end_time, success=False, error_msg=error_msg)
                return False, None
        else:
            error_msg = f"Scraper failed with return code {result.returncode}: {result.stderr}"
            logger.error(f"❌ {error_msg}")
            save_metadata(data_file, scrape_start_time, scrape_end_time, success=False, error_msg=error_msg)

            # Restore backup if scrape failed
            if backup_file and os.path.exists(backup_file):
                os.rename(backup_file, data_file)
                logger.info("Restored backup file (scrape failed)")

            return False, None

    except subprocess.TimeoutExpired:
        scrape_end_time = datetime.now()
        error_msg = "Scraper timed out after 30 minutes"
        logger.error(f"❌ {error_msg}")
        save_metadata(data_file, scrape_start_time, scrape_end_time, success=False, error_msg=error_msg)

        # Restore backup if scrape timed out
        if backup_file and os.path.exists(backup_file):
            os.rename(backup_file, data_file)
            logger.info("Restored backup file (scrape timed out)")

        return False, None

    except Exception as e:
        scrape_end_time = datetime.now()
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"❌ {error_msg}")
        save_metadata(data_file, scrape_start_time, scrape_end_time, success=False, error_msg=error_msg)
        return False, None

def main():
    """Main function"""
    logger.info("="*50)
    logger.info("Reddit Data Update Started")
    logger.info("="*50)

    # Check if reddit_scrapper.py exists
    if not os.path.exists('reddit_scrapper.py'):
        logger.error("❌ reddit_scrapper.py not found")
        return 1

    # Run the scraper
    success, metadata = run_reddit_scraper()

    if success:
        logger.info("🎉 Data update completed successfully!")
        if metadata:
            logger.info(f"📊 Comments processed: {metadata.get('total_comments', 'Unknown')}")
            logger.info(f"🎯 Comments with tickers: {metadata.get('comments_with_tickers', 'Unknown')}")
            logger.info(f"⏱️  Duration: {metadata.get('scrape_duration_seconds', 0):.1f} seconds")
        return 0
    else:
        logger.error("💥 Data update failed!")
        return 1

if __name__ == "__main__":
    exit(main())
