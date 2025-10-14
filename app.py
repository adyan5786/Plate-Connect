from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///food_platform.db'
db = SQLAlchemy(app)

# User Table: Donor or NGO/Shelter
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    user_type = db.Column(db.String(10), nullable=False)  # 'donor' or 'ngo'
    address = db.Column(db.String(200), nullable=False)
    purpose = db.Column(db.String(200))

# Food Listing Table
class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  
    donor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    food_type = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    address = db.Column(db.String(200), nullable=False)
    donor = db.relationship('User', backref='listings')

# Requests Table
class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'), nullable=False)
    ngo_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')

# History Table
class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ngo_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'), nullable=False) 
    food_type = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    address = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False) 

    donor = db.relationship('User', foreign_keys=[donor_id])
    ngo = db.relationship('User', foreign_keys=[ngo_id])
    listing = db.relationship('Listing')

# Helper Functions and Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        address = request.form['address']
        user_type = request.form['user_type']
        purpose = request.form.get('purpose', '')

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with that email already exists. Please login or use another email.', 'error')
            return redirect(url_for('signup'))

        password_hash = generate_password_hash(password)
        user = User(email=email, password_hash=password_hash, name=name, address=address, user_type=user_type, purpose=purpose)
        db.session.add(user)
        db.session.commit()
        flash('Signup successful. Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['user_type'] = user.user_type
            if user.user_type == 'donor':
                return redirect(url_for('donor_dashboard'))
            else:
                return redirect(url_for('ngo_dashboard'))
        else:
            flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        new_pass = request.form['new_pass']
        confirm_pass = request.form['confirm_pass']
        user = User.query.filter_by(email=email).first()
        if user and new_pass == confirm_pass:
            user.password_hash = generate_password_hash(new_pass)
            db.session.commit()
            flash('Password updated. Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Email not found or passwords do not match', 'error')
            return render_template('forgot_password.html')
    return render_template('forgot_password.html')

# Donor Dashboard
@app.route('/donor_dashboard')
def donor_dashboard():
    donor_id = session.get('user_id')
    if donor_id is None:
        return redirect(url_for('login'))

    listings = Listing.query.filter_by(donor_id=donor_id).all()
    pickup_requests = []
    for listing in listings:
        requests = Request.query.filter_by(listing_id=listing.id, status='pending').all()
        for req in requests:
            ngo_user = User.query.get(req.ngo_id)
            pickup_requests.append({'listing': listing, 'ngo': ngo_user, 'request': req})

    # fetch approved history for donor
    history_items = History.query.filter_by(donor_id=donor_id, status='approved').all()
    request_history = []
    for h in history_items:
        ngo_user = User.query.get(h.ngo_id)
        request_history.append({
            'id': h.id,
            'food_type': h.food_type,
            'quantity': h.quantity,
            'description': h.description,
            'ngo_name': ngo_user.name if ngo_user else "Unknown"
        })

    return render_template(
        'donor_dashboard.html',
        listings=listings,
        pickup_requests=pickup_requests,
        request_history=request_history
    )
    
@app.route('/edit_listing/<int:listing_id>', methods=['GET', 'POST'])
def edit_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)

    if request.method == 'POST':
        # update listing here
        listing.food_type = request.form['food_type']
        listing.quantity = request.form['quantity']
        listing.description = request.form['description']
        db.session.commit()
        return redirect(url_for('donor_dashboard'))

    return render_template('edit_listing.html', listing=listing)

@app.route('/remove_listing/<int:listing_id>', methods=['POST'])
def remove_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    db.session.delete(listing)
    db.session.commit()
    return redirect(url_for('donor_dashboard'))

@app.route('/update_listing/<int:listing_id>', methods=['POST'])
def update_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)

    # You might want to verify that the logged-in user owns the listing
    donor_id = session.get('user_id')
    if listing.donor_id != donor_id:
        abort(403)  # Forbidden

    listing.food_type = request.form['food_type']
    listing.quantity = request.form['quantity']
    listing.description = request.form['description']
    db.session.commit()
    return redirect(url_for('donor_dashboard'))

@app.route('/add_listing', methods=['POST'])
def add_listing():
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if user is None or user.user_type != 'donor':
        flash("Unauthorized.")
        return redirect(url_for('login'))
    # Get form data
    food_type = request.form['food_type']
    quantity = request.form['quantity']
    description = request.form['description']
    # Use donor's address from user object
    address = user.address
    # Create new listing
    listing = Listing(
        donor_id=user.id,
        food_type=food_type,
        quantity=quantity,
        description=description,
        address=address
    )
    db.session.add(listing)
    db.session.commit()
    flash("Listing added successfully.")
    return redirect(url_for('donor_dashboard'))

@app.route('/update_request_status/<int:request_id>/<new_status>', methods=['POST'])
def update_request_status(request_id, new_status):
    req = Request.query.get_or_404(request_id)
    if new_status not in ['approved', 'rejected']:
        flash('Invalid status')
        return redirect(url_for('donor_dashboard'))

    req.status = new_status
    db.session.commit()

    # Fetch the listing safely
    listing = Listing.query.get(req.listing_id)
    if not listing:
        flash("Listing not found for this request.")
        return redirect(url_for('donor_dashboard'))

    ngo_user = User.query.get(req.ngo_id)
    donor_user = User.query.get(listing.donor_id)

    # Save to History table with the listing_id
    history_entry = History(
        donor_id=donor_user.id,
        ngo_id=ngo_user.id,
        listing_id=listing.id,  # <-- This must never be None!
        food_type=listing.food_type,
        quantity=listing.quantity,
        description=listing.description,
        address=listing.address,
        status=new_status
    )
    db.session.add(history_entry)
    db.session.commit()

    # If approved, remove listing from Listing table
    if new_status == 'approved':
        db.session.delete(listing)
        db.session.commit()

    flash(f'Request has been {new_status}.')
    return redirect(url_for('donor_dashboard'))

# NGO Dashboard
@app.route('/ngo_dashboard')
def ngo_dashboard():
    ngo_id = session.get('user_id')
    if not ngo_id:
        return redirect(url_for('login'))

    # 1. Get IDs of listings already approved (i.e., not available)
    approved_listing_ids = [
        h.listing_id for h in History.query.filter_by(status='approved').all()
    ]
    # 2. Get IDs of listings already requested by THIS NGO (to exclude from available)
    requested_listing_ids = [
        req.listing_id for req in Request.query.filter_by(ngo_id=ngo_id).all()
    ]

    # 3. Show only listings NOT requested by this NGO and NOT already approved
    listings = Listing.query.filter(
        ~Listing.id.in_(requested_listing_ids + approved_listing_ids)
    ).all()

    # 4. My Requests: Only requests made by this NGO (with status)
    my_requests = (
        Request.query.filter_by(ngo_id=ngo_id)
        .join(Listing, Request.listing_id == Listing.id)
        .add_entity(Listing)
        .all()
    )

    return render_template(
        'ngo_dashboard.html',
        listings=listings,
        my_requests=my_requests,
        ngo_profile_pic_url='/static/profile.jpg'
    )

@app.route('/request_listing/<int:listing_id>', methods=['POST'])
def request_listing(listing_id):
    ngo_id = session.get('user_id')
    if not ngo_id:
        # handle not logged in
        return redirect(url_for('login'))

    # Check if already requested
    existing = Request.query.filter_by(listing_id=listing_id, ngo_id=ngo_id).first()
    if not existing:
        new_request = Request(listing_id=listing_id, ngo_id=ngo_id, status='pending')
        db.session.add(new_request)
        db.session.commit()

    return redirect(url_for('ngo_dashboard'))

@app.route('/listing/<int:listing_id>')
def listing_details(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    # Add any other data you want to show
    return render_template('listing_details.html', listing=listing)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if request.method == 'POST':
        # Update user info
        user.name = request.form['name']
        user.address = request.form['address']
        if user.user_type == 'ngo':
            user.purpose = request.form['purpose']
        # Handle password change
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        if new_password and new_password == confirm_password:
            user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash("Profile updated.")
    return render_template('profile.html', user=user)

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)