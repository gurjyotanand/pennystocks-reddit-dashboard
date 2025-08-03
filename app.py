#!/usr/bin/env python3
"""
Reddit Penny Stocks Dashboard
Flask application for visualizing r/pennystocks data
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify
import os
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_data_refresh_timestamp():
    """Get the most accurate data refresh timestamp"""
    # Try to get timestamp from metadata file first (most accurate)
    metadata_file = 'data_metadata.json'
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                if metadata.get('success', False):
                    scrape_time = datetime.fromisoformat(metadata['scrape_end_time'])
                    return scrape_time.strftime('%Y-%m-%d %H:%M:%S UTC')
        except:
            pass

    # Fallback to file modification time
    data_files = [
        'lounge_thread_filtered_comments.json',
        'data/lounge_thread_filtered_comments.json',
        '/app/data/lounge_thread_filtered_comments.json'
    ]

    for file_path in data_files:
        if os.path.exists(file_path):
            mod_time = os.path.getmtime(file_path)
            return datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S UTC')

    return "Unknown"

def get_data_metadata():
    """Get additional metadata about the data"""
    metadata_file = 'data_metadata.json'
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def load_and_process_data():
    """Load and process the Reddit data"""
    try:
        # Try different possible locations for the data file
        data_files = [
            'lounge_thread_filtered_comments.json',
            'data/lounge_thread_filtered_comments.json',
            '/app/data/lounge_thread_filtered_comments.json'
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

        # 1. Top 10 tickers based on mentions
        ticker_mentions = {}
        ticker_comments = df[df['tickers'] != '']

        for _, row in ticker_comments.iterrows():
            if row['tickers']:
                tickers = [t.strip() for t in str(row['tickers']).split(',') if t.strip()]
                for ticker in tickers:
                    ticker_mentions[ticker] = ticker_mentions.get(ticker, 0) + 1

        top_10_tickers = sorted(ticker_mentions.items(), key=lambda x: x[1], reverse=True)[:10]

        # 2. Top 20 comments based on score
        top_20_comments = df.nlargest(20, 'score')[
            ['author', 'score', 'body', 'tickers', 'created_utc', 'author_total_karma']
        ].to_dict('records')

        # 3. WATCHLIST - High-quality comments with multiple tickers from experienced users
        watchlist_comments = df[
            (df['ticker_count'] >= 4) & 
            (df['author_total_karma'] >= 500)
        ].sort_values('score', ascending=False).head(10)[
            ['author', 'score', 'body', 'tickers', 'created_utc', 'author_total_karma', 'ticker_count']
        ].to_dict('records')

        # 4. Latest 5 comments for top 5 tickers
        top_5_tickers = [ticker for ticker, _ in top_10_tickers[:5]]
        latest_comments_by_ticker = {}

        for ticker in top_5_tickers:
            ticker_comments_df = df[df['tickers'].str.contains(ticker, na=False, case=False)]
            latest_comments = ticker_comments_df.sort_values('created_utc', ascending=False).head(5)
            latest_comments_by_ticker[ticker] = latest_comments[
                ['author', 'score', 'body', 'created_utc', 'author_total_karma']
            ].to_dict('records')

        # Get precise data refresh timestamp
        data_refresh_time = get_data_refresh_timestamp()
        metadata = get_data_metadata()

        # Summary stats
        summary_stats = {
            'total_comments': len(df),
            'comments_with_tickers': len(df[df['tickers'] != '']),
            'unique_tickers': len(ticker_mentions),
            'avg_score': round(df['score'].mean(), 2),
            'max_score': df['score'].max(),
            'users_1000_karma': len(df[df['author_total_karma'] >= 1000]),
            'last_updated': data_refresh_time,
            'scrape_duration': metadata.get('scrape_duration_seconds', 0)
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

@app.route('/api/metadata')
def api_metadata():
    """API endpoint for data metadata"""
    metadata = get_data_metadata()
    return jsonify(metadata)

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error="Internal server error"), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
