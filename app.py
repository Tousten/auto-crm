from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///autocrm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    vehicles = db.relationship('Vehicle', backref='customer', lazy=True)

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    make = db.Column(db.String(50))
    model = db.Column(db.String(50))
    year = db.Column(db.Integer)
    plate = db.Column(db.String(20))
    vin = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('register'))
        
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email')
        password = request.form.get('password')
        
        # Try to find user by username or email
        user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username/email or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    customer_count = Customer.query.filter_by(user_id=current_user.id).count()
    vehicle_count = Vehicle.query.join(Customer).filter(Customer.user_id == current_user.id).count()
    return render_template('dashboard.html', customer_count=customer_count, vehicle_count=vehicle_count)

@app.route('/customers')
@login_required
def customers():
    customers = Customer.query.filter_by(user_id=current_user.id).all()
    return render_template('customers.html', customers=customers)

@app.route('/customers/add', methods=['POST'])
@login_required
def add_customer():
    name = request.form.get('name')
    phone = request.form.get('phone')
    email = request.form.get('email')
    
    new_customer = Customer(user_id=current_user.id, name=name, phone=phone, email=email)
    db.session.add(new_customer)
    db.session.commit()
    
    flash('Customer added successfully!')
    return redirect(url_for('customers'))

# API endpoint for WhatsApp Sender
@app.route('/api/customers', methods=['POST'])
def api_add_customer():
    """API endpoint for WhatsApp Sender to add customers"""
    data = request.json
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    name = data.get('name')
    phone = data.get('phone')
    email = data.get('email', '')
    seller_id = data.get('seller_id')  # Can be null for NO SELLER
    
    if not name or not phone:
        return jsonify({"error": "Name and phone required"}), 400
    
    # Check if customer with this phone already exists
    existing = Customer.query.filter_by(phone=phone).first()
    if existing:
        return jsonify({
            "message": "Customer already exists",
            "customer_id": existing.id,
            "name": existing.name
        }), 200
    
    # Create new customer
    new_customer = Customer(
        user_id=seller_id,  # Can be None for NO SELLER
        name=name,
        phone=phone,
        email=email
    )
    db.session.add(new_customer)
    db.session.commit()
    
    return jsonify({
        "message": "Customer added successfully",
        "customer_id": new_customer.id,
        "name": new_customer.name
    }), 201

@app.route('/api/customers', methods=['GET'])
@login_required
def api_get_customers():
    """API endpoint to get customers for logged-in seller"""
    customers = Customer.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        "id": c.id,
        "name": c.name,
        "phone": c.phone,
        "email": c.email
    } for c in customers])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))