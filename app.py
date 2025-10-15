from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
from math import radians, cos, sin, asin, sqrt

load_dotenv()
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///food_platform.db"
db = SQLAlchemy(app)


def haversine(lat1, lon1, lat2, lon2):
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return round(c * r, 2)


# User Table: Donor or NGO/Shelter
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    user_type = db.Column(db.String(10), nullable=False)  # 'donor' or 'ngo'
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


# Requests Table (status column removed)
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


@app.route("/")
def home():
    return render_template("index.html")


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

    listings = Listing.query.filter_by(donor_id=donor_id).all()
    pickup_requests = []
    for listing in listings:
        requests = Request.query.filter_by(listing_id=listing.id).all()
        for req in requests:
            ngo_user = User.query.get(req.ngo_id)
            pickup_requests.append(
                {"listing": listing, "ngo": ngo_user, "request": req}
            )

    # fetch approved and removed history for donor
    history_items = History.query.filter(
        History.donor_id == donor_id, History.status.in_(["approved", "removed"])
    ).all()
    request_history = []
    for h in history_items:
        ngo_user = User.query.get(h.ngo_id) if h.ngo_id else None
        request_history.append(
            {
                "id": h.id,
                "food_type": h.food_type,
                "quantity": h.quantity,
                "description": h.description,
                "ngo_name": ngo_user.name if ngo_user else None,
                "status": h.status,
            }
        )

    return render_template(
        "donor_dashboard.html",
        listings=listings,
        pickup_requests=pickup_requests,
        request_history=request_history,
    )


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


@app.route("/remove_listing/<int:listing_id>", methods=["POST"])
def remove_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    donor_id = session.get("user_id")
    history_entry = History(
        donor_id=donor_id,
        ngo_id=None,  # No NGO involved
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


@app.route("/update_request_status/<int:request_id>/<new_status>", methods=["POST"])
def update_request_status(request_id, new_status):
    req = Request.query.get_or_404(request_id)
    if new_status not in ["approved", "rejected"]:
        flash("Invalid status")
        return redirect(url_for("donor_dashboard"))

    listing = Listing.query.get(req.listing_id)
    if not listing:
        flash("Listing not found for this request.")
        return redirect(url_for("donor_dashboard"))

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
    return redirect(url_for("donor_dashboard"))


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

    # Available Donations - with distance
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
            distance = haversine(
                ngo.latitude, ngo.longitude, donor.latitude, donor.longitude
            )
        listings.append({"listing": listing, "donor": donor, "distance": distance})

    # My Requests
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
            distance = haversine(
                ngo.latitude, ngo.longitude, donor.latitude, donor.longitude
            )
        pending_requests.append((req, listing, donor, distance))

    # My History
    my_history_query = History.query.filter(
        History.ngo_id == ngo_id, History.status.in_(["approved", "rejected"])
    ).all()
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
            distance = haversine(
                ngo.latitude, ngo.longitude, donor.latitude, donor.longitude
            )
        h.donor = donor  # for template compatibility
        my_history.append((h, donor, distance))

    return render_template(
        "ngo_dashboard.html",
        listings=listings,
        pending_requests=pending_requests,
        my_history=my_history,
        ngo_profile_pic_url="/static/profile.jpg",
    )


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


@app.route("/listing/<int:listing_id>")
def listing_details(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    return render_template("listing_details.html", listing=listing)


@app.route("/profile", methods=["GET", "POST"])
def profile():
    user_id = session.get("user_id")
    user = User.query.get(user_id)
    if request.method == "POST":
        user.name = request.form["name"]
        user.address = request.form["address"]
        if user.user_type == "ngo":
            user.purpose = request.form["purpose"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]
        if new_password and new_password == confirm_password:
            user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash("Profile updated.")
    return render_template("profile.html", user=user)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
