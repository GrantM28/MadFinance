from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.secret_key = "strategy_engine_secret"

# Database Setup
db_path = os.path.join(os.path.dirname(__file__), 'data', 'strategy.db')
if not os.path.exists(os.path.dirname(db_path)):
    os.makedirs(os.path.dirname(db_path))

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELS (Fixed: These must be defined before the routes use them) ---

class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(50), nullable=False) # Monthly, Bi-weekly, Weekly

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_day = db.Column(db.Integer)

class Debt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float, nullable=False) # APR
    min_payment = db.Column(db.Float, nullable=False)

with app.app_context():
    db.create_all()

# --- MATH ENGINE ---

def get_monthly_income_value():
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

# --- ROUTES ---

@app.route('/')
def dashboard():
    incomes = Income.query.all()
    bills = Bill.query.all()
    debts = Debt.query.all()
    
    total_inc = get_monthly_income_value()
    total_bills = sum(b.amount for b in bills)
    total_min_debt = sum(d.min_payment for d in debts)
    
    cashflow = total_inc - total_bills - total_min_debt
    dti = ((total_bills + total_min_debt) / total_inc * 100) if total_inc > 0 else 0
    
    summary = {
        "income": total_inc,
        "total_debt": sum(d.balance for d in debts),
        "cashflow": cashflow,
        "dti": dti
    }
    
    return render_template('dashboard.html', 
                           summary=summary, 
                           debt_count=len(debts))

@app.route('/income', methods=['GET', 'POST'])
def manage_income():
    if request.method == 'POST':
        new_inc = Income(
            name=request.form['name'], 
            amount=float(request.form['amount']), 
            frequency=request.form['frequency']
        )
        db.session.add(new_inc)
        db.session.commit()
        return redirect(url_for('manage_income'))
    incomes = Income.query.all()
    return render_template('income.html', incomes=incomes)

@app.route('/debt', methods=['GET', 'POST'])
def manage_debt():
    if request.method == 'POST':
        new_debt = Debt(
            name=request.form['name'], 
            balance=float(request.form['balance']), 
            interest_rate=float(request.form['apr']), 
            min_payment=float(request.form['min_pay'])
        )
        db.session.add(new_debt)
        db.session.commit()
        return redirect(url_for('manage_debt'))
    debts = Debt.query.all()
    return render_template('debt.html', debts=debts)

@app.route('/bills', methods=['GET', 'POST'])
def manage_bills():
    if request.method == 'POST':
        new_bill = Bill(
            name=request.form['name'], 
            amount=float(request.form['amount']), 
            due_day=int(request.form['due_day'])
        )
        db.session.add(new_bill)
        db.session.commit()
        return redirect(url_for('manage_bills'))
    bills = Bill.query.all()
    return render_template('bills.html', bills=bills)

# Delete Routes
@app.route('/delete/<string:category>/<int:id>')
def delete_item(category, id):
    model_map = {'income': Income, 'debt': Debt, 'bill': Bill}
    item = model_map[category].query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return redirect(request.referrer)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)