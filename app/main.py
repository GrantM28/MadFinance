from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, date
import calendar
import os
import math

app = Flask(__name__)
app.secret_key = "finance_strategy_engine_secret"

# ---------------- DB ----------------
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

class PlannedPayment(db.Model):
    """
    Monthly Schedule items (what your wife does in Excel)
    Ex: 02/01/2026 : BHG Loan : $400
    """
    id = db.Column(db.Integer, primary_key=True)
    pay_date = db.Column(db.Date, nullable=False)
    name = db.Column(db.String(140), nullable=False)  # "BHG Loan", "Trash", etc
    amount = db.Column(db.Float, nullable=False)
    kind = db.Column(db.String(30), nullable=False, default="debt")  # debt, bill, other (for filtering/colors)

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.String(200), nullable=False)

with app.app_context():
    db.create_all()

# ---------------- HELPERS ----------------

def _to_float(val, default=None):
    try:
        return float(val)
    except Exception:
        return default

def _parse_date(val):
    if not val:
        return None
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except Exception:
        return None

def get_setting(key, default=None):
    s = Setting.query.filter_by(key=key).first()
    return s.value if s else default

def set_setting(key, value):
    s = Setting.query.filter_by(key=key).first()
    if not s:
        s = Setting(key=key, value=str(value))
        db.session.add(s)
    else:
        s.value = str(value)
    db.session.commit()

def bool_setting(key, default=False):
    v = get_setting(key, None)
    if v is None:
        return default
    return str(v).lower() in ("1", "true", "yes", "on")

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

def month_bounds(year, month):
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    last = date(year, month, last_day)
    return first, last

def parse_month_param(month_str):
    # expects YYYY-MM
    if not month_str:
        today = date.today()
        return today.year, today.month
    try:
        y, m = month_str.split("-")
        y = int(y); m = int(m)
        if m < 1 or m > 12:
            raise ValueError
        return y, m
    except Exception:
        today = date.today()
        return today.year, today.month

def simulate_payoff(debts, extra_monthly=0.0, method="avalanche", max_months=600):
    """
    Monthly compounding sim.
    Uses min payments + extra (attack power).
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

    monthly_payment_floor = sum(d["min"] for d in sim) + max(extra_monthly, 0)
    monthly_interest_floor = sum(d["bal"] * (d["apr"] / 12) for d in sim)
    if monthly_payment_floor <= monthly_interest_floor:
        return max_months, None, float("inf")

    while any(d["bal"] > 0.01 for d in sim):
        months += 1
        if months > max_months:
            return max_months, None, total_interest

        # interest
        for d in sim:
            if d["bal"] <= 0:
                continue
            interest = d["bal"] * (d["apr"] / 12)
            total_interest += interest
            d["bal"] += interest

        # mins
        for d in sim:
            if d["bal"] <= 0:
                continue
            pay = min(d["min"], d["bal"])
            d["bal"] -= pay

        # extra
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

@app.route("/")
def dashboard():
    debts = Debt.query.all()
    bills = Bill.query.all()

    monthly_income = get_monthly_income_value()
    total_debt = sum(d.balance for d in debts)
    total_min_debt = sum(d.min_payment for d in debts)
    total_bills = sum(b.amount for b in bills)
    obligations = total_bills + total_min_debt
    cashflow = monthly_income - obligations

    # DTI: you asked about bills being included.
    # We'll show BOTH:
    # - cashflow burden: bills + debt mins
    # - lender-ish DTI: debt mins only (and you can add "housing_in_dti" later)
    cashflow_burden_pct = (obligations / monthly_income * 100) if monthly_income > 0 else 0.0
    lender_dti_pct = (total_min_debt / monthly_income * 100) if monthly_income > 0 else 0.0

    w_apr = weighted_apr(debts)

    # Strategy controls
    method = session.get("strategy_method", get_setting("default_strategy", "avalanche") or "avalanche")
    extra_override = session.get("extra_override", None)
    extra_monthly = max(cashflow, 0.0) if extra_override is None else max(float(extra_override), 0.0)

    ava_m, ava_date, ava_int = simulate_payoff(debts, extra_monthly, "avalanche")
    snb_m, snb_date, snb_int = simulate_payoff(debts, extra_monthly, "snowball")

    summary = {
        "monthly_income": monthly_income,
        "total_debt": total_debt,
        "weighted_apr": w_apr,
        "bills": total_bills,
        "debt_mins": total_min_debt,
        "obligations": obligations,
        "cashflow": cashflow,
        "cashflow_burden_pct": cashflow_burden_pct,
        "lender_dti_pct": lender_dti_pct,
        "strategy_method": method,
        "extra_monthly": extra_monthly,
        "ava": {"months": ava_m, "date": ava_date, "interest": ava_int},
        "snb": {"months": snb_m, "date": snb_date, "interest": snb_int},
        "ava_unreachable": (ava_int == float("inf")),
        "snb_unreachable": (snb_int == float("inf")),
    }

    # chart payload: debt balances + mins
    debt_chart = [{
        "name": d.name,
        "balance": float(d.balance),
        "apr": float(d.interest_rate),
        "min": float(d.min_payment),
    } for d in debts]

    return render_template("dashboard.html", summary=summary, debt_chart=debt_chart)

@app.route("/strategy", methods=["POST"])
def set_strategy_route():
    method = (request.form.get("method") or "avalanche").strip().lower()
    if method not in ("avalanche", "snowball"):
        method = "avalanche"
    session["strategy_method"] = method

    extra_raw = (request.form.get("extra_override") or "").strip()
    if extra_raw == "":
        session["extra_override"] = None
    else:
        session["extra_override"] = _to_float(extra_raw, 0.0)

    return redirect(url_for("dashboard"))

# ---------------- INCOME ----------------

@app.route("/income", methods=["GET", "POST"])
def manage_income():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        amount = _to_float(request.form.get("amount"), None)
        freq = request.form.get("frequency") or "Monthly"
        p_date = _parse_date(request.form.get("next_pay_date"))

        if not name or amount is None:
            flash("Income requires a name and amount.", "danger")
            return redirect(url_for("manage_income"))

        db.session.add(Income(name=name, amount=float(amount), frequency=freq, next_pay_date=p_date))
        db.session.commit()
        flash("Income added.", "success")
        return redirect(url_for("manage_income"))

    incomes = Income.query.order_by(Income.name.asc()).all()
    return render_template("income.html", incomes=incomes)

# ---------------- DEBT ----------------

@app.route("/debt", methods=["GET", "POST"])
def manage_debt():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        balance = _to_float(request.form.get("balance"), None)
        apr = _to_float(request.form.get("apr"), None)
        min_pay = _to_float(request.form.get("min_pay"), None)

        if not name or balance is None or apr is None or min_pay is None:
            flash("Debt requires name, balance, APR, and minimum payment.", "danger")
            return redirect(url_for("manage_debt"))

        db.session.add(Debt(name=name, balance=float(balance), interest_rate=float(apr), min_payment=float(min_pay)))
        db.session.commit()
        flash("Debt added.", "success")
        return redirect(url_for("manage_debt"))

    debts = Debt.query.order_by(Debt.name.asc()).all()
    return render_template("debt.html", debts=debts)

# ---------------- BILLS ----------------

@app.route("/bills", methods=["GET", "POST"])
def manage_bills():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        amount = _to_float(request.form.get("amount"), None)
        due_date = _parse_date(request.form.get("due_date"))

        if not name or amount is None or due_date is None:
            flash("Bill requires name, amount, and due date.", "danger")
            return redirect(url_for("manage_bills"))

        db.session.add(Bill(name=name, amount=float(amount), due_date=due_date))
        db.session.commit()
        flash("Bill added.", "success")
        return redirect(url_for("manage_bills"))

    bills = Bill.query.order_by(Bill.due_date.asc()).all()
    return render_template("bills.html", bills=bills)

# ---------------- MONTHLY SCHEDULE ----------------

@app.route("/schedule")
def monthly_schedule():
    y, m = parse_month_param(request.args.get("month"))
    start, end = month_bounds(y, m)

    items = PlannedPayment.query.filter(
        PlannedPayment.pay_date >= start,
        PlannedPayment.pay_date <= end
    ).order_by(PlannedPayment.pay_date.asc()).all()

    by_day = {}
    for it in items:
        by_day.setdefault(it.pay_date, []).append(it)

    debts = Debt.query.order_by(Debt.name.asc()).all()
    bills = Bill.query.order_by(Bill.name.asc()).all()

    options = []
    for d in debts:
        options.append({"label": f"Debt: {d.name}", "name": d.name, "kind": "debt"})
    for b in bills:
        options.append({"label": f"Bill: {b.name}", "name": b.name, "kind": "bill"})
    options.append({"label": "Other (custom)", "name": "__custom__", "kind": "other"})

    # Build calendar cells (pad to start weekday)
    first_day = date(y, m, 1)
    last_day_num = calendar.monthrange(y, m)[1]
    first_weekday = (first_day.weekday() + 1) % 7  # convert Mon=0..Sun=6 -> Sun=0..Sat=6

    calendar_cells = []
    for _ in range(first_weekday):
        calendar_cells.append({"is_pad": True})

    for day in range(1, last_day_num + 1):
        calendar_cells.append({"is_pad": False, "date": date(y, m, day)})

    # pad end to complete last week row
    while len(calendar_cells) % 7 != 0:
        calendar_cells.append({"is_pad": True})

    month_label = date(y, m, 1).strftime("%B %Y")
    month_param = f"{y:04d}-{m:02d}"

    return render_template(
        "schedule.html",
        by_day=by_day,
        options=options,
        month_label=month_label,
        month_param=month_param,
        calendar_cells=calendar_cells
    )

@app.route("/schedule/add", methods=["POST"])
def add_schedule_item():
    pay_date = _parse_date(request.form.get("pay_date"))
    sel_name = (request.form.get("sel_name") or "").strip()
    custom_name = (request.form.get("custom_name") or "").strip()
    amount = _to_float(request.form.get("amount"), None)
    kind = (request.form.get("kind") or "debt").strip().lower()

    month_param = request.form.get("month_param") or ""

    if pay_date is None or amount is None:
        flash("Schedule item needs a date and amount.", "danger")
        return redirect(url_for("monthly_schedule", month=month_param))

    if sel_name == "__custom__":
        if not custom_name:
            flash("Choose a name or type a custom name.", "danger")
            return redirect(url_for("monthly_schedule", month=month_param))
        name = custom_name
        kind = "other"
    else:
        name = sel_name
        if kind not in ("debt", "bill", "other"):
            kind = "other"

    db.session.add(PlannedPayment(pay_date=pay_date, name=name, amount=float(amount), kind=kind))
    db.session.commit()
    flash("Planned payment added.", "success")
    return redirect(url_for("monthly_schedule", month=month_param))

@app.route("/schedule/delete/<int:item_id>")
def delete_schedule_item(item_id):
    it = PlannedPayment.query.get_or_404(item_id)
    # redirect back to its month
    month_param = it.pay_date.strftime("%Y-%m")
    db.session.delete(it)
    db.session.commit()
    flash("Planned payment deleted.", "success")
    return redirect(url_for("monthly_schedule", month=month_param))

# ---------------- DEBT PAYOFF ----------------

@app.route("/payoff")
def payoff():
    debts = Debt.query.all()
    monthly_income = get_monthly_income_value()
    bills = Bill.query.all()
    obligations = sum(b.amount for b in bills) + sum(d.min_payment for d in debts)
    cashflow = monthly_income - obligations

    method = session.get("strategy_method", get_setting("default_strategy", "avalanche") or "avalanche")
    extra_override = session.get("extra_override", None)
    extra_monthly = max(cashflow, 0.0) if extra_override is None else max(float(extra_override), 0.0)

    ava_m, ava_date, ava_int = simulate_payoff(debts, extra_monthly, "avalanche")
    snb_m, snb_date, snb_int = simulate_payoff(debts, extra_monthly, "snowball")

    # What-if table: extra amounts
    bumps = [0, 100, 250, 500, 1000]
    scenarios = []
    for bump in bumps:
        extra = max(extra_monthly + bump, 0.0)
        m1, d1, i1 = simulate_payoff(debts, extra, "avalanche")
        m2, d2, i2 = simulate_payoff(debts, extra, "snowball")
        scenarios.append({
            "extra": extra,
            "ava_months": m1,
            "ava_interest": i1,
            "snb_months": m2,
            "snb_interest": i2,
        })

    return render_template(
        "payoff.html",
        method=method,
        extra_monthly=extra_monthly,
        cashflow=cashflow,
        ava={"months": ava_m, "date": ava_date, "interest": ava_int, "unreachable": (ava_int == float("inf"))},
        snb={"months": snb_m, "date": snb_date, "interest": snb_int, "unreachable": (snb_int == float("inf"))},
        scenarios=scenarios
    )

# ---------------- SETTINGS ----------------

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        default_strategy = request.form.get("default_strategy") or "avalanche"
        set_setting("default_strategy", default_strategy)

        # placeholder toggles (you can add more)
        include_bills_in_dti = "1" if request.form.get("include_bills_in_dti") == "on" else "0"
        set_setting("include_bills_in_dti", include_bills_in_dti)

        flash("Settings saved.", "success")
        return redirect(url_for("settings"))

    current = {
        "default_strategy": get_setting("default_strategy", "avalanche"),
        "include_bills_in_dti": bool_setting("include_bills_in_dti", True)
    }
    return render_template("settings.html", s=current)

# ---------------- DELETE ----------------

@app.route("/delete/<string:category>/<int:item_id>")
def delete_item(category, item_id):
    model_map = {"income": Income, "debt": Debt, "bill": Bill}
    if category not in model_map:
        flash("Invalid delete category.", "danger")
        return redirect(url_for("dashboard"))

    item = model_map[category].query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Deleted.", "success")
    return redirect(request.referrer or url_for("dashboard"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
