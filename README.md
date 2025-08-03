# Reddit Penny Stocks Dashboard

A real-time dashboard that analyzes and visualizes discussions from r/pennystocks subreddit.

## Features

- 📊 **Top 10 Tickers**: Most mentioned stock tickers with interactive charts
- 💬 **Top 20 Comments**: Highest scored comments with ticker analysis  
- ⭐ **Watchlist**: High-karma users mentioning multiple tickers
- 🔥 **Latest Comments**: Recent discussions for top 5 tickers
- 🔄 **Auto-refresh**: Data updates every 10 minutes
- 📱 **Responsive Design**: Works on desktop and mobile

## Project Structure

```
reddit-dashboard/
├── app.py                 # Main Flask application
├── reddit_scrapper.py     # Reddit data scraping script
├── templates/
│   └── dashboard.html     # Dashboard template
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── nixpacks.toml         # Coolify deployment config
├── update_data.py        # Data update script
├── setup_cron.sh         # Cron job setup
└── README.md            # This file
```

## Local Development

1. **Clone and setup**:
   ```bash
   git clone <your-repo>
   cd reddit-dashboard
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Add your data**:
   - Place `lounge_thread_filtered_comments.json` in the root directory
   - Place `reddit_scrapper.py` in the root directory
   - Place `tickers.json` in the root directory (for ticker validation)

3. **Run locally**:
   ```bash
   python app.py
   ```
   Visit `http://localhost:5000`

## Deployment on VPS with Coolify

### Prerequisites
- VPS with Coolify installed
- GitHub repository with your code
- Domain name (optional)

### Step 1: Prepare Your Repository

1. **Create a new GitHub repository**
2. **Push all files** including:
   - `app.py`
   - `templates/dashboard.html`
   - `requirements.txt`
   - `nixpacks.toml`
   - `reddit_scrapper.py`
   - `tickers.json`
   - Any sample data files

### Step 2: Deploy with Coolify

1. **Log into your Coolify dashboard**
2. **Create new application**:
   - Click "New Resource" → "Public Git Repository"
   - Enter your GitHub repository URL
   - Choose branch (usually `main` or `master`)

3. **Configure application**:
   - **Name**: `reddit-dashboard`
   - **Build Pack**: Nixpacks (auto-detected)
   - **Port**: `5000`
   - **Domain**: Set your domain or use Coolify's generated one

4. **Environment Variables** (if needed):
   - Add any Reddit API credentials
   - Set `FLASK_ENV=production`

5. **Deploy**:
   - Click "Deploy" button
   - Monitor the build logs
   - Wait for deployment to complete

### Step 3: Setup Automatic Data Updates

Since Coolify doesn't have built-in cron jobs, you have a few options:

#### Option A: External Cron Job (Recommended)
1. **SSH into your VPS**:
   ```bash
   ssh user@your-vps-ip
   ```

2. **Create update script**:
   ```bash
   nano /home/user/update_reddit_data.sh
   ```

   Add:
   ```bash
   #!/bin/bash
   cd /path/to/your/app
   docker exec $(docker ps -qf "name=reddit-dashboard") python update_data.py
   ```

3. **Make executable and add to cron**:
   ```bash
   chmod +x /home/user/update_reddit_data.sh
   crontab -e
   ```

   Add line:
   ```
   */10 * * * * /home/user/update_reddit_data.sh >> /var/log/reddit_update.log 2>&1
   ```

#### Option B: Background Service
Deploy the data updater as a separate service:

1. **Create second application** in Coolify
2. **Use same repository** but different start command
3. **Set start command**: `python update_data.py && sleep 600 && python update_data.py`
4. **Configure** as a background service

#### Option C: GitHub Actions (Advanced)
Set up GitHub Actions to update data and trigger redeployment.

### Step 4: Configure Persistence

1. **Add volume mount** in Coolify:
   - Mount: `/app/data`
   - This will persist your JSON data files between deployments

2. **Update file paths** in your scripts to use `/app/data/`

### Step 5: Monitoring and Logs

1. **View application logs** in Coolify dashboard
2. **Monitor cron job logs**: `tail -f /var/log/reddit_update.log`
3. **Check application health** via the dashboard URL

## Configuration

### Reddit API Setup
1. Get Reddit API credentials from https://www.reddit.com/prefs/apps
2. Update `reddit_scrapper.py` with your credentials
3. Add credentials as environment variables in Coolify

### Customization
- **Update interval**: Modify cron schedule (default: every 10 minutes)
- **Data filters**: Adjust karma/age filters in `reddit_scrapper.py`
- **Dashboard styling**: Modify `templates/dashboard.html`
- **Ticker validation**: Update `tickers.json` with valid ticker symbols

## Troubleshooting

### Common Issues

1. **"Bad Gateway" Error**:
   - Check if app is running on correct port (5000)
   - Verify Coolify port configuration
   - Check application logs

2. **Data Not Updating**:
   - Verify cron job is running: `crontab -l`
   - Check update logs: `tail -f /var/log/reddit_update.log`
   - Ensure file permissions are correct

3. **Memory Issues**:
   - Monitor resource usage in Coolify
   - Consider upgrading VPS plan
   - Optimize data processing in scripts

4. **Reddit API Limits**:
   - Add delays between API calls
   - Implement proper error handling
   - Cache data when possible

### Debugging Commands

```bash
# Check container status
docker ps | grep reddit-dashboard

# View application logs
docker logs $(docker ps -qf "name=reddit-dashboard")

# Execute commands in container
docker exec -it $(docker ps -qf "name=reddit-dashboard") /bin/bash

# Check file structure
docker exec $(docker ps -qf "name=reddit-dashboard") ls -la /app
```

## Performance Tips

1. **Database**: Consider PostgreSQL for larger datasets
2. **Caching**: Implement Redis for frequently accessed data  
3. **CDN**: Use CloudFlare for static assets
4. **Monitoring**: Set up Uptime Kuma for availability monitoring

## Security

1. **Environment Variables**: Store sensitive data in Coolify environment variables
2. **Rate Limiting**: Implement rate limiting for API endpoints
3. **HTTPS**: Enable SSL/TLS in Coolify
4. **Firewall**: Configure VPS firewall properly

## Support

For issues and questions:
1. Check Coolify documentation: https://coolify.io/docs
2. Reddit API documentation: https://www.reddit.com/dev/api/
3. Flask documentation: https://flask.palletsprojects.com/

## License

MIT License - feel free to modify and distribute.
