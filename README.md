# Cracker Shop Billing System

Enhanced billing application for cracker shops with GST calculations and database storage.

## Features
- Web-based billing interface
- GST/tax calculations
- SQLite database for record keeping
- Bill generation and printing
- Customer management

## Local Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Run the application
python enhanced_billing.py
```

## Render Deployment
1. Connect your GitHub repository to Render
2. Create a new Web Service
3. Use these settings:
   - **Build Command**: `pip install -r requirements.txt` (optional, no deps needed)
   - **Start Command**: `python enhanced_billing.py`
   - **Environment**: Python 3

## Usage
1. Start the application
2. Open browser to the provided URL
3. Create bills and manage inventory
