#!/usr/bin/env python3
"""
Reddit Penny Stocks Dashboard - Production Version
No auto-reload, optimized for production deployment
"""

import json
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, jsonify
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'production-secret-key')

# Production logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Disable Flask debug mode completely
app.config['DEBUG'] = False
app.config['TESTING'] = False

def get_data_refresh_timestamp():
    """Get the most accurate data refresh timestamp"""
    metadata_file = os.environ.get('METADATA_FILE_PATH', 'data_metadata.json')

    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                if metadata.get('success', False):
                    scrape_time = datetime.fromisoformat(metadata['scrape_end_time'])
                    return scrape_time.strftime('%Y-%m-%d %H:%M:%S UTC')
        except Exception as e:
            logger.warning(f"Error reading metadata file: {e}")

    # Fallback to file modification time
    data_file_paths = [
        'lounge_thread_filtered_comments.json',
        '/app/lounge_thread_filtered_comments.json'
    ]

    for file_path in data_file_paths:
        if os.path.exists(file_path):
            try:
                mod_time = os.path.getmtime(file_path)
                return datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S UTC')
            except Exception as e:
                logger.warning(f"Error getting modification time for {file_path}: {e}")

    return "Unknown"

def load_and_process_data():
    """Load and process the Reddit data with error handling"""
    try:
        # Try different possible locations for the data file
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
        df = pd.DataFrame(comments_data)

        if df.empty:
            logger.warning("DataFrame is empty")
            return None

        # Process data safely
        ticker_mentions = {}
        ticker_comments = df[df['tickers'] != '']

        for _, row in ticker_comments.iterrows():
            if row['tickers']:
                tickers = [t.strip() for t in str(row['tickers']).split(',') if t.strip()]
                for ticker in tickers:
                    ticker_mentions[ticker] = ticker_mentions.get(ticker, 0) + 1

        top_10_tickers = sorted(ticker_mentions.items(), key=lambda x: x[1], reverse=True)[:10]

        # Top 20 comments based on score
        top_20_comments = df.nlargest(20, 'score')[
            ['author', 'score', 'body', 'tickers', 'created_utc', 'author_total_karma']
        ].to_dict('records')

        # Watchlist - High-quality comments
        watchlist_comments = df[
            (df['ticker_count'] >= 2) & 
            (df['author_total_karma'] >= 1000)
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

        # Get data refresh timestamp
        data_refresh_time = get_data_refresh_timestamp()

        # Summary stats
        summary_stats = {
            'total_comments': len(df),
            'comments_with_tickers': len(df[df['tickers'] != '']),
            'unique_tickers': len(ticker_mentions),
            'avg_score': round(df['score'].mean(), 2) if not df['score'].empty else 0,
            'max_score': df['score'].max() if not df['score'].empty else 0,
            'users_1000_karma': len(df[df['author_total_karma'] >= 1000]),
            'last_updated': data_refresh_time
        }

        return {
            'top_10_tickers': top_10_tickers,
            'top_20_comments': top_20_comments,
            'watchlist_comments': watchlist_comments,
            'latest_comments_by_ticker': latest_comments_by_ticker,
            'summary_stats': summary_stats
        }

    except Exception as e:
        logger.error(f"Error loading data: {e}")
        import traceback
        traceback.print_exc()
        return None

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
    data = load_and_process_data()
    if not data:
        return jsonify({'error': 'Error loading data'}), 500

    return jsonify(data)

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        data = load_and_process_data()
        status = 'healthy' if data else 'unhealthy'

        return jsonify({
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0'
        }), 200 if data else 503
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error="Internal server error"), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Production settings - no debug, no auto-reload
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
