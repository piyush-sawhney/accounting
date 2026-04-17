import os
import csv
import io
import zipfile
from datetime import datetime
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
    jsonify,
)
from werkzeug.utils import secure_filename
from weasyprint import HTML

from models import db, Settings, Party, Invoice, InvoiceItem

app = Flask(__name__)
app.config["SECRET_KEY"] = "gst-invoice-secret-key-2024"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///gst_invoices.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "static/uploads"
app.config["EXPORT_FOLDER"] = "exports"
app.config["LOGO_FOLDER"] = "static/logos"

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["EXPORT_FOLDER"], exist_ok=True)
os.makedirs(app.config["LOGO_FOLDER"], exist_ok=True)

db.init_app(app)


def parse_date(date_str):
    """Parse date from various formats"""
    if not date_str:
        return None
    date_str = date_str.strip()
    formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def parse_number(value):
    """Parse numeric value from various formats (handles commas, currency symbols)"""
    if not value:
        return 0.0
    value = str(value).strip()
    value = value.replace("?", "").replace("₹", "").replace(",", "").replace("'", "")
    try:
        return float(value)
    except ValueError:
        return 0.0


def parse_percentage(value):
    """Parse percentage value (handles % sign)"""
    if not value:
        return 0.0
    value = str(value).strip().replace("%", "")
    try:
        return float(value)
    except ValueError:
        return 0.0


def parse_tax_type(tax_type):
    """Normalize tax type"""
    if not tax_type:
        return "INTER"
    tax_type = tax_type.strip().upper()
    if tax_type in ["INTRA", "INNERS", "INRA"]:
        return "INTRA"
    return "INTER"


def validate_tax_rates(tax_type, is_rcm, cgst_rate, sgst_rate, igst_rate):
    """
    Validate tax rates based on rules:
    1. RCM only: no igst, cgst, sgst
    2. INTER only: IGST, no cgst, no sgst
    3. INTRA only: CGST + SGST, no igst

    Returns (is_valid, error_message)
    """
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
    """Extract PAN from GSTIN (digits 3-12)"""
    if not gstin or len(gstin) < 12:
        return ""
    return gstin[2:12].upper()


def number_to_words(num):
    """Convert number to words format: 'Nineteen Thousand Six Hundred Forty Only and Eighty Four Paisa'"""
    num = float(num)
    if num == 0:
        return "Zero Only"

    # Define word arrays
    ones = [
        "",
        "One",
        "Two",
        "Three",
        "Four",
        "Five",
        "Six",
        "Seven",
        "Eight",
        "Nine",
        "Ten",
        "Eleven",
        "Twelve",
        "Thirteen",
        "Fourteen",
        "Fifteen",
        "Sixteen",
        "Seventeen",
        "Eighteen",
        "Nineteen",
    ]
    tens = [
        "",
        "",
        "Twenty",
        "Thirty",
        "Forty",
        "Fifty",
        "Sixty",
        "Seventy",
        "Eighty",
        "Ninety",
    ]
    thousands = ["", "Thousand", "Million", "Billion"]

    def convert_hundreds(n):
        """Convert number less than 1000 to words"""
        words = []
        if n >= 100:
            words.append(ones[n // 100])
            words.append("Hundred")
            n %= 100
        if n >= 20:
            words.append(tens[n // 10])
            n %= 10
        if n > 0:
            words.append(ones[n])
        return " ".join(words)

    def convert_number(n):
        """Convert any number to words"""
        if n == 0:
            return ""

        words = []
        thousand_index = 0

        while n > 0:
            remainder = n % 1000
            if remainder > 0:
                remainder_words = convert_hundreds(remainder)
                if thousand_index > 0:
                    remainder_words += " " + thousands[thousand_index]
                words.insert(0, remainder_words)
            n //= 1000
            thousand_index += 1

        return " ".join(words)

    # Split into rupees and paise
    integer_part = int(num)
    paise = int(round((num - integer_part) * 100))

    # Convert rupees to words
    rupees_words = convert_number(integer_part)
    if rupees_words:
        rupees_words += " Only"
    else:
        rupees_words = "Zero Only"

    # Convert paise to words if needed
    if paise > 0:
        paise_words = convert_number(paise)
        result = f"{rupees_words} and {paise_words} Paisa"
    else:
        result = rupees_words

    return result


def get_fiscal_year():
    now = datetime.now()
    if now.month >= 4:
        return f"{now.year}-{now.year + 1}"
    else:
        return f"{now.year - 1}-{now.year}"


def generate_invoice_numbers():
    pending_invoices = (
        Invoice.query.filter(Invoice.invoice_no == None)
        .order_by(Invoice.invoice_date)
        .all()
    )

    if not pending_invoices:
        return 0

    last_invoice = (
        Invoice.query.filter(Invoice.invoice_no != None)
        .order_by(Invoice.invoice_no.desc())
        .first()
    )

    if last_invoice:
        last_no = last_invoice.invoice_no
        parts = last_no.split("/")
        if len(parts) == 2:
            try:
                seq = int(parts[1])
            except:
                seq = 0
        else:
            seq = 0
    else:
        seq = 0

    for invoice in pending_invoices:
        seq += 1
        invoice_no = f"{get_fiscal_year().split('-')[0][-2:]}-{get_fiscal_year()[-2:]}/{str(seq).zfill(3)}"
        invoice.invoice_no = invoice_no
        invoice.locked = True

        total = invoice.calculate_gst()["total"]
        invoice.total_in_words = number_to_words(total)

    db.session.commit()
    return len(pending_invoices)


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        Settings.set("company_name", request.form.get("company_name"))
        Settings.set("arn_number", request.form.get("arn_number"))
        Settings.set("address", request.form.get("address"))
        Settings.set("gstin", request.form.get("gstin"))
        Settings.set("pan", request.form.get("pan"))
        Settings.set("place_of_supply", request.form.get("place_of_supply"))
        Settings.set("state_code", request.form.get("state_code"))

        if "logo" in request.files and request.files["logo"].filename:
            logo = request.files["logo"]
            logo_path = os.path.join(app.config["LOGO_FOLDER"], "logo.png")
            logo.save(logo_path)
            Settings.set("logo", "logo.png")

        flash("Settings saved successfully", "success")
        return redirect(url_for("settings"))

    company_name = Settings.get("company_name", "")
    arn_number = Settings.get("arn_number", "")
    address = Settings.get("address", "")
    gstin = Settings.get("gstin", "")
    pan = Settings.get("pan", "")
    logo = Settings.get("logo", "")
    place_of_supply = Settings.get("place_of_supply", "")
    state_code = Settings.get("state_code", "")

    return render_template(
        "settings.html",
        company_name=company_name,
        arn_number=arn_number,
        address=address,
        gstin=gstin,
        pan=pan,
        logo=logo,
        place_of_supply=place_of_supply,
        state_code=state_code,
    )


@app.route("/dashboard")
def dashboard():
    year = request.args.get("year")
    month = request.args.get("month")
    search = request.args.get("search", "").strip()

    query = Invoice.query

    if year:
        query = query.filter(db.extract("year", Invoice.invoice_date) == int(year))
    if month:
        query = query.filter(db.extract("month", Invoice.invoice_date) == int(month))
    if search:
        query = query.join(Party).filter(
            db.or_(
                Invoice.invoice_no.ilike(f"%{search}%"),
                Invoice.reference_serial_no.ilike(f"%{search}%"),
                Party.gstin.ilike(f"%{search}%"),
                Party.name.ilike(f"%{search}%"),
            )
        )

    invoices = query.order_by(Invoice.invoice_date.desc()).all()
    parties = Party.query.all()
    pending_count = Invoice.query.filter(Invoice.invoice_no == None).count()

    all_invoices = Invoice.query.all()
    years = sorted(
        set(inv.invoice_date.year for inv in all_invoices if inv.invoice_date)
    )
    if not years:
        years = [datetime.now().year]

    all_invoices_for_year = Invoice.query.all()
    total_revenue = sum(
        inv.calculate_gst().get("subtotal", 0) or 0 for inv in all_invoices_for_year
    )
    total_gst = (
        sum(inv.calculate_gst().get("total", 0) or 0 for inv in all_invoices_for_year)
        - total_revenue
    )
    invoice_count = len(all_invoices_for_year)

    months = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    chart_labels = []
    chart_data = []
    from datetime import timedelta

    for i in range(6, 0, -1):
        target_month = (
            datetime.now().replace(day=1) - timedelta(days=1) * (i - 1)
        ).month
        target_year = (datetime.now().replace(day=1) - timedelta(days=1) * (i - 1)).year
        month_invoices = Invoice.query.filter(
            db.extract("month", Invoice.invoice_date) == target_month,
            db.extract("year", Invoice.invoice_date) == target_year,
        ).all()
        revenue = sum(
            inv.calculate_gst().get("subtotal", 0) or 0 for inv in month_invoices
        )
        chart_labels.append(f"{months[target_month - 1]} {target_year}")
        chart_data.append(revenue)

    return render_template(
        "dashboard.html",
        invoices=invoices,
        parties=parties,
        pending_count=pending_count,
        selected_year=year,
        selected_month=month,
        search_query=search,
        years=years,
        total_revenue=total_revenue,
        total_gst=total_gst,
        invoice_count=invoice_count,
        chart_labels=chart_labels,
        chart_data=chart_data,
    )


@app.route("/party/api/<int:party_id>")
def party_api(party_id):
    party = Party.query.get_or_404(party_id)
    return jsonify(
        {
            "name": party.name,
            "gstin": party.gstin,
            "pan": party.pan,
            "address": party.address,
            "state": party.state,
            "state_code": party.state_code,
        }
    )


@app.route("/parties", methods=["GET", "POST"])
def parties():
    if request.method == "POST":
        name = request.form.get("name")
        gstin = request.form.get("gstin")
        amc_code = request.form.get("amc_code")
        pan = request.form.get("pan")
        address = request.form.get("address")
        state = request.form.get("state")
        state_code = request.form.get("state_code")
        email = request.form.get("email")
        phone = request.form.get("phone")

        existing = Party.query.filter_by(gstin=gstin).first()
        if existing:
            flash(f"Party with GSTIN {gstin} already exists", "danger")
            return redirect(url_for("parties"))

        party = Party(
            name=name,
            gstin=gstin,
            amc_code=amc_code,
            pan=pan,
            address=address,
            state=state,
            state_code=state_code,
            email=email,
            phone=phone,
        )
        db.session.add(party)
        db.session.commit()
        flash("Party added successfully", "success")
        return redirect(url_for("parties"))

    parties = Party.query.all()
    return render_template("parties.html", parties=parties)


@app.route("/export/parties")
def export_parties():
    parties = Party.query.all()
    return export_parties_response(parties)


@app.route("/export/parties/selected", methods=["POST"])
def export_selected_parties():
    ids_raw = request.form.get("party_ids", "")
    party_ids = ids_raw.split(",") if ids_raw else []
    if not party_ids or party_ids == [""]:
        flash("No parties selected", "warning")
        return redirect(url_for("parties"))
    parties = Party.query.filter(Party.id.in_(party_ids)).all()
    return export_parties_response(parties)


def export_parties_response(parties):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "name",
            "gstin",
            "pan",
            "amc_code",
            "address",
            "state",
            "state_code",
            "email",
            "phone",
        ]
    )

    for party in parties:
        writer.writerow(
            [
                party.name,
                party.gstin,
                party.pan or "",
                party.amc_code or "",
                party.address or "",
                party.state or "",
                party.state_code or "",
                party.email or "",
                party.phone or "",
            ]
        )

    output.seek(0)
    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"parties_export_{datetime.now().strftime('%Y%m%d')}.csv",
    )


@app.route("/party/edit/<int:party_id>", methods=["GET", "POST"])
def edit_party(party_id):
    party = Party.query.get_or_404(party_id)

    if request.method == "POST":
        party.name = request.form.get("name")
        party.gstin = request.form.get("gstin")
        party.pan = request.form.get("pan")
        party.amc_code = request.form.get("amc_code")
        party.address = request.form.get("address")
        party.state = request.form.get("state")
        party.state_code = request.form.get("state_code")
        party.email = request.form.get("email")
        party.phone = request.form.get("phone")

        existing = Party.query.filter(
            Party.gstin == party.gstin, Party.id != party_id
        ).first()
        if existing:
            flash(f"Party with GSTIN {party.gstin} already exists", "danger")
            return redirect(url_for("edit_party", party_id=party_id))

        db.session.commit()
        flash("Party updated successfully", "success")
        return redirect(url_for("parties"))

    return render_template("edit_party.html", party=party)


@app.route("/party/delete/<int:party_id>")
def delete_party(party_id):
    party = Party.query.get_or_404(party_id)
    db.session.delete(party)
    db.session.commit()
    flash("Party deleted successfully", "success")
    return redirect(url_for("parties"))


@app.route("/invoices", methods=["GET"])
def manage_invoices():
    year = request.args.get("year")
    month = request.args.get("month")
    search = request.args.get("search", "").strip()
    sort_by = request.args.get("sort_by", "invoice_no")
    sort_dir = request.args.get("sort_dir", "desc")
    selected_year = year
    selected_month = month
    search_query = search
    tax_type_filter = request.args.get("tax_type", "")
    party_filter = request.args.get("party", "")

    query = Invoice.query.join(Party)

    if year:
        query = query.filter(db.extract("year", Invoice.invoice_date) == int(year))
    if month:
        query = query.filter(db.extract("month", Invoice.invoice_date) == int(month))
    if search:
        query = query.filter(
            db.or_(
                Invoice.invoice_no.ilike(f"%{search}%"),
                Invoice.reference_serial_no.ilike(f"%{search}%"),
                Party.gstin.ilike(f"%{search}%"),
                Party.name.ilike(f"%{search}%"),
            )
        )
    if tax_type_filter:
        query = query.filter(Invoice.tax_type == tax_type_filter)
    if party_filter:
        query = query.filter(Invoice.party_id == int(party_filter))

    sort_column = Invoice.invoice_no
    if sort_by == "date":
        sort_column = Invoice.invoice_date
    elif sort_by == "party":
        sort_column = Party.name

    if sort_dir == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    invoices = query.all()
    parties = Party.query.all()
    pending_count = Invoice.query.filter(Invoice.invoice_no == None).count()

    all_invoices = Invoice.query.all()
    years = sorted(
        set(inv.invoice_date.year for inv in all_invoices if inv.invoice_date)
    )
    if not years:
        years = [datetime.now().year]

    return render_template(
        "invoice_management.html",
        invoices=invoices,
        parties=parties,
        selected_year=selected_year,
        selected_month=selected_month,
        search_query=search_query,
        years=years,
        sort_by=sort_by,
        sort_dir=sort_dir,
        tax_type_filter=tax_type_filter,
        party_filter=party_filter,
        pending_count=pending_count,
    )


@app.route("/invoice/create", methods=["GET", "POST"])
def create_invoice():
    parties = Party.query.all()

    if request.method == "POST":
        party_id = request.form.get("party_id")
        reference_serial_no = request.form.get("reference_serial_no", "").strip()
        sac_hsn_code = request.form.get("sac_hsn_code", "").strip()

        if not party_id:
            flash("Party selection is required.", "danger")
            return redirect(url_for("create_invoice"))

        if not sac_hsn_code:
            flash("SAC/HSN code is required.", "danger")
            return redirect(url_for("create_invoice"))

        if reference_serial_no:
            existing = Invoice.query.filter(
                Invoice.reference_serial_no == reference_serial_no
            ).first()
            if existing:
                flash(
                    f"Reference serial number {reference_serial_no} already exists",
                    "danger",
                )
                return redirect(url_for("create_invoice"))

        invoice_date = datetime.strptime(
            request.form.get("invoice_date"), "%Y-%m-%d"
        ).date()
        tax_type = request.form.get("tax_type")
        place_of_supply = request.form.get("place_of_supply")
        sac_hsn_code = request.form.get("sac_hsn_code")
        reverse_charge = float(request.form.get("reverse_charge") or 0)
        is_rcm = request.form.get("is_rcm") == "on"
        distributor_code = request.form.get("distributor_code", "").strip()

        if is_rcm and reverse_charge <= 0:
            flash("Reverse Charge amount is required when RCM is enabled.", "danger")
            return redirect(url_for("create_invoice"))

        invoice = Invoice(
            reference_serial_no=reference_serial_no,
            invoice_date=invoice_date,
            party_id=party_id,
            tax_type=tax_type,
            place_of_supply=place_of_supply,
            sac_hsn_code=sac_hsn_code,
            reverse_charge=reverse_charge,
            is_rcm=is_rcm,
            distributor_code=distributor_code,
        )

        # Local copy of party details
        party = Party.query.get(party_id)
        if party:
            invoice.party_name = party.name
            invoice.party_address = party.address
            invoice.party_gstin = party.gstin
            invoice.party_pan = party.pan
            invoice.party_state = party.state
            invoice.party_state_code = party.state_code

        db.session.add(invoice)
        db.session.flush()

        items_desc = request.form.getlist("item_description[]")
        items_taxable = request.form.getlist("item_taxable_value[]")
        items_cgst_rate = request.form.getlist("item_cgst_rate[]")
        items_sgst_rate = request.form.getlist("item_sgst_rate[]")
        items_igst_rate = request.form.getlist("item_igst_rate[]")

        for i in range(len(items_desc)):
            if items_desc[i].strip():
                taxable = float(items_taxable[i]) if i < len(items_taxable) else 0
                cgst_rate = float(items_cgst_rate[i]) if i < len(items_cgst_rate) else 0
                sgst_rate = float(items_sgst_rate[i]) if i < len(items_sgst_rate) else 0
                igst_rate = float(items_igst_rate[i]) if i < len(items_igst_rate) else 0

                is_valid, error_msg = validate_tax_rates(
                    tax_type, is_rcm, cgst_rate, sgst_rate, igst_rate
                )
                if not is_valid:
                    flash(f"Item '{items_desc[i][:30]}': {error_msg}", "danger")
                    return redirect(url_for("create_invoice"))

                cgst_amt = taxable * cgst_rate / 100 if tax_type == "INTRA" else 0
                sgst_amt = taxable * sgst_rate / 100 if tax_type == "INTRA" else 0
                igst_amt = taxable * igst_rate / 100 if tax_type == "INTER" else 0

                item = InvoiceItem(
                    invoice_id=invoice.id,
                    description=items_desc[i],
                    taxable_value=taxable,
                    cgst_rate=cgst_rate,
                    cgst_amt=cgst_amt,
                    sgst_rate=sgst_rate,
                    sgst_amt=sgst_amt,
                    igst_rate=igst_rate,
                    igst_amt=igst_amt,
                )
                db.session.add(item)

        db.session.commit()
        flash("Invoice created successfully", "success")
        return redirect(url_for("manage_invoices"))

    return render_template("create_invoice.html", parties=parties)


@app.route("/invoice/<int:invoice_id>")
def view_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template(
        "invoice_preview.html",
        invoice=invoice,
        settings={
            "company_name": Settings.get("company_name", ""),
            "address": Settings.get("address", ""),
            "gstin": Settings.get("gstin", ""),
            "pan": Settings.get("pan", ""),
            "logo": Settings.get("logo", ""),
        },
    )


@app.route("/invoice/delete/<int:invoice_id>")
def delete_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    db.session.delete(invoice)
    db.session.commit()
    flash("Invoice deleted successfully", "success")
    return redirect(url_for("dashboard"))


@app.route("/invoice/pdf/<int:invoice_id>")
def generate_pdf(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)

    html_content = render_template(
        "invoice_pdf_template.html",
        invoice=invoice,
        settings={
            "company_name": Settings.get("company_name", ""),
            "address": Settings.get("address", ""),
            "gstin": Settings.get("gstin", ""),
            "pan": Settings.get("pan", ""),
            "logo": Settings.get("logo", ""),
            "place_of_supply": Settings.get("place_of_supply", ""),
            "state_code": Settings.get("state_code", ""),
        },
    )

    # Replace / with _ for filename safety
    safe_filename = (
        invoice.invoice_no.replace("/", "_")
        if invoice.invoice_no
        else f"invoice_{invoice.id}"
    )
    pdf_path = os.path.join(app.config["EXPORT_FOLDER"], f"{safe_filename}.pdf")

    HTML(string=html_content).write_pdf(pdf_path)

    download_name = (
        f"{invoice.invoice_no}.pdf"
        if invoice.invoice_no
        else f"invoice_{invoice.id}.pdf"
    )
    return send_file(pdf_path, as_attachment=True, download_name=download_name)


@app.route("/invoice/preview-html/<int:invoice_id>")
def preview_html(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template("invoice_print.html", invoice=invoice)


@app.route("/invoice/generate-numbers", methods=["POST"])
def generate_numbers():
    count = generate_invoice_numbers()
    if count > 0:
        flash(f"Generated invoice numbers for {count} invoices", "success")
    else:
        flash("No pending invoices to generate numbers for", "warning")
    return redirect(url_for("manage_invoices"))


@app.route("/batch/export", methods=["POST"])
def batch_export():
    invoice_ids = request.form.getlist("invoice_ids")

    if not invoice_ids:
        flash("No invoices selected", "warning")
        return redirect(url_for("dashboard"))

    zip_path = os.path.join(
        app.config["EXPORT_FOLDER"],
        f"invoices_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
    )

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for invoice_id in invoice_ids:
            invoice = Invoice.query.get(invoice_id)
            if not invoice or not invoice.invoice_no:
                continue

            html_content = render_template(
                "invoice_pdf_template.html",
                invoice=invoice,
                settings={
                    "company_name": Settings.get("company_name", ""),
                    "arn_number": Settings.get("arn_number", ""),
                    "address": Settings.get("address", ""),
                    "gstin": Settings.get("gstin", ""),
                    "pan": Settings.get("pan", ""),
                    "logo": Settings.get("logo", ""),
                    "place_of_supply": Settings.get("place_of_supply", ""),
                    "state_code": Settings.get("state_code", ""),
                },
            )
            safe_filename = (
                invoice.invoice_no.replace("/", "_")
                if invoice.invoice_no
                else f"invoice_{invoice.id}"
            )
            pdf_path = os.path.join(app.config["EXPORT_FOLDER"], f"{safe_filename}.pdf")

            HTML(string=html_content).write_pdf(pdf_path)

            zip_filename = (
                f"{invoice.invoice_no}.pdf"
                if invoice.invoice_no
                else f"invoice_{invoice.id}.pdf"
            )
            zip_file.write(pdf_path, zip_filename)
            os.remove(pdf_path)

    return send_file(zip_path, as_attachment=True, download_name=f"invoices_batch.zip")


@app.route("/import/parties", methods=["GET", "POST"])
def import_parties():
    if request.method == "POST":
        file = request.files.get("csv_file")

        if not file or file.filename == "":
            flash("No file selected", "danger")
            return redirect(url_for("import_parties"))

        if not file.filename.endswith(".csv"):
            flash("Please upload a CSV file", "danger")
            return redirect(url_for("import_parties"))

        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)

        imported = 0
        errors = []

        for row_num, row in enumerate(csv_reader, start=2):
            try:
                gstin = (row.get("gstin") or "").strip().upper()
                name = (row.get("name") or "").strip()
                provided_pan = (row.get("pan") or "").strip().upper()
                amc_code = (row.get("amc_code") or "").strip()
                address = (row.get("address") or "").strip()
                state = (row.get("state") or "").strip()
                state_code = (row.get("state_code") or "").strip()

                if not name or not gstin:
                    errors.append(f"Row {row_num}: Missing name or GSTIN")
                    continue

                pan = provided_pan if provided_pan else extract_pan_from_gstin(gstin)

                existing = Party.query.filter_by(gstin=gstin).first()
                if existing:
                    existing.name = name
                    existing.pan = pan
                    if amc_code:
                        existing.amc_code = amc_code
                    if address:
                        existing.address = address
                    if state:
                        existing.state = state
                    if state_code:
                        existing.state_code = state_code
                    imported += 1
                else:
                    party = Party(
                        name=name,
                        gstin=gstin,
                        pan=pan,
                        amc_code=amc_code,
                        address=address,
                        state=state,
                        state_code=state_code,
                    )
                    db.session.add(party)
                    imported += 1

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

        if imported > 0:
            db.session.commit()
            flash(f"Successfully imported {imported} parties", "success")

        if errors:
            for error in errors[:10]:
                flash(error, "warning")

        return redirect(url_for("parties"))

    return render_template("import_parties.html")


@app.route("/import/invoices", methods=["GET", "POST"])
def import_invoices():
    if request.method == "POST":
        file = request.files.get("csv_file")

        if not file or file.filename == "":
            flash("No file selected", "danger")
            return redirect(url_for("import_invoices"))

        if not file.filename.endswith(".csv"):
            flash("Please upload a CSV file", "danger")
            return redirect(url_for("import_invoices"))

        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)

        imported = 0
        updated = 0
        errors = []

        for row_num, row in enumerate(csv_reader, start=2):
            try:
                invoice_no = (row.get("invoice_no") or "").strip()
                reference_serial_no = (row.get("reference_serial_no") or "").strip()
                invoice_date_str = (row.get("invoice_date") or "").strip()
                party_gstin = (row.get("party_gstin") or "").strip().upper()
                description = (row.get("description") or "").strip()
                sac_hsn_code = (row.get("sac_hsn_code") or "").strip()
                taxable_value = parse_number(row.get("taxable_value"))
                tax_type = parse_tax_type(row.get("tax_type"))
                cgst_rate = parse_percentage(row.get("cgst_rate"))
                sgst_rate = parse_percentage(row.get("sgst_rate"))
                igst_rate = parse_percentage(row.get("igst_rate"))
                place_of_supply = (row.get("place_of_supply") or "").strip()
                reverse_charge = parse_number(row.get("reverse_charge"))
                is_rcm = (row.get("is_rcm") or "").strip() == "1"
                distributor_code = (row.get("distributor_code") or "").strip()

                if not party_gstin or not invoice_date_str:
                    errors.append(f"Row {row_num}: Missing GSTIN or Invoice Date")
                    continue

                party = Party.query.filter_by(gstin=party_gstin).first()
                if not party:
                    errors.append(
                        f"Row {row_num}: Party with GSTIN {party_gstin} not found"
                    )
                    continue

                invoice_date = parse_date(invoice_date_str)
                if not invoice_date:
                    errors.append(
                        f"Row {row_num}: Invalid date format - {invoice_date_str}"
                    )
                    continue

                if is_rcm and reverse_charge <= 0:
                    errors.append(
                        f"Row {row_num}: Reverse Charge amount is required when RCM is enabled"
                    )
                    continue

                invoice = None
                if invoice_no:
                    invoice = Invoice.query.filter_by(invoice_no=invoice_no).first()
                elif reference_serial_no:
                    invoice = Invoice.query.filter_by(
                        reference_serial_no=reference_serial_no
                    ).first()

                if invoice:
                    if invoice.locked:
                        errors.append(
                            f"Row {row_num}: Invoice {invoice.invoice_no or invoice.id} is locked and cannot be updated"
                        )
                        continue

                    invoice.invoice_no = invoice_no or invoice.invoice_no
                    invoice.reference_serial_no = (
                        reference_serial_no or invoice.reference_serial_no
                    )
                    invoice.invoice_date = invoice_date
                    invoice.party_id = party.id
                    invoice.tax_type = tax_type
                    invoice.place_of_supply = place_of_supply
                    invoice.sac_hsn_code = sac_hsn_code
                    invoice.reverse_charge = reverse_charge
                    invoice.is_rcm = is_rcm
                    invoice.distributor_code = distributor_code

                    # Update local copy
                    invoice.party_name = party.name
                    invoice.party_address = party.address
                    invoice.party_gstin = party.gstin
                    invoice.party_pan = party.pan
                    invoice.party_state = party.state
                    invoice.party_state_code = party.state_code
                    updated += 1
                else:
                    invoice = Invoice(
                        invoice_no=invoice_no or None,
                        reference_serial_no=reference_serial_no,
                        invoice_date=invoice_date,
                        party_id=party.id,
                        tax_type=tax_type,
                        place_of_supply=place_of_supply,
                        sac_hsn_code=sac_hsn_code,
                        reverse_charge=reverse_charge,
                        is_rcm=is_rcm,
                        distributor_code=distributor_code,
                    )
                    # Local copy
                    invoice.party_name = party.name
                    invoice.party_address = party.address
                    invoice.party_gstin = party.gstin
                    invoice.party_pan = party.pan
                    invoice.party_state = party.state
                    invoice.party_state_code = party.state_code
                    db.session.add(invoice)
                    db.session.flush()
                    imported += 1

                if invoice:
                    InvoiceItem.query.filter_by(invoice_id=invoice.id).delete()

                is_valid, error_msg = validate_tax_rates(
                    tax_type, is_rcm, cgst_rate, sgst_rate, igst_rate
                )
                if not is_valid:
                    errors.append(
                        f"Row {row_num}: Invalid tax configuration - {error_msg}"
                    )
                    continue

                cgst_amt = 0
                sgst_amt = 0
                igst_amt = 0
                if not is_rcm:
                    cgst_amt = (
                        taxable_value * cgst_rate / 100 if tax_type == "INTRA" else 0
                    )
                    sgst_amt = (
                        taxable_value * sgst_rate / 100 if tax_type == "INTRA" else 0
                    )
                    igst_amt = (
                        taxable_value * igst_rate / 100 if tax_type == "INTER" else 0
                    )

                item = InvoiceItem(
                    invoice_id=invoice.id,
                    description=description,
                    taxable_value=taxable_value,
                    cgst_rate=cgst_rate,
                    cgst_amt=cgst_amt,
                    sgst_rate=sgst_rate,
                    sgst_amt=sgst_amt,
                    igst_rate=igst_rate,
                    igst_amt=igst_amt,
                )
                db.session.add(item)

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

        if imported > 0 or updated > 0:
            db.session.commit()
            flash(
                f"Successfully imported {imported} new and updated {updated} existing invoices",
                "success",
            )

        if errors:
            flash(
                f"Failed to import {len(errors)} rows. See below for first 10 errors:",
                "warning",
            )
            for error in errors[:10]:
                flash(error, "info")

        return redirect(url_for("manage_invoices"))

    return render_template("import_invoices.html")


@app.route("/invoice/sync-party/<int:invoice_id>")
def sync_party(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if invoice.locked:
        return jsonify(
            {"success": False, "message": "Locked invoices cannot be synced"}
        ), 403
    party = Party.query.get(invoice.party_id)
    if not party:
        return jsonify({"success": False, "message": "Linked party not found"}), 404
    invoice.party_name = party.name
    invoice.party_address = party.address
    invoice.party_gstin = party.gstin
    invoice.party_pan = party.pan
    invoice.party_state = party.state
    invoice.party_state_code = party.state_code
    db.session.commit()
    return jsonify(
        {
            "success": True,
            "data": {
                "name": invoice.party_name,
                "address": invoice.party_address,
                "gstin": invoice.party_gstin,
                "pan": invoice.party_pan,
                "state": invoice.party_state,
                "state_code": invoice.party_state_code,
            },
        }
    )


@app.route("/invoice/batch-sync", methods=["POST"])
def batch_sync():
    ids_raw = request.form.get("invoice_ids", "")
    invoice_ids = ids_raw.split(",") if ids_raw else []
    if not invoice_ids or invoice_ids == [""]:
        flash("No invoices selected", "warning")
        return redirect(url_for("manage_invoices"))
    synced_count, locked_count = 0, 0
    for inv_id in invoice_ids:
        inv = Invoice.query.get(inv_id)
        if inv:
            if inv.locked:
                locked_count += 1
                continue
            party = Party.query.get(inv.party_id)
            if party:
                inv.party_name = party.name
                inv.party_address = party.address
                inv.party_gstin = party.gstin
                inv.party_pan = party.pan
                inv.party_state = party.state
                inv.party_state_code = party.state_code
                synced_count += 1
    db.session.commit()
    if synced_count > 0:
        flash(
            f"Successfully synced party details for {synced_count} invoices", "success"
        )
    if locked_count > 0:
        flash(f"Skipped {locked_count} locked invoices", "info")
    return redirect(url_for("manage_invoices"))


@app.route("/invoice/batch-lock", methods=["POST"])
def batch_lock():
    ids_raw = request.form.get("invoice_ids", "")
    invoice_ids = ids_raw.split(",") if ids_raw else []
    if not invoice_ids or invoice_ids == [""]:
        flash("No invoices selected", "warning")
        return redirect(url_for("manage_invoices"))
    locked_count = 0
    for inv_id in invoice_ids:
        inv = Invoice.query.get(inv_id)
        if inv:
            inv.locked = True
            locked_count += 1
    db.session.commit()
    if locked_count > 0:
        flash(f"Successfully locked {locked_count} invoices", "success")
    return redirect(url_for("manage_invoices"))


@app.route("/invoice/batch-unlock", methods=["POST"])
def batch_unlock():
    ids_raw = request.form.get("invoice_ids", "")
    invoice_ids = ids_raw.split(",") if ids_raw else []
    if not invoice_ids or invoice_ids == [""]:
        flash("No invoices selected", "warning")
        return redirect(url_for("manage_invoices"))
    unlocked_count = 0
    for inv_id in invoice_ids:
        inv = Invoice.query.get(inv_id)
        if inv:
            inv.locked = False
            unlocked_count += 1
    db.session.commit()
    if unlocked_count > 0:
        flash(f"Successfully unlocked {unlocked_count} invoices", "success")
    return redirect(url_for("manage_invoices"))


@app.route("/invoice/batch-delete", methods=["POST"])
def batch_delete():
    ids_raw = request.form.get("invoice_ids", "")
    invoice_ids = ids_raw.split(",") if ids_raw else []
    if not invoice_ids or invoice_ids == [""]:
        flash("No invoices selected", "warning")
        return redirect(url_for("manage_invoices"))
    deleted_count = 0
    for inv_id in invoice_ids:
        inv = Invoice.query.get(inv_id)
        if inv and not inv.locked:
            db.session.delete(inv)
            deleted_count += 1
    db.session.commit()
    if deleted_count > 0:
        flash(f"Successfully deleted {deleted_count} invoices", "success")
    else:
        flash("No invoices deleted (some may be locked)", "warning")
    return redirect(url_for("manage_invoices"))


@app.route("/invoice/edit/<int:invoice_id>", methods=["GET", "POST"])
def edit_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if invoice.locked:
        flash("This invoice is locked and cannot be edited.", "danger")
        return redirect(url_for("manage_invoices"))
    parties = Party.query.all()

    if request.method == "POST":
        invoice_no = request.form.get("invoice_no", "").strip()
        reference_serial_no = request.form.get("reference_serial_no", "").strip()

        if invoice_no:
            existing = Invoice.query.filter(
                Invoice.invoice_no == invoice_no, Invoice.id != invoice_id
            ).first()
            if existing:
                flash(f"Invoice number {invoice_no} already exists", "danger")
                return redirect(url_for("edit_invoice", invoice_id=invoice_id))

        if reference_serial_no:
            existing = Invoice.query.filter(
                Invoice.reference_serial_no == reference_serial_no,
                Invoice.id != invoice_id,
            ).first()
            if existing:
                flash(
                    f"Reference serial number {reference_serial_no} already exists",
                    "danger",
                )
                return redirect(url_for("edit_invoice", invoice_id=invoice_id))

        invoice.invoice_no = invoice_no or None
        invoice.reference_serial_no = reference_serial_no or None
        invoice.party_id = request.form.get("party_id")
        invoice.invoice_date = datetime.strptime(
            request.form.get("invoice_date"), "%Y-%m-%d"
        ).date()
        invoice.tax_type = request.form.get("tax_type")
        invoice.place_of_supply = request.form.get("place_of_supply")
        invoice.sac_hsn_code = request.form.get("sac_hsn_code")
        invoice.reverse_charge = float(request.form.get("reverse_charge") or 0)
        invoice.is_rcm = request.form.get("is_rcm") == "on"
        invoice.distributor_code = request.form.get("distributor_code", "").strip()

        # Local copy overrides
        invoice.party_name = request.form.get("party_name", "").strip()
        invoice.party_address = request.form.get("party_address", "").strip()
        invoice.party_gstin = request.form.get("party_gstin", "").strip().upper()
        invoice.party_pan = request.form.get("party_pan", "").strip().upper()
        invoice.party_state = request.form.get("party_state", "").strip()
        invoice.party_state_code = request.form.get("party_state_code", "").strip()

        if invoice.is_rcm and invoice.reverse_charge <= 0:
            flash("Reverse Charge amount is required when RCM is enabled.", "danger")
            return redirect(url_for("edit_invoice", invoice_id=invoice_id))

        if invoice.invoice_no and not invoice.total_in_words:
            invoice.total_in_words = number_to_words(invoice.calculate_gst()["total"])

        for item in invoice.items:
            db.session.delete(item)

        items_desc = request.form.getlist("item_description[]")
        items_taxable = request.form.getlist("item_taxable_value[]")
        items_cgst_rate = request.form.getlist("item_cgst_rate[]")
        items_sgst_rate = request.form.getlist("item_sgst_rate[]")
        items_igst_rate = request.form.getlist("item_igst_rate[]")

        tax_type = request.form.get("tax_type")
        is_rcm = request.form.get("is_rcm") == "on"

        for i in range(len(items_desc)):
            if items_desc[i].strip():
                taxable = float(items_taxable[i]) if i < len(items_taxable) else 0
                cgst_rate = float(items_cgst_rate[i]) if i < len(items_cgst_rate) else 0
                sgst_rate = float(items_sgst_rate[i]) if i < len(items_sgst_rate) else 0
                igst_rate = float(items_igst_rate[i]) if i < len(items_igst_rate) else 0

                is_valid, error_msg = validate_tax_rates(
                    tax_type, is_rcm, cgst_rate, sgst_rate, igst_rate
                )
                if not is_valid:
                    flash(f"Item '{items_desc[i][:30]}': {error_msg}", "danger")
                    return redirect(url_for("edit_invoice", invoice_id=invoice_id))

                cgst_amt = taxable * cgst_rate / 100 if tax_type == "INTRA" else 0
                sgst_amt = taxable * sgst_rate / 100 if tax_type == "INTRA" else 0
                igst_amt = taxable * igst_rate / 100 if tax_type == "INTER" else 0

                item = InvoiceItem(
                    invoice_id=invoice.id,
                    description=items_desc[i],
                    taxable_value=taxable,
                    cgst_rate=cgst_rate,
                    cgst_amt=cgst_amt,
                    sgst_rate=sgst_rate,
                    sgst_amt=sgst_amt,
                    igst_rate=igst_rate,
                    igst_amt=igst_amt,
                )
                db.session.add(item)

        db.session.commit()
        flash("Invoice updated successfully", "success")
        return redirect(url_for("manage_invoices"))

    return render_template("edit_invoice.html", invoice=invoice, parties=parties)


@app.template_filter("currency")
def currency_filter(value):
    if value is None or value == "":
        return "0.00"
    try:
        return f"{float(value):,.2f}"
    except (ValueError, TypeError):
        return "0.00"


@app.context_processor
def inject_now():
    from datetime import datetime

    return dict(
        current_date=datetime.utcnow().strftime("%Y-%m-%d"),
        settings={
            "company_name": Settings.get("company_name", ""),
            "arn_number": Settings.get("arn_number", ""),
            "address": Settings.get("address", ""),
            "gstin": Settings.get("gstin", ""),
            "pan": Settings.get("pan", ""),
            "logo": Settings.get("logo", ""),
            "place_of_supply": Settings.get("place_of_supply", ""),
            "state_code": Settings.get("state_code", ""),
        },
    )


def init_db():
    with app.app_context():
        db.create_all()


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
