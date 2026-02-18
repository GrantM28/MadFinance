from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.secret_key = "secret_strategy_key"

# Database Setup
db_path = os.path.join(os.path.dirname(__file__), 'data', 'strategy.db')
if not os.path.exists(os.path.dirname(db_path)):
    os.makedirs(os.path.dirname(db_path))

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELS (Keep previous Income, Bill, Debt models) ---
# ... (Reference previous models from context) ...

@app.route('/')
def dashboard():
    # Math for DTI and Cashflow
    incomes = Income.query.all()
    bills = Bill.query.all()
    debts = Debt.query.all()
    
    # Simple Monthly Normalization
    total_inc = sum([(i.amount*2.166) if i.frequency == 'Bi-weekly' else i.amount for i in incomes])
    total_debt_pay = sum([d.min_payment for d in debts])
    total_bills = sum([b.amount for b in bills])
    
    cashflow = total_inc - total_debt_pay - total_bills
    dti = ((total_debt_pay + total_bills) / total_inc * 100) if total_inc > 0 else 0

    return render_template('dashboard.html', 
                           summary={"income": total_inc, "cashflow": cashflow, "dti": dti},
                           debt_count=len(debts))

@app.route('/income', methods=['GET', 'POST'])
def manage_income():
    if request.method == 'POST':
        new_inc = Income(name=request.form['name'], amount=float(request.form['amount']), frequency=request.form['frequency'])
        db.session.add(new_inc); db.session.commit()
        return redirect(url_for('manage_income'))
    return render_template('income.html', incomes=Income.query.all())

@app.route('/debt', methods=['GET', 'POST'])
def manage_debt():
    if request.method == 'POST':
        new_debt = Debt(name=request.form['name'], balance=float(request.form['balance']), interest_rate=float(request.form['apr']), min_payment=float(request.form['min_pay']))
        db.session.add(new_debt); db.session.commit()
        return redirect(url_for('manage_debt'))
    return render_template('debt.html', debts=Debt.query.all())

@app.route('/bills', methods=['GET', 'POST'])
def manage_bills():
    if request.method == 'POST':
        new_bill = Bill(name=request.form['name'], amount=float(request.form['amount']), due_day=int(request.form['due_day']))
        db.session.add(new_bill); db.session.commit()
        return redirect(url_for('manage_bills'))
    return render_template('bills.html', bills=Bill.query.all())

# Add delete routes for each type...

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)