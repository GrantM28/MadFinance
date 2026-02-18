from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
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

# --- MODELS ---
class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(50), nullable=False) 
    next_pay_date = db.Column(db.Date, nullable=True)

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=True)

class Debt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float, nullable=False)
    min_payment = db.Column(db.Float, nullable=False)

with app.app_context():
    db.create_all()

# --- MATH ENGINE ---
def get_monthly_income_value():
    incomes = Income.query.all()
    total = 0
    for i in incomes:
        if i.frequency == 'Bi-weekly': total += (i.amount * 26) / 12
        elif i.frequency == 'Weekly': total += (i.amount * 52) / 12
        else: total += i.amount
    return total

# --- ROUTES ---
@app.route('/')
def dashboard():
    incomes = Income.query.order_by(Income.next_pay_date).all()
    bills = Bill.query.order_by(Bill.due_date).all()
    debts = Debt.query.all()

    paycheck_groups = []
    for i, inc in enumerate(incomes):
        start_date = inc.next_pay_date
        # Window ends at next paycheck or 14 days later
        end_date = incomes[i+1].next_pay_date if i+1 < len(incomes) else start_date + timedelta(days=14)
        
        # Capture bills for this specific window
        period_bills = [b for b in bills if start_date <= b.due_date < end_date]
        # Distribute debt mins across checks for accuracy
        debt_share = sum([d.min_payment for d in debts]) / (len(incomes) if incomes else 1)
        
        bill_sum = sum(b.amount for b in period_bills)
        remainder = inc.amount - bill_sum - debt_share
        
        paycheck_groups.append({
            'date': start_date,
            'income': inc.amount,
            'bills': period_bills,
            'bill_total': bill_sum,
            'debt_min': debt_share,
            'remainder': remainder
        })

    # Strategic Metrics
    monthly_inc = get_monthly_income_value()
    total_debt = sum(d.balance for d in debts)
    avg_apr = sum(d.interest_rate for d in debts) / (len(debts) if debts else 1)
    
    # SAFETY: Fix for ZeroDivisionError
    total_obligations = sum(b.amount for b in bills) + sum(d.min_payment for d in debts)
    dti = (total_obligations / monthly_inc * 100) if monthly_inc > 0 else 0

    return render_template('dashboard.html', 
                           groups=paycheck_groups, 
                           total_debt=total_debt, 
                           avg_apr=avg_apr if debts else 0,
                           dti=dti,
                           summary={"income": monthly_inc, "cashflow": monthly_inc - total_obligations})

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