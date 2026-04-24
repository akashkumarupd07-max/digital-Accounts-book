from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import pytz

app = Flask(__name__)

# --- DATABASE CONFIG FOR RENDER/POSTGRESQL ---
# Agar DATABASE_URL milta hai (Render par), toh wo use hoga, nahi toh local sqlite chaleba.
database_url = os.environ.get('DATABASE_URL', 'sqlite:///khata.db')

# Render ke DATABASE_URL mein 'postgres://' hota hai jise SQLAlchemy ke liye 'postgresql://' karna padta hai
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

def get_ist_time():
    return datetime.now(pytz.timezone('Asia/Kolkata'))

# --- MODELS ---
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    transactions = db.relationship('Transaction', backref='customer', lazy=True, cascade="all, delete-orphan")

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    t_type = db.Column(db.String(10)) # DEBIT (-) or CREDIT (+)
    note = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=get_ist_time)

# Database table create karne ke liye
with app.app_context():
    db.create_all()

# --- ROUTES ---

@app.route('/')
def index():
    customers = Customer.query.all()
    total_market_due = sum(c.balance for c in customers)
    
    now = get_ist_time()
    current_month_name = now.strftime('%B')
    
    m_debit = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.t_type == 'DEBIT',
        db.extract('month', Transaction.date) == now.month,
        db.extract('year', Transaction.date) == now.year
    ).scalar() or 0
    
    return render_template('index.html', customers=customers, total_due=total_market_due, m_debit=m_debit, current_month=current_month_name)

@app.route('/reports')
def reports():
    now = get_ist_time()
    monthly_data = []
    
    for m in range(1, 13):
        debit = db.session.query(db.func.sum(Transaction.amount)).filter(
            Transaction.t_type == 'DEBIT',
            db.extract('month', Transaction.date) == m,
            db.extract('year', Transaction.date) == now.year
        ).scalar() or 0
        
        credit = db.session.query(db.func.sum(Transaction.amount)).filter(
            Transaction.t_type == 'CREDIT',
            db.extract('month', Transaction.date) == m,
            db.extract('year', Transaction.date) == now.year
        ).scalar() or 0
        
        if debit > 0 or credit > 0:
            month_name = datetime(2000, m, 1).strftime('%B')
            monthly_data.append({'month': month_name, 'debit': debit, 'credit': credit})
            
    return render_template('reports.html', monthly_data=monthly_data[::-1], now=now.year)

@app.route('/customer/<int:c_id>')
def view_customer(c_id):
    customer = Customer.query.get_or_404(c_id)
    history = Transaction.query.filter_by(customer_id=c_id).order_by(Transaction.date.desc()).all()
    return render_template('customer.html', customer=customer, history=history)

@app.route('/add_customer', methods=['POST'])
def add_customer():
    name = request.form.get('name')
    phone = request.form.get('phone')
    if name and phone:
        new_cust = Customer(name=name, phone=phone)
        db.session.add(new_cust)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/transaction/<int:c_id>', methods=['POST'])
def transaction(c_id):
    amount_str = request.form.get('amount')
    if not amount_str:
        return redirect(url_for('index'))
    
    amount = float(amount_str)
    t_type = request.form.get('t_type') 
    note = request.form.get('note')
    
    customer = Customer.query.get(c_id)
    if t_type == 'DEBIT':
        customer.balance += amount
    else:
        customer.balance -= amount
        
    new_t = Transaction(customer_id=c_id, amount=amount, t_type=t_type, note=note, date=get_ist_time())
    db.session.add(new_t)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete_customer/<int:c_id>')
def delete_customer(c_id):
    customer = Customer.query.get_or_404(c_id)
    db.session.delete(customer)
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
                                        
