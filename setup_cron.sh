#!/bin/bash
# Cron setup script for data updates every 10 minutes

echo "Setting up cron job for Reddit data updates..."

# Get the current directory
CURRENT_DIR=$(pwd)
echo "Current directory: $CURRENT_DIR"

# Check if update_data.py exists
if [ ! -f "$CURRENT_DIR/update_data.py" ]; then
    echo "Error: update_data.py not found in $CURRENT_DIR"
    exit 1
fi

# Make sure the script is executable
chmod +x "$CURRENT_DIR/update_data.py"

# Create the cron job command
CRON_COMMAND="*/10 * * * * cd $CURRENT_DIR && python3 update_data.py >> $CURRENT_DIR/logs/cron.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "update_data.py"; then
    echo "Cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "update_data.py" | crontab -
fi

# Add the new cron job
(crontab -l 2>/dev/null; echo "$CRON_COMMAND") | crontab -

echo "Cron job added successfully!"
echo "Command: $CRON_COMMAND"
echo ""
echo "The data will be updated every 10 minutes."
echo "Check logs in: $CURRENT_DIR/logs/"
echo ""
echo "To view current cron jobs: crontab -l"
echo "To remove this cron job: crontab -e (then delete the line with update_data.py)"
echo ""
echo "Manual test: python3 $CURRENT_DIR/update_data.py"
