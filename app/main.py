from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

db_path = os.path.join(os.path.dirname(__file__), 'data', 'strategy.db')
os.makedirs(os.path.dirname(db_path), exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------- MODELS ----------------

class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    amount = db.Column(db.Float)
    frequency = db.Column(db.String(50))  # Monthly, Bi-weekly, Weekly

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    amount = db.Column(db.Float)
    due_day = db.Column(db.Integer)

class Debt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    balance = db.Column(db.Float)
    interest_rate = db.Column(db.Float)  # APR %
    min_payment = db.Column(db.Float)
    extra_payment = db.Column(db.Float, default=0)  # Strategy money applied

with app.app_context():
    db.create_all()

# ---------------- MATH ENGINE ----------------

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

def simulate_payoff(debts, strategy="avalanche"):
    sim = [
        {
            "balance": float(d.balance),
            "apr": d.interest_rate / 100,
            "min": d.min_payment,
            "extra": d.extra_payment or 0
        } for d in debts
    ]

    if strategy == "avalanche":
        sim.sort(key=lambda x: x["apr"], reverse=True)
    else:  # snowball
        sim.sort(key=lambda x: x["balance"])

    months = 0
    total_interest = 0

    while any(d["balance"] > 0 for d in sim):
        months += 1
        for d in sim:
            if d["balance"] <= 0:
                continue

            interest = d["balance"] * (d["apr"] / 12)
            total_interest += interest
            d["balance"] += interest

            payment = min(d["min"] + d["extra"], d["balance"])
            d["balance"] -= payment

    return months, total_interest

# ---------------- ROUTES ----------------

@app.route('/')
def index():
    incomes = Income.query.all()
    bills = Bill.query.all()
    debts = Debt.query.all()

    monthly_income = get_monthly_income()
    total_bills = sum(b.amount for b in bills)
    total_minimums = sum(d.min_payment for d in debts)
    total_balance = sum(d.balance for d in debts)

    cashflow = monthly_income - total_bills - total_minimums

    backend_dti = ((total_bills + total_minimums) / monthly_income * 100) if monthly_income else 0

    avalanche_months, avalanche_interest = simulate_payoff(debts, "avalanche") if debts else (0, 0)
    snowball_months, snowball_interest = simulate_payoff(debts, "snowball") if debts else (0, 0)

    summary = {
        "income": monthly_income,
        "bills": total_bills,
        "cashflow": cashflow,
        "balance": total_balance,
        "dti": backend_dti,
        "ava_months": avalanche_months,
        "ava_interest": avalanche_interest,
        "snow_months": snowball_months,
        "snow_interest": snowball_interest
    }

    return render_template("index.html",
                           summary=summary,
                           debts=debts,
                           income_list=incomes,
                           bills_list=bills)

# ---------------- ADD DATA ----------------

@app.route('/add_income', methods=['POST'])
def add_income():
    db.session.add(Income(
        name=request.form['name'],
        amount=float(request.form['amount']),
        frequency=request.form['frequency']
    ))
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/add_bill', methods=['POST'])
def add_bill():
    db.session.add(Bill(
        name=request.form['name'],
        amount=float(request.form['amount']),
        due_day=int(request.form['due_day'])
    ))
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/add_debt', methods=['POST'])
def add_debt():
    db.session.add(Debt(
        name=request.form['name'],
        balance=float(request.form['balance']),
        interest_rate=float(request.form['apr']),
        min_payment=float(request.form['min_pay'])
    ))
    db.session.commit()
    return redirect(url_for('index'))

# ---------------- STRATEGY CONTROL ----------------

@app.route('/set_extra', methods=['POST'])
def set_extra():
    extra = float(request.form['extra'])
    debts = Debt.query.all()

    if debts:
        split = extra / len(debts)
        for d in debts:
            d.extra_payment = split

    db.session.commit()
    return redirect(url_for('index'))

# ---------------- DELETE ----------------

@app.route('/delete_debt/<int:id>')
def delete_debt(id):
    db.session.delete(Debt.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete_income/<int:id>')
def delete_income(id):
    db.session.delete(Income.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete_bill/<int:id>')
def delete_bill(id):
    db.session.delete(Bill.query.get_or_404(id))
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
