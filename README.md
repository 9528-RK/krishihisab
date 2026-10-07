# 🌾 KRUSHIHISAB — शेतीचा हिशोब, आता डिजिटल!

A Marathi-first farmer/tractor business management web app built with Flask + SQLite.

## Features
- Dashboard: total income, paid, remaining, expenses, profit, customers
- Customer/farmer master: mobile, village, land, crop, notes
- Job/work entry with quantity × rate calculation
- Payment history with automatic allocation against oldest outstanding jobs
- Outstanding/बाकी report
- Expense management
- Rate management
- Daily/recent work records and date/search filters
- Monthly income/paid/due report
- CSV exports
- SQLite database (persistent local data)
- Responsive mobile-friendly UI
- API summary endpoint for future mobile/app integration

## Run locally
1. Install Python 3.10+.
2. Open terminal in this folder.
3. `pip install -r requirements.txt`
4. `python app.py`
5. Open `http://127.0.0.1:5000`

The SQLite database `farmer_manager.db` is created automatically.

## Deploy on Render
1. Push this project to a GitHub repository and connect it to Render.
2. Render can use the included `render.yaml` to create the web service and persistent SQLite disk.
3. Set `SECRET_KEY` to a secure random value in the Render environment settings before handling real data.

The service runs with Gunicorn. The database is stored under `/var/data` on Render's persistent disk, so records survive restarts and redeploys. The persistent disk requires a paid Render web-service plan. For a free deployment, use a managed database such as PostgreSQL instead of SQLite.

## Suggested next upgrades
- Login + roles (Owner/Staff)
- WhatsApp/SMS payment reminders
- PDF receipts/invoices
- Multi-farm and machinery tracking
- GST/tax invoice support
- Marathi/English language switch
- Cloud database and automatic backups
