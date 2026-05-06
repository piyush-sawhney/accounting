from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import redirect, url_for, session, flash, current_app
from models import Company, db
import os
import re
import shutil
import pdfkit

def parse_date(date_str):
    if not date_str: return None
    date_str = date_str.strip()
    for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]:
        try: return datetime.strptime(date_str, fmt).date()
        except ValueError: continue
    return None

def parse_number(value):
    if not value: return 0.0
    value = str(value).strip().replace("?", "").replace("₹", "").replace(",", "").replace("'", "")
    try: return float(value)
    except ValueError: return 0.0

def parse_percentage(value):
    if not value: return 0.0
    value = str(value).strip().replace("%", "")
    try: return float(value)
    except ValueError: return 0.0

def parse_tax_type(tax_type):
    if not tax_type: return "INTER"
    tax_type = tax_type.strip().upper()
    return "INTRA" if tax_type in ["INTRA", "INNERS", "INRA"] else "INTER"

def validate_tax_rates(tax_type, is_rcm, cgst_rate, sgst_rate, igst_rate):
    if is_rcm:
        if cgst_rate > 0 or sgst_rate > 0 or igst_rate > 0:
            return False, "RCM enabled - tax rates must be 0"
        return True, None
    if tax_type == "INTER":
        if cgst_rate > 0 or sgst_rate > 0:
            return False, "INTER state - IGST required, CGST/SGST must be 0"
        if igst_rate <= 0:
            return False, "INTER state - IGST rate is required"
        return True, None
    if tax_type == "INTRA":
        if igst_rate > 0:
            return False, "INTRA state - CGST/SGST required, IGST must be 0"
        if cgst_rate <= 0 or sgst_rate <= 0:
            return False, "INTRA state - CGST and SGST rates are required"
        return True, None
    return True, None

def extract_pan_from_gstin(gstin):
    return gstin[2:12].upper() if gstin and len(gstin) >= 12 else ""

def number_to_words(num):
    num = float(num)
    if num == 0: return "Zero Only"
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", " Seventy", "Eighty", "Ninety"]
    thousands = ["", "Thousand", "Million", "Billion"]
    def convert_hundreds(n):
        words = []
        if n >= 100:
            words.append(ones[n // 100]); words.append("Hundred"); n %= 100
        if n >= 20:
            words.append(tens[n // 10]); n %= 10
        if n > 0:
            words.append(ones[n])
        return " ".join(words)
    def convert_number(n):
        if n == 0: return ""
        words = []; thousand_index = 0
        while n > 0:
            remainder = n % 1000
            if remainder > 0:
                remainder_words = convert_hundreds(remainder)
                if thousand_index > 0: remainder_words += " " + thousands[thousand_index]
                words.insert(0, remainder_words)
            n //= 1000; thousand_index += 1
        return " ".join(words)
    integer_part = int(num)
    paise = int(round((num - integer_part) * 100))
    rupees_words = convert_number(integer_part)
    rupees_words = (rupees_words + " Only") if rupees_words else "Zero Only"
    return f"{rupees_words} and {convert_number(paise)} Paisa" if paise > 0 else rupees_words

def get_fiscal_year():
    now = datetime.now()
    return f"{now.year}-{now.year + 1}" if now.month >= 4 else f"{now.year - 1}-{now.year}"

def get_fy_short():
    fy = get_fiscal_year()
    return fy.replace("-", "_")

def get_current_company():
    company = Company.query.filter_by(is_default=True).first()
    return company or Company.query.first()

def get_greeting():
    hour = datetime.now().hour
    return "Good Morning" if hour < 12 else "Good Afternoon" if hour < 17 else "Good Evening"

def get_export_path(invoice):
    fy_short = get_fy_short()
    month_name = (
        get_month_name(invoice.invoice_date.month)
        if invoice.invoice_date
        else "Unknown"
    )
    def sanitize(name):
        name = str(name).strip()
        name = re.sub(r'[<>:"/\\|?*&]', "_", name)
        return re.sub(r"_+", "_", name).strip("_")
    party_name = sanitize(invoice.party_name or invoice.party.name if invoice.party else "Unknown")
    invoice_no = sanitize(invoice.invoice_no or f"invoice_{invoice.id}")
    return os.path.join(
        current_app.config["EXPORT_FOLDER"],
        fy_short,
        month_name,
        f"{party_name}_{invoice_no}.pdf",
    )

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"): return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"): return redirect(url_for("auth.login", next=request.url))
        if session.get("role") != "admin":
            flash("Admin access required", "danger")
            return redirect(url_for("dashboard.dashboard"))
        return f(*args, **kwargs)
    return decorated_function

def get_month_name(month_num):
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    return months[month_num - 1] if 1 <= month_num <= 12 else ""


def generate_invoice_numbers():
    from models import Invoice, InvoiceSequence
    from datetime import datetime
    
    current_fy = f"{datetime.now().year}-{datetime.now().year + 1}"
    fy_prefix = current_fy.split("-")[0][-2:] + "-" + current_fy[-2:]
    
    pending = Invoice.query.filter(Invoice.invoice_no.is_(None)).order_by(Invoice.invoice_date).all()
    
    if not pending:
        return 0
    
    seq_record = InvoiceSequence.query.filter_by(fy=current_fy).first()
    if not seq_record:
        seq_record = InvoiceSequence(fy=current_fy, last_number=0)
        db.session.add(seq_record)
        db.session.flush()
    
    existing = Invoice.query.filter(
        Invoice.invoice_no.like(f"{fy_prefix}/%")
    ).order_by(Invoice.invoice_no.desc()).first()
    
    if existing:
        max_num = int(existing.invoice_no.split("/")[-1])
        if seq_record.last_number < max_num:
            seq_record.last_number = max_num
    
    seq = seq_record.last_number
    
    for invoice in pending:
        seq += 1
        invoice.invoice_no = f"{fy_prefix}/{str(seq).zfill(3)}"
    
    seq_record.last_number = seq
    db.session.commit()
    
    return len(pending)

def get_pdfkit_config():
    import shutil
    wkhtmltopdf_path = os.environ.get('WKHTMLTOPDF_PATH')
    if not wkhtmltopdf_path:
        wkhtmltopdf_path = shutil.which('wkhtmltopdf')
        if not wkhtmltopdf_path:
            for path in [
                r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe',
                r'C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe',
                r'C:\wkhtmltopdf\bin\wkhtmltopdf.exe',
            ]:
                if os.path.exists(path):
                    wkhtmltopdf_path = path
                    break
    if wkhtmltopdf_path:
        return pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
    return None

