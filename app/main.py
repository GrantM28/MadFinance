from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, date
import os

app = Flask(__name__)
app.secret_key = "strategy_engine_secret"

# Database Setup
db_path = os.path.join(os.path.dirname(__file__), 'data', 'strategy.db')
os.makedirs(os.path.dirname(db_path), exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------- MODELS ----------------

class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(50), nullable=False)  # Monthly, Bi-weekly, Weekly
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
    interest_rate = db.Column(db.Float, nullable=False)  # APR %
    min_payment = db.Column(db.Float, nullable=False)

with app.app_context():
    db.create_all()

# ---------------- HELPERS ----------------

def _to_float(val, default=0.0):
    try:
        return float(val)
    except Exception:
        return default

def _parse_date(val):
    """Accept YYYY-MM-DD or blank."""
    if not val:
        return None
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except Exception:
        return None

def get_monthly_income_value():
    incomes = Income.query.all()
    total = 0.0
    for i in incomes:
        if i.frequency == 'Bi-weekly':
            total += (i.amount * 26) / 12
        elif i.frequency == 'Weekly':
            total += (i.amount * 52) / 12
        else:
            total += i.amount
    return total

def weighted_apr(debts):
    total_bal = sum(d.balance for d in debts) or 0.0
    if total_bal <= 0:
        return 0.0
    return sum((d.balance / total_bal) * d.interest_rate for d in debts)

def simulate_payoff(debts, extra_monthly=0.0, method="avalanche", max_months=600):
    """
    Monthly compounding payoff sim (good enough for planning).
    Returns:
      months, payoff_date, total_interest
    """
    if not debts:
        return 0, None, 0.0

    sim = [{
        "name": d.name,
        "bal": float(d.balance),
        "apr": float(d.interest_rate) / 100.0,
        "min": float(d.min_payment)
    } for d in debts]

    def sort_key(x):
        if method == "snowball":
            return (x["bal"], -x["apr"])
        return (-x["apr"], x["bal"])

    months = 0
    total_interest = 0.0
    start = date.today()

    # quick “impossible payoff” guard if minimums are too low (interest-only treadmill)
    # Not perfect, but prevents infinite loops.
    if all(d["bal"] > 0 for d in sim):
        monthly_interest_floor = sum(d["bal"] * (d["apr"] / 12) for d in sim)
        monthly_payment_floor = sum(d["min"] for d in sim) + max(extra_monthly, 0)
        if monthly_payment_floor <= monthly_interest_floor:
            return max_months, None, float("inf")

    while any(d["bal"] > 0.01 for d in sim):
        months += 1
        if months > max_months:
            return max_months, None, total_interest

        # interest accrues
        for d in sim:
            if d["bal"] <= 0:
                continue
            interest = d["bal"] * (d["apr"] / 12)
            total_interest += interest
            d["bal"] += interest

        # pay minimums
        for d in sim:
            if d["bal"] <= 0:
                continue
            pay = min(d["min"], d["bal"])
            d["bal"] -= pay

        # apply extra to priority debt
        extra = max(extra_monthly, 0.0)
        while extra > 0.01 and any(d["bal"] > 0.01 for d in sim):
            sim.sort(key=sort_key)
            target = next((x for x in sim if x["bal"] > 0.01), None)
            if not target:
                break
            pay = min(extra, target["bal"])
            target["bal"] -= pay
            extra -= pay

    payoff_date = start + timedelta(days=int(months * 30.4375))
    return months, payoff_date, total_interest

# ---------------- DASHBOARD ----------------

@app.route('/')
def dashboard():
    incomes = Income.query.order_by(Income.next_pay_date).all()
    bills = Bill.query.order_by(Bill.due_date).all()
    debts = Debt.query.all()

    # Build check-to-check schedule (your existing feature)
    paycheck_groups = []
    for i, inc in enumerate(incomes):
        if not inc.next_pay_date:
            continue

        start_date = inc.next_pay_date
        end_date = incomes[i+1].next_pay_date if (i+1 < len(incomes) and incomes[i+1].next_pay_date) else start_date + timedelta(days=14)

        period_bills = [b for b in bills if b.due_date and start_date <= b.due_date < end_date]
        debt_share = sum(d.min_payment for d in debts) / (len(incomes) if incomes else 1)

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

    monthly_inc = get_monthly_income_value()
    total_debt = sum(d.balance for d in debts)
    w_apr = weighted_apr(debts)
    total_bills = sum(b.amount for b in bills)
    total_min_debt = sum(d.min_payment for d in debts)
    total_obligations = total_bills + total_min_debt
    dti = (total_obligations / monthly_inc * 100) if monthly_inc > 0 else 0.0
    cashflow = monthly_inc - total_obligations

    # Strategy controls (persist in session)
    strat_method = session.get("strategy_method", "avalanche")
    extra_override = session.get("extra_override", None)

    # Default extra is your cashflow (attack power) but never negative
    extra_monthly = max(cashflow, 0.0) if extra_override is None else max(float(extra_override), 0.0)

    ava_m, ava_date, ava_int = simulate_payoff(debts, extra_monthly=extra_monthly, method="avalanche")
    snb_m, snb_date, snb_int = simulate_payoff(debts, extra_monthly=extra_monthly, method="snowball")

    summary = {
        "income": monthly_inc,
        "bills": total_bills,
        "debt_min": total_min_debt,
        "obligations": total_obligations,
        "cashflow": cashflow,
        "total_debt": total_debt,
        "weighted_apr": w_apr,
        "dti": dti,
        "extra_monthly": extra_monthly,
        "strategy_method": strat_method,
        "ava": {"months": ava_m, "date": ava_date, "interest": ava_int},
        "snb": {"months": snb_m, "date": snb_date, "interest": snb_int},
    }
    
    summary["ava_unreachable"] = (ava_int == float("inf"))
    summary["snb_unreachable"] = (snb_int == float("inf"))

    return render_template(
        'dashboard.html',
        groups=paycheck_groups,
        summary=summary
    )

@app.route('/strategy', methods=['POST'])
def set_strategy():
    method = request.form.get("method", "avalanche").strip().lower()
    if method not in ("avalanche", "snowball"):
        method = "avalanche"

    extra_raw = request.form.get("extra_override", "").strip()
    if extra_raw == "":
        session["extra_override"] = None
    else:
        session["extra_override"] = _to_float(extra_raw, 0.0)

    session["strategy_method"] = method
    return redirect(url_for("dashboard"))

# ---------------- INCOME ----------------

@app.route('/income', methods=['GET', 'POST'])
def manage_income():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        amount = _to_float(request.form.get('amount'), None)
        freq = request.form.get('frequency', 'Monthly')

        # IMPORTANT: don’t hard-crash if missing. Your old code did request.form['next_pay_date'] :contentReference[oaicite:3]{index=3}
        p_date = _parse_date(request.form.get('next_pay_date'))

        if not name or amount is None:
            flash("Income requires a name and amount.", "danger")
            return redirect(url_for('manage_income'))

        new_inc = Income(name=name, amount=float(amount), frequency=freq, next_pay_date=p_date)
        db.session.add(new_inc)
        db.session.commit()
        flash("Income added.", "success")
        return redirect(url_for('manage_income'))

    return render_template('income.html', incomes=Income.query.all())

# ---------------- DEBT ----------------

@app.route('/debt', methods=['GET', 'POST'])
def manage_debt():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        balance = _to_float(request.form.get('balance'), None)
        apr = _to_float(request.form.get('apr'), None)
        min_pay = _to_float(request.form.get('min_pay'), None)

        if not name or balance is None or apr is None or min_pay is None:
            flash("Debt requires name, balance, APR, and minimum payment.", "danger")
            return redirect(url_for('manage_debt'))

        new_debt = Debt(name=name, balance=float(balance), interest_rate=float(apr), min_payment=float(min_pay))
        db.session.add(new_debt)
        db.session.commit()
        flash("Debt added.", "success")
        return redirect(url_for('manage_debt'))

    return render_template('debt.html', debts=Debt.query.all())

# ---------------- BILLS ----------------

@app.route('/bills', methods=['GET', 'POST'])
def manage_bills():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        amount = _to_float(request.form.get('amount'), None)

        # FIX: don’t hard-crash on missing due_date (your error)
        # Your old code did request.form['due_date'] :contentReference[oaicite:4]{index=4}
        due_date_val = request.form.get('due_date')

        # Back-compat: if you ever had due_day in older forms
        due_day_val = request.form.get('due_day')

        d_date = _parse_date(due_date_val)
        if d_date is None and due_day_val:
            # Convert day-of-month into a date in current month (or next month if already passed)
            try:
                day = int(due_day_val)
                today = date.today()
                candidate = date(today.year, today.month, min(max(day, 1), 28))
                if candidate < today:
                    # move to next month safely
                    if today.month == 12:
                        candidate = date(today.year + 1, 1, min(max(day, 1), 28))
                    else:
                        candidate = date(today.year, today.month + 1, min(max(day, 1), 28))
                d_date = candidate
            except Exception:
                d_date = None

        if not name or amount is None:
            flash("Bill requires a name and amount.", "danger")
            return redirect(url_for('manage_bills'))

        if d_date is None:
            flash("Bill requires a valid due date.", "danger")
            return redirect(url_for('manage_bills'))

        new_bill = Bill(name=name, amount=float(amount), due_date=d_date)
        db.session.add(new_bill)
        db.session.commit()
        flash("Bill added.", "success")
        return redirect(url_for('manage_bills'))

    return render_template('bills.html', bills=Bill.query.order_by(Bill.due_date).all())

# ---------------- DELETE ----------------

@app.route('/delete/<string:category>/<int:id>')
def delete_item(category, id):
    model_map = {'income': Income, 'debt': Debt, 'bill': Bill}
    if category not in model_map:
        flash("Invalid delete category.", "danger")
        return redirect(request.referrer or url_for("dashboard"))
    item = model_map[category].query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash("Deleted.", "success")
    return redirect(request.referrer or url_for("dashboard"))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
