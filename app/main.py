from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

db_path = os.path.join(os.path.dirname(__file__), 'data', 'strategy.db')
if not os.path.exists(os.path.dirname(db_path)):
    os.makedirs(os.path.dirname(db_path))

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELS ---

class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    amount = db.Column(db.Float)
    frequency = db.Column(db.String(50)) # Monthly, Bi-weekly, Weekly

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    amount = db.Column(db.Float)
    due_day = db.Column(db.Integer)

class Debt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    balance = db.Column(db.Float)
    interest_rate = db.Column(db.Float) # APR
    min_payment = db.Column(db.Float)

with app.app_context():
    db.create_all()

# --- MATH ENGINE ---

def get_monthly_income():
    incomes = Income.query.all()
    total = 0
    for i in incomes:
        if i.frequency == 'Bi-weekly':
            total += (i.amount * 26) / 12
        elif i.frequency == 'Weekly':
            total += (i.amount * 52) / 12
        else:
            total += i.amount
    return total

@app.route('/')
def index():
    incomes = Income.query.all()
    bills = Bill.query.all()
    debts = Debt.query.all()
    
    monthly_inc = get_monthly_income()
    total_bills = sum(b.amount for b in bills)
    total_min_debt = sum(d.min_payment for d in debts)
    total_debt_balance = sum(d.balance for d in debts)
    
    cashflow = monthly_inc - total_bills - total_min_debt
    dti = ((total_bills + total_min_debt) / monthly_inc * 100) if monthly_inc > 0 else 0
    
    summary = {
        "income": monthly_inc,
        "total_debt": total_debt_balance,
        "cashflow": cashflow,
        "dti": dti
    }
    
    return render_template('index.html', 
                           summary=summary,
                           debts=debts,
                           income_list=incomes,
                           bills_list=bills)

# --- ROUTES FOR ADDING DATA ---

@app.route('/add_income', methods=['POST'])
def add_income():
    new_inc = Income(name=request.form['name'], amount=float(request.form['amount']), frequency=request.form['frequency'])
    db.session.add(new_inc)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/add_bill', methods=['POST'])
def add_bill():
    new_bill = Bill(name=request.form['name'], amount=float(request.form['amount']), due_day=int(request.form['due_day']))
    db.session.add(new_bill)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/add_debt', methods=['POST'])
def add_debt():
    new_debt = Debt(name=request.form['name'], balance=float(request.form['balance']), 
                    interest_rate=float(request.form['apr']), min_payment=float(request.form['min_pay']))
    db.session.add(new_debt)
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)