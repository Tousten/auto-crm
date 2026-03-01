from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
import urllib.parse
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'whatsapp-crm-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///whatsapp_crm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Admin credentials
ADMIN_USERNAME = '007'
ADMIN_PASSWORD_HASH = generate_password_hash('Gothard')

# Database Models
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    messages = db.relationship('Message', backref='customer', lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=db.func.current_timestamp())

# Create tables
with app.app_context():
    db.create_all()

# Public Routes
@app.route('/')
def index():
    return redirect(url_for('send_message'))

@app.route('/send', methods=['GET', 'POST'])
def send_message():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        message = request.form.get('message', '').strip()
        
        if name and phone and message:
            # Clean phone number
            phone_clean = clean_phone(phone)
            
            # Save or update customer
            customer = Customer.query.filter_by(phone=phone_clean).first()
            if not customer:
                customer = Customer(name=name, phone=phone_clean)
                db.session.add(customer)
                db.session.commit()
            
            # Save message
            msg = Message(customer_id=customer.id, message_text=message)
            db.session.add(msg)
            db.session.commit()
            
            # Generate WhatsApp link
            personalized_msg = message.replace('{nome}', name)
            encoded_msg = urllib.parse.quote(personalized_msg)
            wa_link = f"https://wa.me/{phone_clean}?text={encoded_msg}"
            
            return jsonify({
                'success': True,
                'whatsapp_link': wa_link,
                'message': 'Customer saved! Click the link to open WhatsApp.'
            })
        
        return jsonify({'success': False, 'error': 'All fields required'}), 400
    
    # GET - show form
    return render_template_string(HTML_PUBLIC)

def clean_phone(phone):
    digits = ''.join(c for c in phone if c.isdigit())
    if digits.startswith('00'):
        digits = digits[2:]
    if len(digits) <= 11 and not digits.startswith('55'):
        digits = '55' + digits
    return digits

# Admin Routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template_string(HTML_LOGIN, error='Invalid credentials')
    
    return render_template_string(HTML_LOGIN, error=None)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    
    customer_count = Customer.query.count()
    message_count = Message.query.count()
    recent_customers = Customer.query.order_by(Customer.created_at.desc()).limit(10).all()
    
    return render_template_string(HTML_ADMIN, 
        customer_count=customer_count,
        message_count=message_count,
        customers=recent_customers
    )

@app.route('/admin/customers')
def admin_customers():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    
    customers = Customer.query.order_by(Customer.created_at.desc()).all()
    return render_template_string(HTML_CUSTOMERS, customers=customers)

# HTML Templates
HTML_PUBLIC = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WhatsApp Sender</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #25d366 0%, #128c7e 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px; }
        .container { width: 100%; max-width: 500px; background: white; border-radius: 20px; box-shadow: 0 25px 80px rgba(0,0,0,0.3); overflow: hidden; }
        .header { background: #075e54; color: white; padding: 30px; text-align: center; }
        .header h1 { font-size: 1.5rem; }
        .content { padding: 30px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; color: #333; font-weight: 600; }
        input, textarea { width: 100%; padding: 15px; border: 2px solid #e0e0e0; border-radius: 12px; font-size: 1rem; }
        input:focus, textarea:focus { outline: none; border-color: #25d366; }
        button { width: 100%; padding: 15px; background: linear-gradient(135deg, #25d366 0%, #128c7e 100%); color: white; border: none; border-radius: 12px; font-size: 1.1rem; font-weight: 600; cursor: pointer; }
        .admin-link { text-align: center; margin-top: 20px; }
        .admin-link a { color: #666; text-decoration: none; }
        #result { margin-top: 20px; padding: 15px; border-radius: 10px; display: none; }
        #result.success { background: #d4edda; color: #155724; display: block; }
        #result.error { background: #f8d7da; color: #721c24; display: block; }
        .whatsapp-btn { display: inline-block; padding: 12px 30px; background: #25d366; color: white; text-decoration: none; border-radius: 25px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📱 WhatsApp Sender</h1>
        </div>
        <div class="content">
            <form id="senderForm">
                <div class="form-group">
                    <label>Customer Name</label>
                    <input type="text" name="name" required placeholder="João Silva">
                </div>
                <div class="form-group">
                    <label>Phone Number</label>
                    <input type="text" name="phone" required placeholder="11999999999">
                </div>
                <div class="form-group">
                    <label>Message</label>
                    <textarea name="message" rows="4" required placeholder="Olá {nome}! ...">Olá {nome}! Passando para lembrar sobre o serviço.</textarea>
                </div>
                <button type="submit">Send & Save</button>
            </form>
            <div id="result"></div>
            <div class="admin-link">
                <a href="/admin/login">🔐 Admin Login</a>
            </div>
        </div>
    </div>
    <script>
        document.getElementById('senderForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            const result = document.getElementById('result');
            
            try {
                const response = await fetch('/send', { method: 'POST', body: formData });
                const data = await response.json();
                
                if (data.success) {
                    result.className = 'success';
                    result.innerHTML = '✅ ' + data.message + '<br><a href="' + data.whatsapp_link + '" target="_blank" class="whatsapp-btn">Open WhatsApp</a>';
                } else {
                    result.className = 'error';
                    result.innerHTML = '❌ ' + data.error;
                }
            } catch (error) {
                result.className = 'error';
                result.innerHTML = '❌ Error: ' + error.message;
            }
        });
    </script>
</body>
</html>
'''

HTML_LOGIN = '''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Login</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; justify-content: center; align-items: center; }
        .login-box { background: white; padding: 40px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); width: 90%; max-width: 400px; }
        h1 { color: #333; margin-bottom: 30px; text-align: center; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; color: #666; font-weight: 600; }
        input { width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 8px; }
        button { width: 100%; padding: 14px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; }
        .error { background: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="login-box">
        <h1>🔐 Admin Login</h1>
        {% if error %}
            <div class="error">{{ error }}</div>
        {% endif %}
        <form method="POST">
            <div class="form-group">
                <label>Username</label>
                <input type="text" name="username" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit">Login</button>
        </form>
    </div>
</body>
</html>
'''

HTML_ADMIN = '''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f5f7fa; margin: 0; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px 40px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 1.5rem; }
        .nav a { color: white; text-decoration: none; margin-left: 20px; padding: 8px 16px; background: rgba(255,255,255,0.2); border-radius: 8px; }
        .container { max-width: 1200px; margin: 40px auto; padding: 0 20px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }
        .stat-card { background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); text-align: center; }
        .stat-card .number { font-size: 3rem; font-weight: bold; color: #667eea; }
        .recent { background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
        .recent h2 { color: #333; margin-bottom: 20px; }
        .customer-item { padding: 15px; border-bottom: 1px solid #e0e0e0; }
        .customer-item:last-child { border-bottom: none; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔧 Admin Dashboard</h1>
        <div class="nav">
            <a href="/admin">Dashboard</a>
            <a href="/admin/customers">All Customers</a>
            <a href="/admin/logout">Logout</a>
        </div>
    </div>
    <div class="container">
        <div class="stats">
            <div class="stat-card">
                <h3>Total Customers</h3>
                <div class="number">{{ customer_count }}</div>
            </div>
            <div class="stat-card">
                <h3>Total Messages</h3>
                <div class="number">{{ message_count }}</div>
            </div>
        </div>
        <div class="recent">
            <h2>Recent Customers</h2>
            {% for customer in customers %}
                <div class="customer-item">
                    <strong>{{ customer.name }}</strong> - {{ customer.phone }}
                </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
'''

HTML_CUSTOMERS = '''
<!DOCTYPE html>
<html>
<head>
    <title>All Customers</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f5f7fa; margin: 0; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px 40px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 1.5rem; }
        .nav a { color: white; text-decoration: none; margin-left: 20px; padding: 8px 16px; background: rgba(255,255,255,0.2); border-radius: 8px; }
        .container { max-width: 1200px; margin: 40px auto; padding: 0 20px; }
        .customer-list { background: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
        .customer-item { padding: 15px; border-bottom: 1px solid #e0e0e0; display: flex; justify-content: space-between; }
        .customer-item:last-child { border-bottom: none; }
        .phone { color: #666; font-family: monospace; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔧 All Customers</h1>
        <div class="nav">
            <a href="/admin">Dashboard</a>
            <a href="/admin/customers">All Customers</a>
            <a href="/admin/logout">Logout</a>
        </div>
    </div>
    <div class="container">
        <div class="customer-list">
            <h2>Customer List</h2>
            {% for customer in customers %}
                <div class="customer-item">
                    <span><strong>{{ customer.name }}</strong></span>
                    <span class="phone">{{ customer.phone }}</span>
                </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))