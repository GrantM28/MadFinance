from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

# Database configuration - stores the db file in the 'data' folder
db_path = os.path.join(os.path.dirname(__file__), 'data', 'finance.db')
if not os.path.exists(os.path.dirname(db_path)):
    os.makedirs(os.path.dirname(db_path))

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Model
class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    entry_type = db.Column(db.String(50), nullable=False) # Income, Bill, Debt, etc.
    category = db.Column(db.String(50))

# Create the database tables
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    entries = Entry.query.all()
    total_income = sum(e.amount for e in entries if e.entry_type == 'Income')
    total_out = sum(e.amount for e in entries if e.entry_type != 'Income')
    balance = total_income - total_out
    return render_template('index.html', entries=entries, balance=balance)

@app.route('/add', methods=['POST'])
def add_entry():
    new_entry = Entry(
        name=request.form.get('name'),
        amount=float(request.form.get('amount')),
        entry_type=request.form.get('entry_type'),
        category=request.form.get('category')
    )
    db.session.add(new_entry)
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)