from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
import io, csv, zipfile, os
from datetime import datetime
from models import User, Company, Party, Invoice, InvoiceItem, CreditNote, CreditNoteItem, RecoveryCode, ConfigStore, db, generate_recovery_code
from utils import admin_required, get_current_company



admin_bp = Blueprint('admin', __name__)

@admin_bp.route("/users", methods=["GET", "POST"])
@admin_required
def manage_users():
    from flask import session
    display_codes = session.pop("new_codes", None)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "create":
            full_name = request.form.get("full_name", "").strip()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "staff")

            if not full_name or not username or not password:
                flash("Full name, username and password required", "danger")
            elif User.query.filter_by(username=username).first():
                flash("Username already exists", "danger")
            else:
                user = User(
                    username=username,
                    full_name=full_name,
                    role=role,
                    must_change_password=True,
                )
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash(f"User {full_name} created", "success")

        elif action == "delete":
            user_id = request.form.get("user_id")
            user = db.session.get(User, int(user_id))
            if user and user.id != session.get("user_id"):
                username = user.username
                db.session.delete(user)
                db.session.commit()
                flash(f"User {username} deleted", "success")
            elif user and user.id == session.get("user_id"):
                flash("Cannot delete your own account", "danger")

        elif action == "reset_password":
            user_id = request.form.get("user_id")
            new_password = request.form.get("new_password", "")

            if not new_password or len(new_password) < 6:
                flash("Password must be at least 6 characters", "danger")
            else:
                user = db.session.get(User, int(user_id))
                user.set_password(new_password)
                user.must_change_password = True
                db.session.commit()
                flash(f"Password reset for {user.username}", "success")

    users = User.query.all()
    return render_template("users.html", users=users, display_codes=display_codes)


@admin_bp.route("/backup")
@admin_required
def backup():
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        parties = Party.query.all()
        party_data = io.StringIO()
        writer = csv.writer(party_data)
        writer.writerow(["gstin", "name", "pan", "amc_code", "address", "state", "state_code"])
        for p in parties:
            writer.writerow([p.gstin, p.name, p.pan, p.amc_code, p.address, p.state, p.state_code])
        zf.writestr("parties.csv", party_data.getvalue())

        invoices = Invoice.query.all()
        invoice_data = io.StringIO()
        writer = csv.writer(invoice_data)
        writer.writerow(["invoice_no", "reference_serial_no", "invoice_date", "party_gstin", "description", "sac_hsn_code", "taxable_value", "tax_type", "cgst_rate", "sgst_rate", "igst_rate", "place_of_supply", "reverse_charge", "is_rcm", "distributor_code"])
        for inv in invoices:
            party = db.session.get(Party, inv.party_id)
            party_gstin = party.gstin if party else ""
            items = InvoiceItem.query.filter_by(invoice_id=inv.id).all()
            for item in items:
                cgst_rate = item.cgst_rate or 0
                sgst_rate = item.sgst_rate or 0
                igst_rate = item.igst_rate or 0
                row = [
                    inv.invoice_no or "",
                    inv.reference_serial_no or "",
                    inv.invoice_date.isoformat() if inv.invoice_date else "",
                    party_gstin,
                    item.description or "",
                    inv.sac_hsn_code or "",
                    item.taxable_value,
                    inv.tax_type,
                    cgst_rate,
                    sgst_rate,
                    igst_rate,
                    inv.place_of_supply or "",
                    inv.reverse_charge or 0,
                    "1" if inv.is_rcm else "0",
                    inv.distributor_code or "",
                ]
                writer.writerow(row)
        zf.writestr("invoices.csv", invoice_data.getvalue())

        credit_notes = CreditNote.query.all()
        cn_data = io.StringIO()
        writer = csv.writer(cn_data)
        writer.writerow(["credit_note_no", "credit_note_date", "invoice_no", "reason", "tax_type", "place_of_supply", "description", "sac_hsn_code", "taxable_value", "cgst_rate", "sgst_rate", "igst_rate"])
        for cn in credit_notes:
            invoice = db.session.get(Invoice, cn.invoice_id)
            invoice_no = invoice.invoice_no if invoice else ""
            items = CreditNoteItem.query.filter_by(credit_note_id=cn.id).all()
            for item in items:
                cgst_rate = item.cgst_rate or 0
                sgst_rate = item.sgst_rate or 0
                igst_rate = item.igst_rate or 0
                row = [
                    cn.credit_note_no or "",
                    cn.credit_note_date.isoformat() if cn.credit_note_date else "",
                    invoice_no,
                    cn.reason or "",
                    cn.tax_type,
                    cn.place_of_supply or "",
                    item.description or "",
                    "",
                    item.taxable_value,
                    cgst_rate,
                    sgst_rate,
                    igst_rate,
                ]
                writer.writerow(row)
        zf.writestr("credit_notes.csv", cn_data.getvalue())

        users_list = User.query.all()
        user_data = io.StringIO()
        writer = csv.writer(user_data)
        writer.writerow(["username", "full_name", "role", "is_active"])
        for u in users_list:
            writer.writerow([u.username, u.full_name, u.role, "1" if u.is_active else "0"])
        zf.writestr("users.csv", user_data.getvalue())

        companies_data = io.StringIO()
        writer = csv.writer(companies_data)
        writer.writerow(["id", "name", "address", "gstin", "pan", "is_default"])
        for company in Company.query.all():
            writer.writerow([company.id, company.name, company.address or "", company.gstin or "", company.pan or "", company.is_default])
        zf.writestr("companies.csv", companies_data.getvalue())

        manifest = f"Backup created: {datetime.now().isoformat()}\n"
        manifest += f"Parties: {len(Party.query.all())}\n"
        manifest += f"Invoices: {len(Invoice.query.all())}\n"
        manifest += f"Credit Notes: {len(CreditNote.query.all())}\n"
        manifest += f"Users: {len(User.query.all())}\n"
        zf.writestr("manifest.txt", manifest)

    buffer.seek(0)
    filename = f"gst_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


@admin_bp.route("/users/generate-recovery-codes", methods=["POST"])
@admin_required
def generate_recovery_codes():
    from flask import session
    from constants import RECOVERY_CODE_COUNT
    
    user_id = session.get("user_id")
    if not user_id:
        flash("Authentication error", "danger")
        return redirect(url_for("admin.manage_users"))
    
    user = db.session.get(User, int(user_id))
    
    # Enforce Admin-Only Recovery (Self-Recovery)
    # Delete all existing unused recovery codes for this admin
    RecoveryCode.query.filter_by(user_id=user.id, is_used=False).delete()
    db.session.commit()
    
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        code = generate_recovery_code()
        codes.append(code)
        rc = RecoveryCode(code=code, user_id=user.id)
        db.session.add(rc)
    
    db.session.commit()
    
    # Store in session for immediate display in the modal
    session["new_codes"] = codes
    
    flash(f"Generated {len(codes)} new recovery codes for your account", "success")
    return redirect(url_for("admin.manage_users"))


@admin_bp.route("/users/download-recovery-codes")
@admin_required
def download_recovery_codes():
    from flask import session
    user_id = session.get("user_id")
    
    # Priority 1: Check session for immediately generated codes
    codes = session.get("new_codes", [])
    
    # Priority 2: Fallback to Database (Unused codes for this admin)
    if not codes:
        rcs = RecoveryCode.query.filter_by(user_id=user_id, is_used=False).all()
        codes = [rc.code for rc in rcs]
    
    if not codes:
        flash("No recovery codes available. Please generate new ones.", "warning")
        return redirect(url_for("admin.manage_users"))
    
    content = "Recovery Codes\n"
    content += "=" * 50 + "\n\n"
    for i, code in enumerate(codes, 1):
        content += f"{i}. {code[:4]}-{code[4:]}\n"
    content += "\n" + "=" * 50 + "\n"
    content += "Each code can only be used once.\n"
    content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    from flask import make_response
    response = make_response(content.encode())
    response.headers["Content-Disposition"] = "attachment;filename=recovery_codes.txt"
    response.headers["Content-Type"] = "text/plain"
    
    return response
