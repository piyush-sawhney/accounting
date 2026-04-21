from flask import Blueprint, render_template, request, redirect, url_for, flash
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


@company_bp.route("/import/companies", methods=["GET", "POST"])
def import_companies():
    if request.method == "POST":
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

        imported = 0
        updated = 0
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

                if existing:
                    existing.name = name
                    if gstin:
                        existing.gstin = gstin
                    if pan:
                        existing.pan = pan
                    if address:
                        existing.address = address
                    if is_default and not existing.is_default:
                        Company.query.filter(Company.id != existing.id).update({"is_default": False})
                        existing.is_default = True
                    updated += 1
                else:
                    company = Company(
                        name=name,
                        gstin=gstin or None,
                        pan=pan or None,
                        address=address or None,
                        is_default=is_default or (Company.query.count() == 0)
                    )
                    db.session.add(company)
                    if is_default:
                        db.session.flush()
                        Company.query.filter(Company.id != company.id).update({"is_default": False})
                    imported += 1

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")

        if imported > 0 or updated > 0:
            db.session.commit()
            flash(f"Successfully imported {imported} new and updated {updated} existing companies", "success")

        if errors:
            for error in errors[:10]:
                flash(error, "warning")

        return redirect(url_for("company.company"))

    return render_template("import_companies.html")


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
