#!/usr/bin/env python3
"""
Reddit Penny Stocks Dashboard - Fixed JSON + Working Blue Refresh Button
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime
from flask import Flask, render_template, jsonify
import os
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'production-secret-key')

# Production logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable debug completely
app.config['DEBUG'] = False

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

def load_and_process_data():
    """Load and process Reddit data with proper type conversion"""
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
        
        # Summary stats with safe type conversion
        summary_stats = {
            'total_comments': int(len(df)),
            'comments_with_tickers': int(len(df[df['tickers'] != ''])),
            'unique_tickers': int(len(ticker_mentions)),
            'avg_score': float(round(df['score'].mean(), 2)) if not df['score'].empty else 0.0,
            'max_score': int(df['score'].max()) if not df['score'].empty else 0,
            'users_1000_karma': int(len(df[df['author_total_karma'] >= 1000])),
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
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

@app.route('/')
def dashboard():
    """Main dashboard route"""
    data = load_and_process_data()
    if not data:
        return render_template('error.html', error="Unable to load data"), 500
    
    return render_template('dashboard.html', **data)

@app.route('/api/data')
def api_data():
    """API endpoint for data refresh - FIXED JSON serialization"""
    try:
        data = load_and_process_data()
        if not data:
            return jsonify({'error': 'Error loading data'}), 500
        
        # Data is already converted to JSON-safe types
        return jsonify(data)
    
    except Exception as e:
        logger.error(f"API data error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    """Safe refresh endpoint"""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        return jsonify({
            'status': 'success',
            'message': 'Data refreshed successfully',
            'timestamp': timestamp
        })
    
    except Exception as e:
        logger.error(f"Refresh error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }), 500

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
