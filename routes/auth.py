from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import timedelta, datetime, timezone
from models import User, RecoveryCode, ConfigStore, generate_recovery_code, db
from forms import LoginForm, SetupForm, RecoveryCodeForm
from constants import RECOVERY_CODE_COUNT


auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard.dashboard"))

    # If no users exist, show setup link
    if not User.query.first():
        session["no_users"] = True

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.is_active and user.check_password(form.password.data):
            session["user_id"] = user.id
            session["username"] = user.username
            session["full_name"] = user.full_name
            session["role"] = user.role

            session.pop("setup_codes", None)
            session.pop("new_codes", None)

            if form.remember.data:
                session.permanent = True
                # We can't access app.config here directly, but we can use current_app
                from flask import current_app
                current_app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
            else:
                session.permanent = True
                from flask import current_app
                current_app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

            flash(f"Welcome back, {user.full_name}!", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard.dashboard"))
        else:
            flash("Invalid username or password", "danger")

    return render_template("login.html", form=form)


@auth_bp.route("/logout")
def logout():
    session.pop("setup_codes", None)
    session.pop("new_codes", None)
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    if User.query.first():
        return redirect(url_for("auth.login"))

    form = SetupForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            full_name=form.full_name.data,
            role="admin",
            must_change_password=False,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        codes = []
        for _ in range(RECOVERY_CODE_COUNT):
            code = generate_recovery_code()
            codes.append(code)
            rc = RecoveryCode(code=code, user_id=user.id)
            db.session.add(rc)

        db.session.commit()
        
        session["setup_codes"] = codes
        # Removed ConfigStore.set for setup_codes to ensure consistency with admin management
        
        flash("Setup complete!", "success")
        return redirect(url_for("auth.setup_success"))

    return render_template("setup.html", form=form)


@auth_bp.route("/setup-success")
def setup_success():
    from flask import session
    codes = session.get("setup_codes", [])
    if not codes:
        # Fallback: get codes for the only user (since this is setup)
        user = User.query.first()
        if user:
            rcs = RecoveryCode.query.filter_by(user_id=user.id, is_used=False).all()
            codes = [rc.code for rc in rcs]
        else:
            return redirect(url_for("auth.setup"))
            
    if not codes:
        return redirect(url_for("auth.setup"))
    return render_template("setup_success.html", codes=codes)


@auth_bp.route("/download-setup-codes")
def download_setup_codes():
    codes = session.get("setup_codes", [])
    if not codes:
        codes_str = ConfigStore.get("setup_codes", "")
        codes = [c for c in codes_str.split(",") if c] if codes_str else []
    if not codes:
        flash("No codes to download", "warning")
        return redirect(url_for("auth.setup"))

    content = "Recovery Codes\n"
    content += "=" * 50 + "\n\n"
    for i, code in enumerate(codes, 1):
        content += f"{i}. {code[:4]}-{code[4:]}\n"
    content += "\n" + "=" * 50 + "\n"
    content += "Each code can only be used once.\n"
    content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

    from flask import send_file
    return (
        content.encode(),
        200,
        {
            "Content-Type": "text/plain",
            "Content-Disposition": "attachment;filename=recovery_codes.txt",
        },
    )


@auth_bp.route("/recovery", methods=["GET", "POST"])
def recovery():
    if request.method == "POST":
        code = request.form.get("code", "").strip().replace("-", "").replace(" ", "")

        recovery = RecoveryCode.query.filter_by(
            code=code.upper(), is_used=False
        ).first()

        if not recovery:
            flash("Invalid or used recovery code", "danger")
        else:
            user = db.session.get(User, recovery.user_id)
            new_password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")

            if not new_password:
                recovery.is_used = True
                recovery.used_at = datetime.now(timezone.utc)
                db.session.commit()
                session["recovery_user_id"] = user.id
                session["resetting_password"] = True
                flash("Code verified! Set your new password.", "success")
                return redirect(url_for("auth.recovery"))

            if new_password != confirm:
                flash("Passwords do not match", "danger")
            elif len(new_password) < 6:
                flash("Password must be at least 6 characters", "danger")
            else:
                user.set_password(new_password)
                recovery.is_used = True
                recovery.used_at = datetime.now(timezone.utc)
                db.session.commit()
                flash("Password reset successful! Please login.", "success")
                return redirect(url_for("auth.login"))

    return render_template("recovery.html")
