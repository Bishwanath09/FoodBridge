from flask import Flask, render_template, request, jsonify
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import math

app = Flask(__name__)
DB_PATH = Path(__file__).with_name("foodbridge.db")

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with connect_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            unit TEXT NOT NULL DEFAULT 'meals',
            provider TEXT NOT NULL,
            location TEXT NOT NULL,
            lat REAL,
            lon REAL,
            mode TEXT NOT NULL CHECK(mode IN ('Donation','Discounted')),
            price REAL NOT NULL DEFAULT 0,
            pickup_by TEXT NOT NULL,
            storage_notes TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'available',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL REFERENCES listings(id),
            recipient TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'reserved'
        );
        """)
        count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        if count == 0:
            examples = [
                ("Fresh vegetable meals", "Prepared meals", 18, "meals", "Green Bowl Cafe", "Bistupur, Jamshedpur", 22.787, 86.197, "Donation", 0, (now_local_naive().replace(second=0, microsecond=0) + __import__("datetime").timedelta(minutes=45)).isoformat(timespec="minutes"), "Prepared today; kept hot and covered."),
                ("Seasonal vegetables", "Produce", 12, "kg", "Fresh Basket Store", "Sakchi, Jamshedpur", 22.804, 86.202, "Discounted", 25, (now_local_naive().replace(second=0, microsecond=0) + __import__("datetime").timedelta(hours=3)).isoformat(timespec="minutes"), "Uncut vegetables; stored in a clean area."),
                ("Packaged bread", "Bakery", 24, "packs", "Sunrise Bakery", "Kadma, Jamshedpur", 22.805, 86.175, "Donation", 0, (now_local_naive().replace(second=0, microsecond=0) + __import__("datetime").timedelta(hours=6)).isoformat(timespec="minutes"), "Sealed packs; check packaging and label before collection.")
            ]
            conn.executemany("""INSERT INTO listings
            (title,category,quantity,unit,provider,location,lat,lon,mode,price,pickup_by,storage_notes,status,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'available', ?)""",
            [row + (datetime.now(timezone.utc).isoformat(),) for row in examples])

def now_local_naive():
    return datetime.now().astimezone().replace(tzinfo=None)

def distance_km(a_lat, a_lon, b_lat, b_lon):
    if None in (a_lat, a_lon, b_lat, b_lon):
        return None
    r = 6371
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = math.radians(b_lat-a_lat)
    dl = math.radians(b_lon-a_lon)
    x = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(min(1, math.sqrt(x)))

def listing_dict(row, recipient_lat=None, recipient_lon=None, needed_quantity=None):
    item = dict(row)
    try:
        deadline = datetime.fromisoformat(item["pickup_by"])
        remaining = (deadline - now_local_naive()).total_seconds()
    except (ValueError, TypeError):
        remaining = -1
    item["minutes_left"] = int(remaining // 60)
    item["expired"] = remaining <= 0
    item["distance_km"] = distance_km(recipient_lat, recipient_lon, item["lat"], item["lon"])
    # Transparent demo ranking: urgency, distance and whether the quantity meets the need.
    score = 0
    if remaining > 0:
        if remaining <= 60*60: score += 50
        elif remaining <= 3*60*60: score += 30
        elif remaining <= 6*60*60: score += 15
    if item["distance_km"] is not None:
        score += max(0, 30 - item["distance_km"] * 3)
    if needed_quantity:
        score += 20 if item["quantity"] >= needed_quantity else 5
    item["match_score"] = round(score)
    item["urgency"] = "Expired" if remaining <= 0 else ("Urgent" if remaining <= 60*60 else ("Soon" if remaining <= 3*60*60 else "Available"))
    return item

@app.route("/")
def home():
    return render_template("index.html")

@app.get("/api/listings")
def get_listings():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    mode = request.args.get("mode", "").strip()
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    needed = request.args.get("needed", type=int)
    with connect_db() as conn:
        rows = conn.execute("SELECT * FROM listings WHERE status='available' ORDER BY id DESC").fetchall()
    items = [listing_dict(r, lat, lon, needed) for r in rows]
    items = [x for x in items if not x["expired"]]
    if search:
        s = search.lower()
        items = [x for x in items if s in x["title"].lower() or s in x["location"].lower() or s in x["provider"].lower()]
    if category:
        items = [x for x in items if x["category"] == category]
    if mode:
        items = [x for x in items if x["mode"] == mode]
    items.sort(key=lambda x: (x["match_score"], -x["minutes_left"]), reverse=True)
    return jsonify(items)

@app.post("/api/listings")
def create_listing():
    data = request.get_json(silent=True) or {}
    required = ["title", "category", "quantity", "unit", "provider", "location", "mode", "pickup_by", "storage_notes"]
    missing = [k for k in required if not str(data.get(k, "")).strip()]
    if missing:
        return jsonify({"error": "Please fill in all required fields."}), 400
    try:
        quantity = int(data["quantity"])
        price = float(data.get("price") or 0)
        if quantity < 1 or price < 0:
            raise ValueError()
        deadline = datetime.fromisoformat(data["pickup_by"])
        if deadline <= now_local_naive():
            return jsonify({"error": "Pickup deadline must be in the future."}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Enter a valid quantity, price, and future pickup deadline."}), 400
    mode = data["mode"]
    if mode not in ("Donation", "Discounted"):
        return jsonify({"error": "Choose Donation or Discounted."}), 400
    with connect_db() as conn:
        cur = conn.execute("""INSERT INTO listings
        (title,category,quantity,unit,provider,location,lat,lon,mode,price,pickup_by,storage_notes,status,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'available', ?)""",
        (data["title"].strip(), data["category"], quantity, data["unit"], data["provider"].strip(),
         data["location"].strip(), data.get("lat"), data.get("lon"), mode, price,
         data["pickup_by"], data["storage_notes"].strip(), datetime.now(timezone.utc).isoformat()))
        new_id = cur.lastrowid
    return jsonify({"message": "Food listing added!", "id": new_id}), 201

@app.post("/api/listings/<int:listing_id>/reserve")
def reserve_listing(listing_id):
    data = request.get_json(silent=True) or {}
    recipient = str(data.get("recipient", "")).strip()
    try:
        quantity = int(data.get("quantity", 0))
    except (ValueError, TypeError):
        quantity = 0
    if not recipient or quantity < 1:
        return jsonify({"error": "Enter your name or organization and a valid quantity."}), 400
    with connect_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM listings WHERE id=? AND status='available'", (listing_id,)).fetchone()
        if not row:
            return jsonify({"error": "This listing is no longer available."}), 404
        try:
            deadline = datetime.fromisoformat(row["pickup_by"])
        except ValueError:
            deadline = now_local_naive()
        if deadline <= now_local_naive():
            conn.execute("UPDATE listings SET status='expired' WHERE id=?", (listing_id,))
            return jsonify({"error": "This listing has passed its pickup deadline."}), 400
        reserved = conn.execute("SELECT COALESCE(SUM(quantity),0) FROM reservations WHERE listing_id=? AND status='reserved'", (listing_id,)).fetchone()[0]
        available = row["quantity"] - reserved
        if quantity > available:
            return jsonify({"error": f"Only {available} {row['unit']} are left."}), 400
        conn.execute("INSERT INTO reservations (listing_id,recipient,quantity,created_at,status) VALUES (?,?,?,?, 'reserved')",
                     (listing_id, recipient, quantity, datetime.now(timezone.utc).isoformat()))
        if quantity == available:
            conn.execute("UPDATE listings SET status='reserved' WHERE id=?", (listing_id,))
    return jsonify({"message": f"Reserved {quantity} {row['unit']} successfully. Coordinate pickup with {row['provider']}."})

@app.get("/api/stats")
def stats():
    with connect_db() as conn:
        food_count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        available_count = conn.execute("SELECT COUNT(*) FROM listings WHERE status='available'").fetchone()[0]
        reserved_quantity = conn.execute("SELECT COALESCE(SUM(quantity),0) FROM reservations WHERE status='reserved'").fetchone()[0]
        reservation_count = conn.execute("SELECT COUNT(*) FROM reservations WHERE status='reserved'").fetchone()[0]
    return jsonify({"listings": food_count, "available": available_count, "reserved_quantity": reserved_quantity, "reservations": reservation_count})

@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "app": "FoodBridge"})

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
