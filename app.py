import os
import secrets
from datetime import datetime, timedelta, timezone
from flask import Flask, redirect, url_for, session, flash, request
from flask_sqlalchemy import SQLAlchemy
from models import db, Company, User
from constants import RECOVERY_CODE_COUNT, INVOICE_NUMBER_PADDING, MAX_RETRY_ATTEMPTS

# Import Blueprints
from routes.auth import auth_bp
from routes.company import company_bp
from routes.parties import parties_bp
from routes.invoices import invoices_bp
from routes.admin import admin_bp
from routes.dashboard import dashboard_bp
from routes.credit_notes import credit_notes_bp

# Import Utils
from utils import (
    parse_date, parse_number, parse_percentage, parse_tax_type, 
    validate_tax_rates, extract_pan_from_gstin, number_to_words,
    get_fiscal_year, get_fy_short, get_current_company, get_greeting,
    login_required, admin_required, generate_invoice_numbers
)

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
if not app.config["SECRET_KEY"]:
    if os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError("SECRET_KEY environment variable is required in production")
    app.config["SECRET_KEY"] = "dev-secret-key-change-in-production"

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    f"postgresql+psycopg://{os.environ.get('DB_USER', 'postgres')}:{os.environ.get('DB_PASSWORD', 'postgres')}@{os.environ.get('DB_HOST', 'localhost')}:{os.environ.get('DB_PORT', '5432')}/{os.environ.get('DB_NAME', 'gst_invoices')}",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["EXPORT_FOLDER"] = "exports"
app.config["LOGO_FOLDER"] = "static/logos"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["EXPORT_FOLDER"], exist_ok=True)
os.makedirs(app.config["LOGO_FOLDER"], exist_ok=True)

db.init_app(app)

# Add currency filter for Jinja2 templates
@app.template_filter('currency')
def currency_filter(value):
    if value is None:
        return "0"
    try:
        return f"{float(value):,.2f}"
    except:
        return str(value)

@app.before_request
def check_auth():
    public_routes = ["auth", "static", "index"]
    if request.endpoint and request.endpoint.split(".")[0] in public_routes: return
    if not session.get("user_id"): return redirect(url_for("auth.login"))
    if request.endpoint and "company" not in request.endpoint and "import_companies" != request.endpoint:
        if Company.query.count() == 0:
            flash("Company profile setup is required to use the software.", "info")
            return redirect(url_for("company.company"))

@app.route("/")
def index():
    if not session.get("user_id"): return redirect(url_for("auth.login"))
    if not User.query.first(): return redirect(url_for("auth.setup"))
    return redirect(url_for("dashboard.dashboard"))

app.register_blueprint(auth_bp)
app.register_blueprint(company_bp)
app.register_blueprint(parties_bp)
app.register_blueprint(invoices_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(credit_notes_bp)

# Add URL defaults for backward compatibility with templates
# Templates use short names like url_for('login') but Flask needs url_for('auth.login')
app.url_map.default_subdomain = ''
app.url_map.default_methods = ('GET', 'POST')

if __name__ == "__main__":
    app.run(debug=True)
