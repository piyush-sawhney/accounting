from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
import io, csv
from datetime import datetime
from models import Party, db
from utils import login_required



parties_bp = Blueprint('parties', __name__)

@parties_bp.route("/party/api/<int:party_id>")
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


@parties_bp.route("/parties", methods=["GET", "POST"])
@login_required
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

        # Basic validation
        if not name or not name.strip():
            flash("Party name is required", "danger")
            return redirect(url_for("parties.parties"))
        
        if not gstin or not gstin.strip():
            flash("GSTIN is required", "danger")
            return redirect(url_for("parties.parties"))

        existing = Party.query.filter_by(gstin=gstin.strip()).first()
        if existing:
            flash(f"Party with GSTIN {gstin.strip()} already exists", "danger")
            return redirect(url_for("parties.parties"))

        party = Party(
            name=name.strip(),
            gstin=gstin.strip(),
            amc_code=amc_code.strip() if amc_code else None,
            pan=pan.strip() if pan else None,
            address=address.strip() if address else None,
            state=state.strip() if state else None,
            state_code=state_code.strip() if state_code else None,
            email=email.strip() if email else None,
            phone=phone.strip() if phone else None,
        )
        db.session.add(party)
        db.session.commit()
        flash("Party added successfully", "success")
        return redirect(url_for("parties.parties"))

    sort_by = request.args.get("sort_by", "name")
    sort_dir = request.args.get("sort_dir", "asc")

    sort_column = getattr(Party, sort_by, Party.name)
    if sort_dir == "desc":
        query = Party.query.order_by(sort_column.desc())
    else:
        query = Party.query.order_by(sort_column.asc())

    parties_list = query.all()
    return render_template(
        "parties.html", parties=parties_list, sort_by=sort_by, sort_dir=sort_dir
    )


@parties_bp.route("/party/create", methods=["GET", "POST"])
@login_required
def create_party():
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

        if not name or not name.strip():
            flash("Party name is required", "danger")
            return redirect(url_for("parties.create_party"))
        
        if not gstin or not gstin.strip():
            flash("GSTIN is required", "danger")
            return redirect(url_for("parties.create_party"))

        existing = Party.query.filter_by(gstin=gstin.strip()).first()
        if existing:
            flash(f"Party with GSTIN {gstin.strip()} already exists", "danger")
            return redirect(url_for("parties.create_party"))

        party = Party(
            name=name.strip(),
            gstin=gstin.strip(),
            amc_code=amc_code.strip() if amc_code else None,
            pan=pan.strip() if pan else None,
            address=address.strip() if address else None,
            state=state.strip() if state else None,
            state_code=state_code.strip() if state_code else None,
            email=email.strip() if email else None,
            phone=phone.strip() if phone else None,
        )
        db.session.add(party)
        db.session.commit()
        flash("Party added successfully", "success")
        return redirect(url_for("parties.parties"))

    return render_template("create_party.html")


@parties_bp.route("/export/parties")
def export_parties():
    parties_list = Party.query.all()
    return export_parties_response(parties_list)


@parties_bp.route("/export/parties/selected", methods=["POST"])
def export_selected_parties():
    ids_raw = request.form.get("party_ids", "")
    party_ids = [int(x) for x in ids_raw.split(",") if x] if ids_raw else []
    if not party_ids:
        flash("No parties selected", "warning")
        return redirect(url_for("parties.parties"))
    parties_list = Party.query.filter(Party.id.in_(party_ids)).all()
    return export_parties_response(parties_list)


def export_parties_response(parties_list):
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
        ]
    )

    for party in parties_list:
        writer.writerow(
            [
                party.name,
                party.gstin,
                party.pan or "",
                party.amc_code or "",
                party.address or "",
                party.state or "",
                party.state_code or "",
            ]
        )

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"parties_export_{datetime.now().strftime('%Y%m%d')}.csv",
    )


@parties_bp.route("/party/edit/<int:party_id>", methods=["GET", "POST"])
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
            return redirect(url_for("parties.edit_party", party_id=party_id))

        db.session.commit()
        flash("Party updated successfully", "success")
        return redirect(url_for("parties.parties"))

    return render_template("edit_party.html", party=party)


@parties_bp.route("/party/delete/<int:party_id>")
def delete_party(party_id):
    from models import Invoice
    party = Party.query.get_or_404(party_id)

    invoice_count = Invoice.query.filter_by(party_id=party_id).count()
    if invoice_count > 0:
        flash(
            f"Cannot delete party with {invoice_count} existing invoice(s). Delete invoices first.",
            "danger",
        )
        return redirect(url_for("parties.parties"))

    db.session.delete(party)
    db.session.commit()
    flash("Party deleted successfully", "success")
    return redirect(url_for("parties.parties"))


@parties_bp.route("/import/parties", methods=["GET", "POST"])
@login_required
def import_parties():
    if request.method == "POST":
        file = request.files.get("csv_file")
        if not file or file.filename == "":
            flash("No file selected", "danger")
            return redirect(url_for("parties.import_parties"))

        if not file.filename.endswith(".csv"):
            flash("Please upload a CSV file", "danger")
            return redirect(url_for("parties.import_parties"))

        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)

        imported = 0
        updated = 0
        errors = []

        for row_num, row in enumerate(csv_reader, start=2):
            try:
                gstin = (row.get("gstin") or "").strip().upper()
                name = (row.get("name") or "").strip()
                
                if not name or not gstin:
                    errors.append(f"Row {row_num}: Missing name or GSTIN")
                    continue

                existing = Party.query.filter_by(gstin=gstin).first()
                if existing:
                    existing.name = name
                    if row.get("pan"):
                        existing.pan = row.get("pan").strip().upper()
                    if row.get("amc_code"):
                        existing.amc_code = row.get("amc_code").strip().upper()
                    if row.get("address"):
                        existing.address = row.get("address").strip()
                    if row.get("state"):
                        existing.state = row.get("state").strip()
                    if row.get("state_code"):
                        existing.state_code = row.get("state_code").strip()
                    updated += 1
                else:
                    party = Party(
                        name=name,
                        gstin=gstin,
                        pan=row.get("pan", "").strip().upper() if row.get("pan") else None,
                        amc_code=row.get("amc_code", "").strip().upper() if row.get("amc_code") else None,
                        address=row.get("address", "").strip() if row.get("address") else None,
                        state=row.get("state", "").strip() if row.get("state") else None,
                        state_code=row.get("state_code", "").strip() if row.get("state_code") else None,
                    )
                    db.session.add(party)
                    imported += 1
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

        if imported > 0 or updated > 0:
            db.session.commit()
            if imported > 0:
                flash(f"Successfully imported {imported} new parties", "success")
            if updated > 0:
                flash(f"Successfully updated {updated} existing parties", "success")

        if errors:
            for error in errors[:10]:
                flash(error, "warning")

        return redirect(url_for("parties.parties"))

    return render_template("import_parties.html")
