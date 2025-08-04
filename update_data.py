#!/usr/bin/env python3
"""
Reddit Penny Stocks Dashboard - Mobile-Friendly Version with Background Scheduling
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime
from flask import Flask, render_template, jsonify
import os
import logging
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import signal
import sys

# APScheduler imports
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'production-secret-key')

# Production logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable debug completely
app.config['DEBUG'] = False

# Global variables for tracking refresh status
refresh_status = {
    'is_running': False,
    'last_refresh': None,
    'last_error': None,
    'progress': 0
}

# Initialize scheduler
scheduler = BackgroundScheduler()
executor = ThreadPoolExecutor(max_workers=1)

def convert_numpy_types(obj):
    """Convert numpy/pandas types to native Python types for JSON serialization"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    else:
        return obj

def get_actual_data_timestamp():
    """Get the ACTUAL data refresh timestamp"""
    # First, try to get timestamp from metadata file (most accurate)
    metadata_file = 'data_metadata.json'
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            if metadata.get('success', False) and metadata.get('scrape_end_time'):
                # Convert ISO format back to readable format
                end_time = datetime.fromisoformat(metadata['scrape_end_time'])
                return end_time.strftime('%Y-%m-%d %H:%M:%S UTC')
        except Exception as e:
            logger.warning(f"Error reading metadata file: {e}")

    # Fallback to file modification time of the actual data file
    data_files = [
        'lounge_thread_filtered_comments.json',
        '/app/lounge_thread_filtered_comments.json'
    ]

    for file_path in data_files:
        if os.path.exists(file_path):
            try:
                mod_time = os.path.getmtime(file_path)
                file_time = datetime.fromtimestamp(mod_time)
                return file_time.strftime('%Y-%m-%d %H:%M:%S UTC')
            except Exception:
                continue

    # If no data file exists, return a clear message
    return "No data available"

def load_and_process_data():
    """Load and process Reddit data - Mobile-optimized version"""
    try:
        data_files = [
            'lounge_thread_filtered_comments.json',
            '/app/lounge_thread_filtered_comments.json'
        ]

        data_file = None
        for file_path in data_files:
            if os.path.exists(file_path):
                data_file = file_path
                break

        if not data_file:
            logger.error("No data file found")
            return None

        with open(data_file, 'r') as f:
            comments_data = json.load(f)

        logger.info(f"Loaded {len(comments_data)} comments from {data_file}")

        if not comments_data:
            return None

        df = pd.DataFrame(comments_data)

        # Process ticker mentions
        ticker_mentions = {}
        ticker_comments = df[df['tickers'] != '']

        for _, row in ticker_comments.iterrows():
            if row['tickers']:
                tickers = [t.strip() for t in str(row['tickers']).split(',') if t.strip()]
                for ticker in tickers:
                    ticker_mentions[ticker] = ticker_mentions.get(ticker, 0) + 1

        top_10_tickers = sorted(ticker_mentions.items(), key=lambda x: x[1], reverse=True)[:10]

        # Top 20 comments
        top_20_comments = df.nlargest(20, 'score')[
            ['author', 'score', 'body', 'tickers', 'created_utc', 'author_total_karma']
        ].to_dict('records')

        # Watchlist comments
        watchlist_comments = df[
            (df['ticker_count'] >= 4) & 
            (df['author_total_karma'] >= 500)
        ].sort_values('score', ascending=False).head(10)[
            ['author', 'score', 'body', 'tickers', 'created_utc', 'author_total_karma', 'ticker_count']
        ].to_dict('records')

        # Latest comments for top tickers
        top_5_tickers = [ticker for ticker, _ in top_10_tickers[:5]]
        latest_comments_by_ticker = {}

        for ticker in top_5_tickers:
            ticker_comments_df = df[df['tickers'].str.contains(ticker, na=False, case=False)]
            latest_comments = ticker_comments_df.sort_values('created_utc', ascending=False).head(5)
            latest_comments_by_ticker[ticker] = latest_comments[
                ['author', 'score', 'body', 'created_utc', 'author_total_karma']
            ].to_dict('records')

        # Summary stats
        summary_stats = {
            'total_comments': int(len(df)),
            'comments_with_tickers': int(len(df[df['tickers'] != ''])),
            'unique_tickers': int(len(ticker_mentions)),
            'last_updated': get_actual_data_timestamp()
        }

        # Convert all numpy types to native Python types
        result = {
            'top_10_tickers': convert_numpy_types(top_10_tickers),
            'top_20_comments': convert_numpy_types(top_20_comments),
            'watchlist_comments': convert_numpy_types(watchlist_comments),
            'latest_comments_by_ticker': convert_numpy_types(latest_comments_by_ticker),
            'summary_stats': convert_numpy_types(summary_stats)
        }

        return result

    except Exception as e:
        logger.error(f"Error loading data: {e}")
        return None

def run_reddit_scraper():
    """Run the Reddit scraper in a separate thread - Non-blocking version"""
    global refresh_status

    try:
        refresh_status['is_running'] = True
        refresh_status['progress'] = 10
        refresh_status['last_error'] = None

        logger.info("🕷️ Starting Reddit scraper via update_data.py...")

        # Update progress
        refresh_status['progress'] = 25

        # Run the update_data.py script with timeout
        result = subprocess.run([
            sys.executable, 'update_data.py'
        ], capture_output=True, text=True, timeout=1800)  # 30 minute timeout

        refresh_status['progress'] = 80

        if result.returncode == 0:
            logger.info("✅ Data update completed successfully")
            refresh_status['progress'] = 100
            refresh_status['last_refresh'] = datetime.now().isoformat()

            # Validate the output file
            if os.path.exists('lounge_thread_filtered_comments.json'):
                with open('lounge_thread_filtered_comments.json', 'r') as f:
                    data = json.load(f)
                if len(data) > 0:
                    logger.info(f"✅ Validated: {len(data)} comments collected")
                    return True
                else:
                    raise Exception("No comments found in output file")
            else:
                raise Exception("Output file not created")
        else:
            error_msg = f"Update script failed with code {result.returncode}: {result.stderr}"
            logger.error(f"❌ {error_msg}")
            refresh_status['last_error'] = error_msg
            return False

    except subprocess.TimeoutExpired:
        error_msg = "Data update timed out after 30 minutes"
        logger.error(f"⏰ {error_msg}")
        refresh_status['last_error'] = error_msg
        return False
    except Exception as e:
        error_msg = f"Data update error: {str(e)}"
        logger.error(f"❌ {error_msg}")
        refresh_status['last_error'] = error_msg
        return False
    finally:
        refresh_status['is_running'] = False
        refresh_status['progress'] = 0

def scheduled_scraper_job():
    """Background job that runs every 30 minutes"""
    logger.info("🕐 Running scheduled scraper job...")
    if not refresh_status['is_running']:
        executor.submit(run_reddit_scraper)
    else:
        logger.info("Scraper already running, skipping scheduled run")

@app.route('/')
def dashboard():
    """Main dashboard route"""
    data = load_and_process_data()
    if not data:
        return render_template('error.html', error="Unable to load data"), 500

    return render_template('dashboard.html', **data)

@app.route('/api/data')
def api_data():
    """API endpoint for data refresh"""
    try:
        data = load_and_process_data()
        if not data:
            return jsonify({'error': 'Error loading data'}), 500

        return jsonify(data)

    except Exception as e:
        logger.error(f"API data error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    """Non-blocking refresh endpoint"""
    global refresh_status

    try:
        if refresh_status['is_running']:
            return jsonify({
                'status': 'already_running',
                'message': 'Data refresh already in progress',
                'progress': refresh_status['progress'],
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
            })

        # Start the scraper in background (non-blocking)
        future = executor.submit(run_reddit_scraper)

        # Give it a moment to start
        time.sleep(0.5)

        return jsonify({
            'status': 'started',
            'message': 'Reddit data scraping started in background',
            'progress': refresh_status['progress'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        })

    except Exception as e:
        logger.error(f"Refresh error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }), 500

@app.route('/api/refresh/status')
def refresh_status_endpoint():
    """Get current refresh status"""
    global refresh_status

    return jsonify({
        'is_running': refresh_status['is_running'],
        'progress': refresh_status['progress'],
        'last_refresh': refresh_status['last_refresh'],
        'last_error': refresh_status['last_error'],
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        data = load_and_process_data()
        status = 'healthy' if data else 'unhealthy'

        return jsonify({
            'status': status,
            'refresh_running': refresh_status['is_running'],
            'data_timestamp': get_actual_data_timestamp(),
            'timestamp': datetime.now().isoformat(),
            'version': '4.0.0-mobile-responsive'
        }), 200 if data else 503
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    logger.info('Shutting down gracefully...')
    if scheduler.running:
        scheduler.shutdown(wait=False)
    executor.shutdown(wait=False)
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Initialize scheduler
def init_scheduler():
    """Initialize the background scheduler"""
    if not scheduler.running:
        # Add job to run every 30 minutes
        scheduler.add_job(
            func=scheduled_scraper_job,
            trigger=IntervalTrigger(minutes=30),
            id='reddit_scraper_job',
            name='Reddit Scraper - Every 30 minutes',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info("✅ Background scheduler started - will run every 30 minutes")
        
        # Run initial scrape if no data exists
        if not os.path.exists('lounge_thread_filtered_comments.json'):
            logger.info("🚀 No existing data found, running initial scrape...")
            executor.submit(run_reddit_scraper)

# Ensure scheduler shuts down when app stops
atexit.register(lambda: scheduler.shutdown() if scheduler.running else None)

if __name__ == '__main__':
    # Initialize scheduler
    init_scheduler()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
