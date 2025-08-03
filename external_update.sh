#!/bin/bash
# external_update.sh - Safe production data updates

set -e

echo "🔄 Starting safe production data update..."

# Configuration
CONTAINER_NAME="your-reddit-dashboard"
BACKUP_DIR="./backups"
DATA_FILE="lounge_thread_filtered_comments.json"
METADATA_FILE="data_metadata.json"

# Create backup directory
mkdir -p $BACKUP_DIR

# Step 1: Backup current data
echo "📦 Backing up current data..."
docker cp $CONTAINER_NAME:/app/$DATA_FILE $BACKUP_DIR/${DATA_FILE}.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || echo "No existing data file"

# Step 2: Run data collection locally (safer)
echo "🕷️ Collecting new data locally..."
python3 reddit_scrapper.py

# Step 3: Validate new data
echo "✅ Validating new data..."
if [ ! -f "$DATA_FILE" ]; then
    echo "❌ Error: No data file generated"
    exit 1
fi

if [ ! -s "$DATA_FILE" ]; then
    echo "❌ Error: Data file is empty"
    exit 1
fi

# Step 4: Copy new data to container
echo "📤 Uploading new data to container..."
docker cp $DATA_FILE $CONTAINER_NAME:/app/$DATA_FILE
[ -f "$METADATA_FILE" ] && docker cp $METADATA_FILE $CONTAINER_NAME:/app/$METADATA_FILE

# Step 5: Restart container gracefully (optional)
echo "♻️ Restarting container gracefully..."
docker restart $CONTAINER_NAME

echo "✅ Data update completed successfully!"
echo "🌐 Your dashboard is now updated with fresh data"
