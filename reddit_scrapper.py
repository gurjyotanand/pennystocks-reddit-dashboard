import praw
import pandas as pd
from datetime import datetime, timedelta
import time
import json
import os
import logging
from typing import List, Dict, Any, Tuple
import reticker
from dotenv import load_dotenv
load_dotenv()

class RedditScraper:
    def __init__(self, client_id: str, client_secret: str, user_agent: str, 
                 min_comment_karma: int = 100, min_account_age_days: int = 30,
                 tickers_file: str = "tickers.json"):
        """
        Initialize Reddit scraper with API credentials and filtering parameters
        
        Args:
            client_id: Reddit API client ID
            client_secret: Reddit API client secret
            user_agent: User agent string for API requests
            min_comment_karma: Minimum comment karma required (default: 100)
            min_account_age_days: Minimum account age in days (default: 30)
            tickers_file: Path to JSON file containing valid tickers (default: "sample_tickers.json")
        """
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        
        self.min_comment_karma = min_comment_karma
        self.min_account_age_days = min_account_age_days
        
        # Initialize ticker extractor
        self.ticker_extractor = reticker.TickerExtractor()
        
        # Load valid tickers from JSON file
        self.valid_tickers = self.load_valid_tickers(tickers_file)

        # <-- NEW: Create a set of common words to exclude as tickers
        # This helps reduce false positives for words like "PR", "USA", "DD", "CEO", etc.
        self.excluded_tickers = {
            'A', 'I', 'GO', 'ON', 'IT', 'BE', 'DD', 'CEO', 'PR', 'USA', 'FOR', 
            'NOW', 'YOLO', 'THE', 'GAIN', 'LOSS', 'EPS', 'PE', 'BUY', 'SELL', 
            'HOLD', 'ALL', 'ARE', 'CAN', 'BIG', 'TOP', 'EOD', 'PM', 'AH'
        }
        
        # Setup logging
        self.setup_logging()
        
    def load_valid_tickers(self, tickers_file: str) -> set:
        """
        Load valid tickers from JSON file and return as a set for fast lookup
        Args:
            tickers_file: Path to JSON file containing ticker data (array format)
        Returns:
            Set of valid ticker symbols (uppercase)
        """
        try:
            with open(tickers_file, 'r', encoding='utf-8') as f:
                ticker_data = json.load(f)
            
            valid_tickers = set()
            if isinstance(ticker_data, list):
                for ticker in ticker_data:
                    if isinstance(ticker, str) and len(ticker) >= 1: # Allow 1-letter tickers for now
                        valid_tickers.add(ticker.upper())
            else:
                for item in ticker_data.values():
                    if 'ticker' in item:
                        valid_tickers.add(item['ticker'].upper())
            
            print(f"Loaded {len(valid_tickers)} valid tickers from {tickers_file}")
            return valid_tickers
            
        except FileNotFoundError:
            print(f"Error: Could not find ticker file '{tickers_file}'")
            return set()
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON format in '{tickers_file}'")
            return set()
        except Exception as e:
            print(f"Error loading tickers from {tickers_file}: {str(e)}")
            return set()
    
    def extract_and_validate_tickers(self, text: str) -> List[str]:
        """
        Extract tickers from text and validate against known stock tickers
        
        Args:
            text: Text to extract tickers from
            
        Returns:
            List of valid ticker symbols found in the text
        """
        if not text:
            return []
        
        if not self.valid_tickers:
            self.logger.warning("No valid tickers loaded - extraction will proceed but validation skipped")
        
        try:
            extracted_tickers = self.ticker_extractor.extract(text)
            
            if hasattr(self, '_debug_count'):
                self._debug_count += 1
            else:
                self._debug_count = 1
                
            if self._debug_count <= 5:
                self.logger.info(f"Debug - Text: {text[:100]}...")
                self.logger.info(f"Debug - Extracted: {extracted_tickers}")
            
            if not self.valid_tickers:
                return [ticker.upper() for ticker in extracted_tickers]
            
            # <-- MODIFIED: Validation logic now includes the exclusion list
            valid_tickers = []
            for ticker in extracted_tickers:
                ticker_upper = ticker.upper()
                # Step 1: Check if the ticker is in our exclusion list. If so, skip it.
                if ticker_upper in self.excluded_tickers:
                    continue
                
                # Step 2: Check if the ticker is in our master list of valid tickers.
                if ticker_upper in self.valid_tickers:
                    valid_tickers.append(ticker_upper)
            
            if self._debug_count <= 5 and extracted_tickers:
                self.logger.info(f"Debug - Valid tickers (after exclusion): {valid_tickers}")
            
            seen = set()
            unique_valid_tickers = []
            for ticker in valid_tickers:
                if ticker not in seen:
                    seen.add(ticker)
                    unique_valid_tickers.append(ticker)
            
            return unique_valid_tickers
            
        except Exception as e:
            self.logger.warning(f"Error extracting tickers from text '{text[:50]}...': {str(e)}")
            return []
        
    def setup_logging(self):
        """Setup logging configuration"""
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        log_filename = f"logs/reddit_scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Reddit scraper initialized with filters:")
        self.logger.info(f"- Minimum comment karma: {self.min_comment_karma}")
        self.logger.info(f"- Minimum account age: {self.min_account_age_days} days")
        self.logger.info(f"- Valid tickers loaded: {len(self.valid_tickers)}")
        self.logger.info(f"- Excluding {len(self.excluded_tickers)} common words as tickers.") # <-- NEW Log
        
    # ... (the rest of the class remains the same) ...
    def get_user_info(self, username: str) -> Dict[str, Any]:
        """
        Get user information including karma and account age
        
        Args:
            username: Reddit username
            
        Returns:
            Dictionary containing user info or None if user doesn't exist
        """
        try:
            if username == '[deleted]':
                return {
                    'username': '[deleted]',
                    'comment_karma': 0,
                    'account_age_days': 0,
                    'account_created': None,
                    'exists': False
                }
                
            user = self.reddit.redditor(username)
            
            # This will raise an exception if user doesn't exist
            created_utc = user.created_utc
            account_created = datetime.fromtimestamp(created_utc)
            account_age_days = (datetime.now() - account_created).days
            
            return {
                'username': username,
                'comment_karma': user.comment_karma,
                'link_karma': user.link_karma,
                'total_karma': user.comment_karma + user.link_karma,
                'account_age_days': account_age_days,
                'account_created': account_created,
                'exists': True
            }
            
        except Exception as e:
            self.logger.warning(f"Could not fetch user info for {username}: {str(e)}")
            return {
                'username': username,
                'comment_karma': 0,
                'account_age_days': 0,
                'account_created': None,
                'exists': False
            }
    
    def should_filter_comment(self, user_info: Dict[str, Any]) -> bool:
        """
        Determine if a comment should be filtered out based on user criteria
        
        Args:
            user_info: User information dictionary
            
        Returns:
            True if comment should be filtered out, False otherwise
        """
        if not user_info['exists']:
            return True
            
        if user_info['comment_karma'] < self.min_comment_karma:
            return True
            
        if user_info['account_age_days'] < self.min_account_age_days:
            return True
            
        return False
        
    def get_latest_lounge_thread(self, subreddit_name: str) -> Dict[str, Any]:
        """
        Get the latest "The Lounge" thread from a subreddit
        
        Args:
            subreddit_name: Name of the subreddit (without r/)
            
        Returns:
            Dictionary containing the latest lounge thread data or None if not found
        """
        subreddit = self.reddit.subreddit(subreddit_name)
        
        # Search for "The Lounge" threads and get the most recent one
        search_results = subreddit.search("The Lounge", sort='new', limit=10)
        
        for submission in search_results:
            # Check if the title contains "The Lounge" (case insensitive)
            if "lounge" in submission.title.lower():
                thread_data = {
                    'id': submission.id,
                    'title': submission.title,
                    'author': str(submission.author) if submission.author else '[deleted]',
                    'score': submission.score,
                    'upvote_ratio': submission.upvote_ratio,
                    'num_comments': submission.num_comments,
                    'created_utc': datetime.fromtimestamp(submission.created_utc),
                    'url': submission.url,
                    'selftext': submission.selftext,
                    'permalink': submission.permalink
                }
                return thread_data
        
        return None
    
    def get_all_thread_comments(self, thread_id: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Get ALL comments from a specific thread with filtering and ticker extraction
        
        Args:
            thread_id: Reddit thread ID
            
        Returns:
            Tuple of (filtered_comments, filtered_out_comments)
        """
        submission = self.reddit.submission(id=thread_id)
        submission.comment_sort = 'new'  # Sort by newest comments first
        submission.comments.replace_more(limit=None)  # Expand all "load more comments" links
        
        all_comments = []
        filtered_comments = []
        filtered_out_comments = []
        
        self.logger.info(f"Processing comments from thread: {submission.title}")
        
        total_comments = len(submission.comments.list())
        self.logger.info(f"Total comments found: {total_comments}")
        
        ticker_stats = {'total_comments_with_tickers': 0, 'total_unique_tickers': set()}
        
        for i, comment in enumerate(submission.comments.list(), 1):
            if i % 50 == 0:  # Log progress every 50 comments
                self.logger.info(f"Processing comment {i}/{total_comments}")
                
            # Get user information
            author_name = str(comment.author) if comment.author else '[deleted]'
            user_info = self.get_user_info(author_name)
            
            # Extract tickers from comment body
            extracted_tickers = self.extract_and_validate_tickers(comment.body)
            
            # Update ticker statistics
            if extracted_tickers:
                ticker_stats['total_comments_with_tickers'] += 1
                ticker_stats['total_unique_tickers'].update(extracted_tickers)
            
            # Add a small delay to avoid rate limiting
            time.sleep(0.1)
            
            comment_data = {
                'id': comment.id,
                'body': comment.body,
                'author': author_name,
                'score': comment.score,
                'created_utc': datetime.fromtimestamp(comment.created_utc),
                'parent_id': comment.parent_id,
                'is_submitter': comment.is_submitter,
                'permalink': comment.permalink,
                'depth': comment.depth,
                # Add user info
                'author_comment_karma': user_info['comment_karma'],
                'author_link_karma': user_info.get('link_karma', 0),
                'author_total_karma': user_info.get('total_karma', 0),
                'author_account_age_days': user_info['account_age_days'],
                'author_account_created': user_info['account_created'],
                'author_exists': user_info['exists'],
                # Add ticker information
                'tickers': ', '.join(extracted_tickers) if extracted_tickers else '',
                'ticker_count': len(extracted_tickers)
            }
            
            # Check if comment should be filtered
            if self.should_filter_comment(user_info):
                filtered_out_comments.append(comment_data)
                
                # Log the filtered comment
                reason = []
                if not user_info['exists']:
                    reason.append("deleted/suspended account")
                if user_info['comment_karma'] < self.min_comment_karma:
                    reason.append(f"low karma ({user_info['comment_karma']} < {self.min_comment_karma})")
                if user_info['account_age_days'] < self.min_account_age_days:
                    reason.append(f"new account ({user_info['account_age_days']} days < {self.min_account_age_days})")
                
                self.logger.info(f"Filtered out comment by {author_name}: {', '.join(reason)}")
            else:
                filtered_comments.append(comment_data)
        
        # Log filtering and ticker extraction summary
        total_filtered = len(filtered_out_comments)
        total_kept = len(filtered_comments)
        filter_percentage = (total_filtered / total_comments * 100) if total_comments > 0 else 0
        
        self.logger.info(f"\n=== FILTERING SUMMARY ===")
        self.logger.info(f"Total comments processed: {total_comments}")
        self.logger.info(f"Comments kept: {total_kept}")
        self.logger.info(f"Comments filtered out: {total_filtered}")
        self.logger.info(f"Filter percentage: {filter_percentage:.1f}%")
        
        self.logger.info(f"\n=== TICKER EXTRACTION SUMMARY ===")
        self.logger.info(f"Comments with valid tickers: {ticker_stats['total_comments_with_tickers']}")
        self.logger.info(f"Unique tickers found: {len(ticker_stats['total_unique_tickers'])}")
        if ticker_stats['total_unique_tickers']:
            self.logger.info(f"Tickers: {', '.join(sorted(ticker_stats['total_unique_tickers']))}")
        
        return filtered_comments, filtered_out_comments
    
    def get_latest_threads(self, subreddit_name: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Get the latest threads from a subreddit
        
        Args:
            subreddit_name: Name of the subreddit (without r/)
            limit: Maximum number of threads to fetch
            
        Returns:
            List of dictionaries containing thread data
        """
        subreddit = self.reddit.subreddit(subreddit_name)
        threads = []
        
        for submission in subreddit.new(limit=limit):
            thread_data = {
                'id': submission.id,
                'title': submission.title,
                'author': str(submission.author) if submission.author else '[deleted]',
                'score': submission.score,
                'upvote_ratio': submission.upvote_ratio,
                'num_comments': submission.num_comments,
                'created_utc': datetime.fromtimestamp(submission.created_utc),
                'url': submission.url,
                'selftext': submission.selftext,
                'permalink': submission.permalink
            }
            threads.append(thread_data)
            
        return threads
    
    def save_to_csv(self, data: List[Dict[str, Any]], filename: str):
        """
        Save data to CSV file
        
        Args:
            data: List of dictionaries to save
            filename: Name of the output CSV file
        """
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        self.logger.info(f"Data saved to {filename}")
    
    def save_to_json(self, data: List[Dict[str, Any]], filename: str):
        """
        Save data to JSON file
        
        Args:
            data: List of dictionaries to save
            filename: Name of the output JSON file
        """
        # Convert datetime objects to strings for JSON serialization
        json_data = []
        for item in data:
            json_item = item.copy()
            for key, value in json_item.items():
                if isinstance(value, datetime):
                    json_item[key] = value.isoformat()
            json_data.append(json_item)
            
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        self.logger.info(f"Data saved to {filename}")

def main():
    """
    Main function to get the latest "The Lounge" thread and all its comments with filtering and ticker extraction
    """
    # You need to get these credentials from Reddit
    # Go to https://www.reddit.com/prefs/apps and create a new app
    CLIENT_ID = os.getenv('CLIENT_ID')
    CLIENT_SECRET = os.getenv('CLIENT_SECRET')
    USER_AGENT = os.getenv('USER_AGENT', 'RedditScraper/1.0')
    
    # Initialize the scraper with filtering parameters and ticker validation
    scraper = RedditScraper(
        CLIENT_ID, 
        CLIENT_SECRET, 
        USER_AGENT,
        min_comment_karma=100,    # Filter out users with less than 100 comment karma
        min_account_age_days=30,  # Filter out accounts newer than 30 days
        tickers_file="tickers.json"  # Path to valid tickers JSON file
    )
    
    # Get the latest "The Lounge" thread from pennystocks subreddit
    print("Searching for the latest 'The Lounge' thread in pennystocks subreddit...")
    lounge_thread = scraper.get_latest_lounge_thread("pennystocks")
    
    if lounge_thread:
        print(f"Found latest 'The Lounge' thread:")
        print(f"Title: {lounge_thread['title']}")
        print(f"Author: {lounge_thread['author']}")
        print(f"Score: {lounge_thread['score']}")
        print(f"Comments: {lounge_thread['num_comments']}")
        print(f"Created: {lounge_thread['created_utc']}")
        print(f"URL: {lounge_thread['url']}")
        print()
        
        # Get ALL comments from the thread with filtering and ticker extraction
        print(f"Fetching ALL comments from: {lounge_thread['title']}")
        print("This may take a while for threads with many comments...")
        print("Applying filters: min 100 comment karma, min 30 days account age")
        print("Extracting and validating tickers from comment text...")
        
        filtered_comments, filtered_out_comments = scraper.get_all_thread_comments(lounge_thread['id'])
        
        print(f"\nRetrieved {len(filtered_comments)} comments after filtering")
        print(f"Filtered out {len(filtered_out_comments)} comments")
        
        # Save data to files
        # scraper.save_to_csv([lounge_thread], "latest_lounge_thread.csv")
        # scraper.save_to_json([lounge_thread], "latest_lounge_thread.json")
        
        if filtered_comments:
            # scraper.save_to_csv(filtered_comments, "lounge_thread_filtered_comments.csv")
            scraper.save_to_json(filtered_comments, "lounge_thread_filtered_comments.json")
            
            # Show some ticker statistics
            comments_with_tickers = [c for c in filtered_comments if c['tickers']]
            if comments_with_tickers:
                print(f"\nTicker Analysis:")
                print(f"Comments with tickers: {len(comments_with_tickers)}")
                
                # Count ticker mentions
                ticker_mentions = {}
                for comment in comments_with_tickers:
                    tickers = comment['tickers'].split(', ')
                    for ticker in tickers:
                        if ticker:  # Skip empty strings
                            ticker_mentions[ticker] = ticker_mentions.get(ticker, 0) + 1
                
                if ticker_mentions:
                    print("Most mentioned tickers:")
                    sorted_tickers = sorted(ticker_mentions.items(), key=lambda x: x[1], reverse=True)
                    for ticker, count in sorted_tickers[:10]:  # Top 10
                        print(f"  {ticker}: {count} mentions")
            
        # Also save filtered out comments for analysis
        # if filtered_out_comments:
        #     scraper.save_to_csv(filtered_out_comments, "lounge_thread_filtered_out_comments.csv")
        #     scraper.save_to_json(filtered_out_comments, "lounge_thread_filtered_out_comments.json")
                      
    else:
        print("No 'The Lounge' thread found in pennystocks subreddit")
        print("The thread might not exist or might have a different title")

if __name__ == "__main__":
    main()