from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, flash
import sqlite3, os, csv, io
from datetime import datetime, date

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get('DATABASE_PATH', os.path.join(BASE, 'farmer_manager.db'))
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-change-me')


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    return con


def init_db():
    con = db()
    con.executescript('''
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mobile TEXT,
        village TEXT,
        land_acres REAL DEFAULT 0,
        crop TEXT,
        notes TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        job_date TEXT NOT NULL,
        service TEXT NOT NULL,
        quantity REAL DEFAULT 0,
        unit TEXT DEFAULT 'acre',
        rate REAL DEFAULT 0,
        total REAL DEFAULT 0,
        paid REAL DEFAULT 0,
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        payment_date TEXT NOT NULL,
        amount REAL NOT NULL,
        mode TEXT DEFAULT 'Cash',
        reference TEXT,
        notes TEXT,
        FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        expense_date TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        description TEXT
    );
    CREATE TABLE IF NOT EXISTS rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service TEXT UNIQUE NOT NULL,
        rate REAL NOT NULL,
        unit TEXT DEFAULT 'acre'
    );
    ''')
    defaults = [('ट्रॅक्टर नांगरणी',1200,'acre'),('रोटाव्हेटर',1500,'acre'),('पेरणी',1000,'acre'),('फवारणी',500,'acre'),('इतर काम',1000,'hour')]
    for service, rate, unit in defaults:
        con.execute('INSERT OR IGNORE INTO rates(service,rate,unit) VALUES(?,?,?)',(service,rate,unit))
    con.commit(); con.close()


def money(x): return round(float(x or 0), 2)

@app.context_processor



def globals():
    return {'today': date.today().isoformat(), 'money': money}

@app.route('/')
def dashboard():
    con=db()
    totals=con.execute('''SELECT COALESCE(SUM(total),0) income, COALESCE(SUM(paid),0) paid,
                         COALESCE(SUM(total-paid),0) remaining, COUNT(*) jobs FROM jobs''').fetchone()
    expenses=con.execute('SELECT COALESCE(SUM(amount),0) total FROM expenses').fetchone()['total']
    customers=con.execute('SELECT COUNT(*) c FROM customers').fetchone()['c']
    today=con.execute("SELECT COALESCE(SUM(total),0) income, COALESCE(SUM(paid),0) paid FROM jobs WHERE job_date=?",(date.today().isoformat(),)).fetchone()
    recent=con.execute('''SELECT j.*, c.name customer FROM jobs j JOIN customers c ON c.id=j.customer_id ORDER BY j.job_date DESC,j.id DESC LIMIT 8''').fetchall()
    top=con.execute('''SELECT c.name, c.mobile, COALESCE(SUM(j.total),0) total, COALESCE(SUM(j.total-j.paid),0) due
                       FROM customers c LEFT JOIN jobs j ON j.customer_id=c.id GROUP BY c.id ORDER BY due DESC LIMIT 5''').fetchall()
    con.close()
    return render_template('dashboard.html', totals=totals, expenses=expenses, customers=customers, today=today, recent=recent, top=top)

@app.route('/customers')
def customers():
    q=request.args.get('q','').strip()
    con=db()
    rows=con.execute('''SELECT c.*, COALESCE((SELECT SUM(total) FROM jobs WHERE customer_id=c.id),0) income,
                        COALESCE((SELECT SUM(total-paid) FROM jobs WHERE customer_id=c.id),0) due,
                        COALESCE((SELECT SUM(amount) FROM payments WHERE customer_id=c.id),0) payment_history
                        FROM customers c WHERE name LIKE ? OR mobile LIKE ? OR village LIKE ? ORDER BY c.id DESC''', (f'%{q}%',f'%{q}%',f'%{q}%')).fetchall()
    con.close(); return render_template('customers.html', rows=rows, q=q)

@app.route('/customers/add', methods=['GET','POST'])
def add_customer():
    if request.method=='POST':
        con=db(); con.execute('INSERT INTO customers(name,mobile,village,land_acres,crop,notes,created_at) VALUES(?,?,?,?,?,?,?)',
            (request.form['name'],request.form.get('mobile'),request.form.get('village'),request.form.get('land_acres') or 0,request.form.get('crop'),request.form.get('notes'),datetime.now().isoformat()))
        con.commit(); con.close(); flash('ग्राहक यशस्वीपणे जोडला.','success'); return redirect(url_for('customers'))
    return render_template('customer_form.html')

@app.route('/customers/<int:cid>')
def customer_detail(cid):
    con=db(); c=con.execute('SELECT * FROM customers WHERE id=?',(cid,)).fetchone()
    if not c: return 'Not found',404
    jobs=con.execute('SELECT * FROM jobs WHERE customer_id=? ORDER BY job_date DESC,id DESC',(cid,)).fetchall()
    payments=con.execute('SELECT * FROM payments WHERE customer_id=? ORDER BY payment_date DESC,id DESC',(cid,)).fetchall()
    summary=con.execute('SELECT COALESCE(SUM(total),0) income,COALESCE(SUM(paid),0) paid,COALESCE(SUM(total-paid),0) due FROM jobs WHERE customer_id=?',(cid,)).fetchone()
    con.close(); return render_template('customer_detail.html',c=c,jobs=jobs,payments=payments,summary=summary)

@app.route('/jobs/add', methods=['GET','POST'])
def add_job():
    con=db(); customers=con.execute('SELECT * FROM customers ORDER BY name').fetchall(); rates=con.execute('SELECT * FROM rates ORDER BY service').fetchall()
    if request.method=='POST':
        qty=float(request.form.get('quantity') or 0); rate=float(request.form.get('rate') or 0); total=money(qty*rate); paid=money(request.form.get('paid') or 0)
        con.execute('INSERT INTO jobs(customer_id,job_date,service,quantity,unit,rate,total,paid,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
          (request.form['customer_id'],request.form['job_date'],request.form['service'],qty,request.form.get('unit','acre'),rate,total,paid,request.form.get('notes'),datetime.now().isoformat()))
        con.commit(); con.close(); flash('कामाची नोंद सेव्ह झाली.','success'); return redirect(url_for('dashboard'))
    con.close(); return render_template('job_form.html',customers=customers,rates=rates)

@app.route('/payments/add', methods=['GET','POST'])
def add_payment():
    con=db(); customers=con.execute('SELECT * FROM customers ORDER BY name').fetchall()
    if request.method=='POST':
        con.execute('INSERT INTO payments(customer_id,payment_date,amount,mode,reference,notes) VALUES(?,?,?,?,?,?)',
          (request.form['customer_id'],request.form['payment_date'],float(request.form['amount']),request.form.get('mode','Cash'),request.form.get('reference'),request.form.get('notes')))
        # Allocate payment to oldest unpaid jobs
        remaining=float(request.form['amount']); cid=request.form['customer_id']
        jobs=con.execute('SELECT id,total,paid FROM jobs WHERE customer_id=? AND total>paid ORDER BY job_date,id',(cid,)).fetchall()
        for j in jobs:
            add=min(remaining,j['total']-j['paid'])
            if add>0:
                con.execute('UPDATE jobs SET paid=paid+? WHERE id=?',(add,j['id'])); remaining-=add
            if remaining<=0: break
        con.commit(); con.close(); flash('पेमेंट सेव्ह झाली आणि बाकी रकमेवर adjust केली.','success'); return redirect(url_for('payments'))
    con.close(); return render_template('payment_form.html',customers=customers)

@app.route('/payments')
def payments():
    con=db(); rows=con.execute('''SELECT p.*,c.name customer FROM payments p JOIN customers c ON c.id=p.customer_id ORDER BY payment_date DESC,p.id DESC''').fetchall(); con.close()
    return render_template('payments.html',rows=rows)

@app.route('/dues')
def dues():
    con=db(); rows=con.execute('''SELECT c.id,c.name,c.mobile,c.village,COALESCE(SUM(j.total),0) income,COALESCE(SUM(j.paid),0) paid,COALESCE(SUM(j.total-j.paid),0) due
                                  FROM customers c JOIN jobs j ON j.customer_id=c.id GROUP BY c.id HAVING due>0.009 ORDER BY due DESC''').fetchall(); con.close(); return render_template('dues.html',rows=rows)

@app.route('/jobs')
def jobs():
    q=request.args.get('q',''); start=request.args.get('start',''); end=request.args.get('end','')
    con=db(); sql='''SELECT j.*,c.name customer,c.mobile FROM jobs j JOIN customers c ON c.id=j.customer_id WHERE (c.name LIKE ? OR j.service LIKE ?)'''; args=[f'%{q}%',f'%{q}%']
    if start: sql+=' AND j.job_date>=?'; args.append(start)
    if end: sql+=' AND j.job_date<=?'; args.append(end)
    sql+=' ORDER BY j.job_date DESC,j.id DESC'; rows=con.execute(sql,args).fetchall(); con.close(); return render_template('jobs.html',rows=rows,q=q,start=start,end=end)

@app.route('/expenses',methods=['GET','POST'])
def expenses():
    con=db()
    if request.method=='POST':
        con.execute('INSERT INTO expenses(expense_date,category,amount,description) VALUES(?,?,?,?)',(request.form['expense_date'],request.form['category'],float(request.form['amount']),request.form.get('description'))); con.commit(); flash('खर्च सेव्ह झाला.','success')
    rows=con.execute('SELECT * FROM expenses ORDER BY expense_date DESC,id DESC').fetchall(); total=con.execute('SELECT COALESCE(SUM(amount),0) t FROM expenses').fetchone()['t']; con.close(); return render_template('expenses.html',rows=rows,total=total)

@app.route('/rates',methods=['GET','POST'])
def rates():
    con=db()
    if request.method=='POST':
        con.execute('INSERT INTO rates(service,rate,unit) VALUES(?,?,?) ON CONFLICT(service) DO UPDATE SET rate=excluded.rate,unit=excluded.unit',(request.form['service'],float(request.form['rate']),request.form.get('unit','acre'))); con.commit(); flash('दर अपडेट झाला.','success')
    rows=con.execute('SELECT * FROM rates ORDER BY service').fetchall(); con.close(); return render_template('rates.html',rows=rows)

@app.route('/reports')
def reports():
    con=db(); monthly=con.execute('''SELECT substr(job_date,1,7) month,ROUND(SUM(total),2) income,ROUND(SUM(paid),2) paid,ROUND(SUM(total-paid),2) due FROM jobs GROUP BY month ORDER BY month DESC LIMIT 12''').fetchall()
    profit=con.execute('SELECT COALESCE((SELECT SUM(total) FROM jobs),0) income,COALESCE((SELECT SUM(amount) FROM expenses),0) expense').fetchone(); con.close(); return render_template('reports.html',monthly=monthly,profit=profit)

@app.route('/export/<kind>')
def export(kind):
    con=db(); out=io.StringIO(); w=csv.writer(out)
    if kind=='customers':
        rows=con.execute('SELECT id,name,mobile,village,land_acres,crop,notes,created_at FROM customers').fetchall(); w.writerow(rows[0].keys() if rows else ['id','name','mobile','village','land_acres','crop','notes','created_at'])
    elif kind=='jobs':
        rows=con.execute('''SELECT j.id,j.job_date,c.name customer,j.service,j.quantity,j.unit,j.rate,j.total,j.paid,j.total-j.paid remaining,j.notes FROM jobs j JOIN customers c ON c.id=j.customer_id''').fetchall(); w.writerow(rows[0].keys() if rows else ['id','job_date','customer','service','quantity','unit','rate','total','paid','remaining','notes'])
    else:
        rows=con.execute('SELECT * FROM payments ORDER BY payment_date DESC').fetchall(); w.writerow(rows[0].keys() if rows else ['id','customer_id','payment_date','amount','mode','reference','notes'])
    for r in rows: w.writerow(list(r))
    con.close(); mem=io.BytesIO(out.getvalue().encode('utf-8-sig')); return send_file(mem,as_attachment=True,download_name=f'{kind}.csv',mimetype='text/csv')

@app.route('/api/summary')
def api_summary():
    con=db(); r=con.execute('SELECT COALESCE(SUM(total),0) income,COALESCE(SUM(paid),0) paid,COALESCE(SUM(total-paid),0) due FROM jobs').fetchone(); e=con.execute('SELECT COALESCE(SUM(amount),0) expense FROM expenses').fetchone(); con.close(); return jsonify({'income':r['income'],'paid':r['paid'],'due':r['due'],'expense':e['expense'],'profit':r['income']-e['expense']})

init_db()

if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT','5000')),debug=os.environ.get('FLASK_DEBUG') == '1')

