from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
import requests

# Ensure the instance folder exists in the same directory as app.py
base_dir = os.path.dirname(os.path.abspath(__file__))
instance_path = os.path.join(base_dir, "instance")
os.makedirs(instance_path, exist_ok=True)

# Initialize app and database
load_dotenv()
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
app = Flask(__name__, instance_path=instance_path)
app.secret_key = "your_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///food_platform.db"
db = SQLAlchemy(app)


# Function to get distance using Google Maps Directions API
def get_route_distance(origin_lat, origin_lon, dest_lat, dest_lon):
    cache_entry = DistanceCache.query.filter_by(
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
    ).first()

    if cache_entry:
        return cache_entry.distance_km

    api_key = GOOGLE_MAPS_API_KEY
    origin = f"{origin_lat},{origin_lon}"
    destination = f"{dest_lat},{dest_lon}"
    url = (
        f"https://maps.googleapis.com/maps/api/directions/json"
        f"?origin={origin}&destination={destination}&key={api_key}"
    )
    response = requests.get(url)
    data = response.json()
    if data["status"] == "OK" and data["routes"] and data["routes"][0]["legs"]:
        distance_km = round(data["routes"][0]["legs"][0]["distance"]["value"] / 1000, 2)
        new_cache = DistanceCache(
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            dest_lat=dest_lat,
            dest_lon=dest_lon,
            distance_km=distance_km,
        )
        db.session.add(new_cache)
        db.session.commit()
        return distance_km

    return None


# User Table: Donor or NGO/Shelter
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    user_type = db.Column(db.String(10), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    purpose = db.Column(db.String(200))


# Food Listing Table
class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    food_type = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    address = db.Column(db.String(200), nullable=False)
    donor = db.relationship("User", backref="listings")
    __table_args__ = {"sqlite_autoincrement": True}


# Requests Table
class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)
    ngo_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


# History Table
class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    ngo_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    listing_id = db.Column(db.Integer, db.ForeignKey("listing.id"), nullable=False)
    food_type = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    address = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False)

    donor = db.relationship("User", foreign_keys=[donor_id])
    ngo = db.relationship("User", foreign_keys=[ngo_id])
    listing = db.relationship("Listing")


# Distance Cache Table
class DistanceCache(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin_lat = db.Column(db.Float, nullable=False)
    origin_lon = db.Column(db.Float, nullable=False)
    dest_lat = db.Column(db.Float, nullable=False)
    dest_lon = db.Column(db.Float, nullable=False)
    distance_km = db.Column(db.Float, nullable=False)


# Routes and Views
@app.route("/")
def home():
    return render_template("index.html")


# Signup Route
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        name = request.form["name"]
        address = request.form["address"]
        latitude = request.form.get("latitude")
        longitude = request.form.get("longitude")
        user_type = request.form["user_type"]
        purpose = request.form.get("purpose", "")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash(
                "An account with that email already exists. Please login or use another email.",
                "error",
            )
            return redirect(url_for("signup"))

        if not latitude or not longitude:
            flash(
                "Please select a valid address from the suggestions to autofill location.",
                "error",
            )
            return redirect(url_for("signup"))

        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except ValueError:
            flash("Invalid location data. Please select a valid address.", "error")
            return redirect(url_for("signup"))

        password_hash = generate_password_hash(password)
        user = User(
            email=email,
            password_hash=password_hash,
            name=name,
            address=address,
            user_type=user_type,
            purpose=purpose,
            latitude=latitude,
            longitude=longitude,
        )
        db.session.add(user)
        db.session.commit()
        flash("Signup successful. Please login.", "success")
        return redirect(url_for("login"))
    google_maps_api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    return render_template("signup.html", google_maps_api_key=google_maps_api_key)


# Login Route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["user_type"] = user.user_type
            if user.user_type == "donor":
                return redirect(url_for("donor_dashboard"))
            else:
                return redirect(url_for("ngo_dashboard"))
        else:
            flash("Invalid credentials", "error")
    return render_template("login.html")


# Forgot Password Route
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]
        new_pass = request.form["new_pass"]
        confirm_pass = request.form["confirm_pass"]
        user = User.query.filter_by(email=email).first()
        if user and new_pass == confirm_pass:
            user.password_hash = generate_password_hash(new_pass)
            db.session.commit()
            flash("Password updated. Please login.", "success")
            return redirect(url_for("login"))
        else:
            flash("Email not found or passwords do not match", "error")
            return render_template("forgot_password.html")
    return render_template("forgot_password.html")


# Donor Dashboard
@app.route("/donor_dashboard")
def donor_dashboard():
    donor_id = session.get("user_id")
    if donor_id is None:
        return redirect(url_for("login"))

    user = User.query.get(donor_id)
    listings = Listing.query.filter_by(donor_id=donor_id).all()
    pickup_requests = []
    for listing in listings:
        requests = Request.query.filter_by(listing_id=listing.id).all()
        for req in requests:
            ngo_user = User.query.get(req.ngo_id)
            distance = None
            if (
                user
                and user.latitude
                and user.longitude
                and ngo_user
                and ngo_user.latitude
                and ngo_user.longitude
            ):
                distance = get_route_distance(
                    user.latitude, user.longitude, ngo_user.latitude, ngo_user.longitude
                )
            pickup_requests.append(
                {
                    "listing": listing,
                    "ngo": ngo_user,
                    "request": req,
                    "distance": distance,
                }
            )

    pickup_requests.sort(
        key=lambda x: (
            x["distance"] is None,
            x["distance"] if x["distance"] is not None else float("inf"),
        )
    )

    history_items = History.query.filter(
        History.donor_id == donor_id, History.status.in_(["approved", "removed"])
    ).all()
    request_history = []
    for h in history_items:
        ngo_user = User.query.get(h.ngo_id) if h.ngo_id else None
        distance = None
        if (
            user
            and user.latitude
            and user.longitude
            and ngo_user
            and ngo_user.latitude
            and ngo_user.longitude
        ):
            distance = get_route_distance(
                user.latitude, user.longitude, ngo_user.latitude, ngo_user.longitude
            )
        request_history.append(
            {
                "id": h.id,
                "food_type": h.food_type,
                "quantity": h.quantity,
                "description": h.description,
                "ngo_name": ngo_user.name if ngo_user else None,
                "ngo_address": ngo_user.address if ngo_user else None,
                "distance": distance,
                "status": h.status,
            }
        )

    return render_template(
        "donor_dashboard.html",
        listings=listings,
        pickup_requests=pickup_requests,
        request_history=request_history,
    )


# Edit Listing Route
@app.route("/edit_listing/<int:listing_id>", methods=["GET", "POST"])
def edit_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)

    if request.method == "POST":
        listing.food_type = request.form["food_type"]
        listing.quantity = request.form["quantity"]
        listing.description = request.form["description"]
        db.session.commit()
        return redirect(url_for("donor_dashboard"))

    return render_template("edit_listing.html", listing=listing)


# Remove Listing Route
@app.route("/remove_listing/<int:listing_id>", methods=["POST"])
def remove_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    donor_id = session.get("user_id")
    history_entry = History(
        donor_id=donor_id,
        ngo_id=None,
        listing_id=listing.id,
        food_type=listing.food_type,
        quantity=listing.quantity,
        description=listing.description,
        address=listing.address,
        status="removed",
    )
    db.session.add(history_entry)
    db.session.delete(listing)
    db.session.commit()
    return redirect(url_for("donor_dashboard"))


# Update Listing Route
@app.route("/update_listing/<int:listing_id>", methods=["POST"])
def update_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    donor_id = session.get("user_id")
    if listing.donor_id != donor_id:
        abort(403)
    listing.food_type = request.form["food_type"]
    listing.quantity = request.form["quantity"]
    listing.description = request.form["description"]
    db.session.commit()
    return redirect(url_for("donor_dashboard"))


# Add Listing Route
@app.route("/add_listing", methods=["POST"])
def add_listing():
    user_id = session.get("user_id")
    user = User.query.get(user_id)
    if user is None or user.user_type != "donor":
        flash("Unauthorized.")
        return redirect(url_for("login"))
    food_type = request.form["food_type"]
    quantity = request.form["quantity"]
    description = request.form["description"]
    address = user.address
    listing = Listing(
        donor_id=user.id,
        food_type=food_type,
        quantity=quantity,
        description=description,
        address=address,
    )
    db.session.add(listing)
    db.session.commit()
    return redirect(url_for("donor_dashboard"))


# Update Request Status Route
@app.route("/update_request_status/<int:request_id>/<new_status>", methods=["POST"])
def update_request_status(request_id, new_status):
    req = Request.query.get_or_404(request_id)
    if new_status not in ["approved", "rejected"]:
        flash("Invalid status")
        return redirect(url_for("donor_dashboard", tab="requests"))

    listing = Listing.query.get(req.listing_id)
    if not listing:
        flash("Listing not found for this request.")
        return redirect(url_for("donor_dashboard", tab="requests"))

    ngo_user = User.query.get(req.ngo_id)
    donor_user = User.query.get(listing.donor_id)

    history_entry = History(
        donor_id=donor_user.id,
        ngo_id=ngo_user.id,
        listing_id=listing.id,
        food_type=listing.food_type,
        quantity=listing.quantity,
        description=listing.description,
        address=listing.address,
        status=new_status,
    )
    db.session.add(history_entry)
    db.session.delete(req)
    db.session.commit()

    if new_status == "approved":
        db.session.delete(listing)
        db.session.commit()

    flash(f"Request has been {new_status}.")
    return redirect(url_for("donor_dashboard", tab="requests"))


# NGO Dashboard
@app.route("/ngo_dashboard")
def ngo_dashboard():
    ngo_id = session.get("user_id")
    if not ngo_id:
        return redirect(url_for("login"))

    ngo = User.query.get(ngo_id)
    approved_listing_ids = [
        h.listing_id for h in History.query.filter_by(status="approved").all()
    ]
    requested_listing_ids = [
        req.listing_id for req in Request.query.filter_by(ngo_id=ngo_id).all()
    ]
    listings_query = Listing.query.filter(
        ~Listing.id.in_(requested_listing_ids + approved_listing_ids)
    ).all()

    listings = []
    for listing in listings_query:
        donor = User.query.get(listing.donor_id)
        distance = None
        if (
            donor
            and donor.latitude
            and donor.longitude
            and ngo.latitude
            and ngo.longitude
        ):
            distance = get_route_distance(
                ngo.latitude, ngo.longitude, donor.latitude, donor.longitude
            )
        listings.append({"listing": listing, "donor": donor, "distance": distance})

    listings.sort(
        key=lambda x: (
            x["distance"] is None,
            x["distance"] if x["distance"] is not None else float("inf"),
        )
    )

    pending_requests_query = (
        Request.query.filter_by(ngo_id=ngo_id)
        .join(Listing, Request.listing_id == Listing.id)
        .add_entity(Listing)
        .all()
    )
    pending_requests = []
    for req, listing in pending_requests_query:
        donor = User.query.get(listing.donor_id)
        distance = None
        if (
            donor
            and donor.latitude
            and donor.longitude
            and ngo.latitude
            and ngo.longitude
        ):
            distance = get_route_distance(
                ngo.latitude, ngo.longitude, donor.latitude, donor.longitude
            )
        pending_requests.append((req, listing, donor, distance))

    pending_requests.sort(
        key=lambda x: (x[3] is None, x[3] if x[3] is not None else float("inf"))
    )

    my_history_query = (
        History.query.filter(
            History.ngo_id == ngo_id, History.status.in_(["approved", "rejected"])
        )
        .order_by(History.id.asc())
        .all()
    )
    my_history = []
    for h in my_history_query:
        donor = User.query.get(h.donor_id)
        distance = None
        if (
            donor
            and donor.latitude
            and donor.longitude
            and ngo.latitude
            and ngo.longitude
        ):
            distance = get_route_distance(
                ngo.latitude, ngo.longitude, donor.latitude, donor.longitude
            )
        h.donor = donor
        my_history.append((h, donor, distance))

    return render_template(
        "ngo_dashboard.html",
        listings=listings,
        pending_requests=pending_requests,
        my_history=my_history,
    )


# Request Listing Route
@app.route("/request_listing/<int:listing_id>", methods=["POST"])
def request_listing(listing_id):
    ngo_id = session.get("user_id")
    if not ngo_id:
        return redirect(url_for("login"))

    existing = Request.query.filter_by(listing_id=listing_id, ngo_id=ngo_id).first()
    if not existing:
        new_request = Request(listing_id=listing_id, ngo_id=ngo_id)
        db.session.add(new_request)
        db.session.commit()

    return redirect(url_for("ngo_dashboard"))


# Listing Details Route
@app.route("/listing/<int:listing_id>")
def listing_details(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    return render_template("listing_details.html", listing=listing)


# Logout Route
@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# Run the app
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
