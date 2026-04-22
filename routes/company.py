from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import Company, db
from utils import login_required



company_bp = Blueprint('company', __name__)

@company_bp.route("/company", methods=["GET", "POST"])
@login_required
def company():
    if request.method == "POST":
        company_id = request.form.get("company_id")
        company_name = request.form.get("company_name")
        address = request.form.get("address")
        gstin = request.form.get("gstin")
        pan = request.form.get("pan")
        set_as_default = request.form.get("set_as_default") == "on"

        if company_id:
            company = db.session.get(Company, int(company_id))
            if company:
                company.name = company_name
                company.address = address
                company.gstin = gstin
                company.pan = pan
        else:
            current_count = Company.query.count()
            is_default = current_count == 0
            
            company = Company(
                name=company_name,
                address=address,
                gstin=gstin,
                pan=pan,
                is_default=is_default
            )
            db.session.add(company)
            db.session.flush()
            
            if current_count == 0:
                pass
            elif set_as_default:
                Company.query.filter(Company.id != company.id).update({"is_default": False})

        if "logo" in request.files and request.files["logo"].filename:
            logo = request.files["logo"]
            logo_filename = f"company_{company.id}_logo.png" if company.id else "company_logo.png"
            from flask import current_app
            logo_path = os.path.join(current_app.config["LOGO_FOLDER"], logo_filename)
            logo.save(logo_path)
            if company:
                company.logo = logo_filename

        db.session.commit()
        flash("Company saved successfully", "success")
        return redirect(url_for("company.company"))

    companies = Company.query.order_by(Company.is_default.desc(), Company.name).all()
    can_delete = len(companies) > 1
    default_company = Company.query.filter_by(is_default=True).first()

    return render_template(
        "company.html",
        companies=companies,
        can_delete=can_delete,
        default_company=default_company,
    )

@company_bp.route("/company/delete/<int:company_id>", methods=["POST"])
@login_required
def delete_company(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        flash("Company not found", "danger")
        return redirect(url_for("company.company"))

    if company.is_default:
        flash("Cannot delete default company", "danger")
        return redirect(url_for("company.company"))

    if Company.query.count() <= 1:
        flash("Cannot delete the only company. At least one company is required.", "danger")
        return redirect(url_for("company.company"))

    db.session.delete(company)
    db.session.commit()
    flash("Company deleted successfully", "success")
    return redirect(url_for("company.company"))


@company_bp.route("/company/set-default/<int:company_id>", methods=["POST"])
@login_required
def set_default_company(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        flash("Company not found", "danger")
        return redirect(url_for("company.company"))

    Company.query.update({"is_default": False})
    company.is_default = True
    db.session.commit()
    flash(f"{company.name} set as default", "success")
    return redirect(url_for("company.company"))


def _execute_company_import(companies_data, change_default=False):
    """Execute company import from pre-validated data.

    Args:
        companies_data: List of dicts with company data
        change_default: If True, will change the default company
    """
    imported = 0
    updated = 0
    errors = []

    existing_default = Company.query.filter_by(is_default=True).first() if change_default else None
    new_default_id = None

    for company_data in companies_data:
        try:
            is_update = company_data.get("is_update", False)
            existing_id = company_data.get("existing_id")

            if is_update and existing_id:
                existing = db.session.get(Company, existing_id)
                if existing:
                    existing.name = company_data["name"]
                    if company_data.get("gstin"):
                        existing.gstin = company_data["gstin"]
                    if company_data.get("pan"):
                        existing.pan = company_data["pan"]
                    if company_data.get("address"):
                        existing.address = company_data["address"]
                    if change_default and company_data.get("is_default"):
                        Company.query.filter(Company.id != existing.id).update({"is_default": False})
                        existing.is_default = True
                        new_default_id = existing.id
                    updated += 1
            else:
                company = Company(
                    name=company_data["name"],
                    gstin=company_data.get("gstin") or None,
                    pan=company_data.get("pan") or None,
                    address=company_data.get("address") or None,
                    is_default=False
                )
                db.session.add(company)
                db.session.flush()
                if change_default and company_data.get("is_default"):
                    Company.query.filter(Company.id != company.id).update({"is_default": False})
                    company.is_default = True
                    new_default_id = company.id
                imported += 1

        except Exception as e:
            errors.append(f"Error: {str(e)}")

    db.session.commit()

    return {
        "imported": imported,
        "updated": updated,
        "errors": errors,
        "previous_default": existing_default.name if existing_default else None,
        "new_default_id": new_default_id
    }


@company_bp.route("/import/companies", methods=["GET", "POST"])
def import_companies():
    if request.method == "POST":
        confirm = request.form.get("confirm")
        if confirm == "true":
            return redirect(url_for("company.import_companies_confirm"))

        file = request.files.get("csv_file")

        if not file or file.filename == "":
            flash("No file selected", "danger")
            return redirect(url_for("company.import_companies"))

        if not file.filename.endswith(".csv"):
            flash("Please upload a CSV file", "danger")
            return redirect(url_for("company.import_companies"))

        import io, csv
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)

        companies_data = []
        default_count = 0
        errors = []

        for row_num, row in enumerate(csv_reader, start=2):
            try:
                name = (row.get("name") or "").strip()
                gstin = (row.get("gstin") or "").strip().upper()
                pan = (row.get("pan") or "").strip().upper()
                address = (row.get("address") or "").strip()
                is_default_str = (row.get("is_default") or "").strip().lower()
                is_default = is_default_str in ("1", "true", "yes")

                if not name:
                    errors.append(f"Row {row_num}: Missing company name")
                    continue

                existing = Company.query.filter(
                    (Company.name == name) | (Company.gstin == gstin)
                ).first()

                company_data = {
                    "name": name,
                    "gstin": gstin or None,
                    "pan": pan or None,
                    "address": address or None,
                    "is_default": is_default,
                    "is_update": bool(existing),
                    "existing_id": existing.id if existing else None
                }
                companies_data.append(company_data)

                if is_default:
                    default_count += 1

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

        if errors:
            for error in errors[:10]:
                flash(error, "warning")
            return render_template("import_companies.html")

        if default_count > 1:
            flash(f"Only one default company is allowed. Found {default_count} companies with is_default=true.", "danger")
            return redirect(url_for("company.import_companies"))

        existing_default = Company.query.filter_by(is_default=True).first()
        new_default_company = next((c for c in companies_data if c.get("is_default")), None)
        needs_confirmation = False
        new_default_name = None

        if new_default_company:
            new_default_name = new_default_company["name"]
            if existing_default:
                if new_default_company.get("is_update") and new_default_company["existing_id"] == existing_default.id:
                    needs_confirmation = False
                else:
                    needs_confirmation = True

        if needs_confirmation:
            session["pending_companies_import"] = companies_data
            session["confirm_change_default"] = True
            session["previous_default_name"] = existing_default.name
            session["new_default_name"] = new_default_name
            return render_template(
                "import_companies_confirm.html",
                previous_default=existing_default.name,
                new_default=new_default_name
            )

        result = _execute_company_import(companies_data, change_default=bool(new_default_company))
        flash(f"Successfully imported {result['imported']} new and updated {result['updated']} existing companies", "success")

        return redirect(url_for("company.company"))

    return render_template("import_companies.html")


@company_bp.route("/import/companies/confirm", methods=["POST"])
@login_required
def import_companies_confirm():
    confirm_action = request.form.get("confirm_action")

    if confirm_action == "cancel":
        session.pop("pending_companies_import", None)
        session.pop("confirm_change_default", None)
        session.pop("previous_default_name", None)
        session.pop("new_default_name", None)
        flash("Import cancelled. No changes were made.", "info")
        return redirect(url_for("company.import_companies"))

    companies_data = session.get("pending_companies_import")
    if not companies_data:
        flash("No pending import found. Please upload a CSV file.", "warning")
        return redirect(url_for("company.import_companies"))

    previous_default = session.get("previous_default_name")
    new_default = session.get("new_default_name")

    result = _execute_company_import(companies_data, change_default=True)

    session.pop("pending_companies_import", None)
    session.pop("confirm_change_default", None)
    session.pop("previous_default_name", None)
    session.pop("new_default_name", None)

    message = f"Successfully imported {result['imported']} new and updated {result['updated']} existing companies"
    if previous_default and new_default:
        message += f". Default changed from {previous_default} to {new_default}."
    flash(message, "success")

    return redirect(url_for("company.company"))


@company_bp.route("/delete-logo")
@login_required
def delete_logo():
    company_id = request.args.get("company_id", type=int)
    if company_id:
        company = db.session.get(Company, company_id)
        if company and company.logo:
            import os
            from flask import current_app
            logo_path = os.path.join(current_app.config["LOGO_FOLDER"], company.logo)
            if os.path.exists(logo_path):
                os.remove(logo_path)
            company.logo = None
            db.session.commit()
            flash("Logo deleted", "success")
    return redirect(url_for("company.company"))
