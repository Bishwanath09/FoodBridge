# FoodBridge — HackHorizon 2K26

FoodBridge is a beginner-friendly food waste redistribution demo built with Flask, SQLite, HTML, CSS, and JavaScript.

## Features
- Add surplus-food listings
- Browse/search/filter available food
- Donation and discounted offers
- Reserve a quantity with server-side availability checks
- SQLite persistence
- Smart demo ranking using urgency, optional distance coordinates, and quantity needed
- Urgency badges and pickup deadline display
- Summary statistics

## Requirements
- Python 3.10 or newer
- Internet connection for the optional Google Fonts import; the website itself can work without it

## Run on Windows
1. Install Python from https://www.python.org/downloads/ . During setup, select **Add Python to PATH**.
2. Extract this ZIP to a folder, for example `C:\FoodBridge`.
3. Open that folder in File Explorer.
4. Click the address bar, type `cmd`, and press Enter.
5. Run:

   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   py -m pip install -r requirements.txt
   py app.py
   ```

6. Open http://127.0.0.1:5000 in your browser.
7. Keep the terminal open while using the website. Press `Ctrl+C` in the terminal to stop the server.

If `py` does not work, try `python` instead.

## Database
The file `foodbridge.db` is created automatically the first time `app.py` runs. It stores listings and reservations locally. Do not delete it if you want to keep your demo data.

## Smart matching logic
The demo assigns a score based on:
- Urgency: pickup deadline is approaching
- Distance: only when the recipient enters latitude and longitude and listings have coordinates
- Quantity fit: whether the listing can meet the requested quantity

This is a transparent demo score, not a machine-learning model. Real distance-aware recommendations need verified coordinates, and real deployments should add authentication, permissions, abuse prevention, and proper notification delivery.

## Important food-safety limitation
This project is a hackathon prototype, not a food-safety certification system. Providers must verify food handling, storage, allergens, and local rules. Do not redistribute food that may be unsafe. A pickup deadline alone does not prove food is safe.

## API endpoints
- `GET /api/health` — health check
- `GET /api/listings` — available listings with optional filters
- `POST /api/listings` — create a listing
- `POST /api/listings/<id>/reserve` — reserve a quantity
- `GET /api/stats` — demo statistics

## Before a real-world launch
Add user authentication, organization verification, reservation cancellation and collection confirmation, audit logs, input rate limiting, trusted geocoding, accessibility testing, secure deployment settings, and food-safety policy review.
