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
    purpose = db.Column(db.String(200))  # For NGOs, optional

# Food Listing Table
class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    food_type = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    best_before = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(200), nullable=False)  # redundant for easy access

# Requests Table
class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'), nullable=False)
    ngo_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')

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
        password_hash = generate_password_hash(password)
        user = User(email=email, password_hash=password_hash, name=name, address=address, user_type=user_type, purpose=purpose)
        db.session.add(user)
        db.session.commit()
        flash('Signup successful. Please login.')
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
            flash('Invalid credentials')
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
            flash('Password updated. Please login.')
            return redirect(url_for('login'))
        else:
            flash('Email not found or passwords do not match')
    return render_template('forgot_password.html')

# Donor Dashboard
@app.route('/donor_dashboard')
def donor_dashboard():
    donor_id = session.get('user_id')  # assumes user_id is stored in session at login
    if donor_id is None:
        return redirect(url_for('login'))  # redirect if user not logged in

    listings = Listing.query.filter_by(donor_id=donor_id).all()
    return render_template('donor_dashboard.html', listings=listings)

@app.route('/edit_listing/<int:listing_id>', methods=['GET', 'POST'])
def edit_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)

    if request.method == 'POST':
        # update listing here
        listing.food_type = request.form['food_type']
        listing.quantity = request.form['quantity']
        listing.description = request.form['description']
        listing.best_before = request.form['best_before']
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
    listing.best_before = request.form['best_before']
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
    best_before = request.form['best_before']
    # Use donor's address from user object
    address = user.address
    # Create new listing
    listing = Listing(
        donor_id=user.id,
        food_type=food_type,
        quantity=quantity,
        description=description,
        best_before=best_before,
        address=address
    )
    db.session.add(listing)
    db.session.commit()
    flash("Listing added successfully.")
    return redirect(url_for('donor_dashboard'))

# NGO Dashboard
@app.route('/ngo_dashboard')
def ngo_dashboard():
    # Logic to display all listings with distance calculation
    return render_template('ngo_dashboard.html')

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