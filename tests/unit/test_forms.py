import pytest


class TestLoginForm:
    def test_login_form_valid(self, app):
        from forms import LoginForm

        with app.app_context():
            form = LoginForm(
                username="testuser",
                password="password123",
            )
            assert form.validate() is True

    def test_login_form_missing_username(self, app):
        from forms import LoginForm

        with app.app_context():
            form = LoginForm(username="", password="password123")
            assert form.validate() is False

    def test_login_form_missing_password(self, app):
        from forms import LoginForm

        with app.app_context():
            form = LoginForm(username="testuser", password="")
            assert form.validate() is False

    def test_login_form_short_username(self, app):
        from forms import LoginForm

        with app.app_context():
            form = LoginForm(username="abc", password="password123")
            assert form.validate() is False


class TestSetupForm:
    def test_setup_form_valid(self, app):
        from forms import SetupForm

        with app.app_context():
            form = SetupForm(
                full_name="Test User",
                username="newuser",
                password="password123",
                confirm_password="password123",
            )
            assert form.validate() is True

    def test_setup_form_password_mismatch(self, app):
        from forms import SetupForm

        with app.app_context():
            form = SetupForm(
                full_name="Test User",
                username="newuser",
                password="password123",
                confirm_password="different",
            )
            assert form.validate() is False

    def test_setup_form_short_password(self, app):
        from forms import SetupForm

        with app.app_context():
            form = SetupForm(
                full_name="Test User",
                username="newuser",
                password="abc",
                confirm_password="abc",
            )
            assert form.validate() is False


class TestInvoiceForm:
    def test_invoice_form_valid_intra(self, app):
        from forms import InvoiceForm
        from datetime import date

        with app.app_context():
            form = InvoiceForm(
                invoice_date=date(2026, 4, 15),
                tax_type="INTRA",
                place_of_supply="Maharashtra",
                sac_hsn_code="9971",
            )
            assert form.validate() is True

    def test_invoice_form_valid_inter(self, app):
        from forms import InvoiceForm
        from datetime import date

        with app.app_context():
            form = InvoiceForm(
                invoice_date=date(2026, 4, 15),
                tax_type="INTER",
                place_of_supply="Karnataka",
                sac_hsn_code="9971",
            )
            assert form.validate() is True

    def test_invoice_form_valid_without_hsn(self, app):
        from forms import InvoiceForm
        from datetime import date

        with app.app_context():
            form = InvoiceForm(
                invoice_date=date(2026, 4, 15),
                tax_type="INTRA",
                place_of_supply="Maharashtra",
            )
            assert form.validate() is True

    def test_invoice_form_rcm_requires_reverse_charge(self, app):
        from forms import InvoiceForm
        from datetime import date

        with app.app_context():
            form = InvoiceForm(
                invoice_date=date(2026, 4, 15),
                tax_type="INTRA",
                sac_hsn_code="9971",
                is_rcm=True,
                reverse_charge=0,
            )
            assert form.validate() is False


class TestCreditNoteForm:
    def test_credit_note_form_valid(self, app):
        from forms import CreditNoteForm
        from datetime import date

        with app.app_context():
            form = CreditNoteForm(
                credit_note_date=date(2026, 4, 15),
                reason="Wrong billing",
                tax_type="INTRA",
            )
            assert form.validate() is True

    def test_credit_note_form_short_reason(self, app):
        from forms import CreditNoteForm
        from datetime import date

        with app.app_context():
            form = CreditNoteForm(
                credit_note_date=date(2026, 4, 15),
                reason="ABCD",
                tax_type="INTRA",
            )
            assert form.validate() is False


class TestRecoveryCodeForm:
    def test_recovery_form_valid(self, app):
        from forms import RecoveryCodeForm

        with app.app_context():
            form = RecoveryCodeForm(
                code="A1B2C3D4",
                password="newpass123",
                confirm_password="newpass123",
            )
            assert form.validate() is True

    def test_recovery_form_password_mismatch(self, app):
        from forms import RecoveryCodeForm

        with app.app_context():
            form = RecoveryCodeForm(
                code="A1B2C3D4",
                password="newpass123",
                confirm_password="different",
            )
            assert form.validate() is False

    def test_recovery_form_invalid_code_length(self, app):
        from forms import RecoveryCodeForm

        with app.app_context():
            form = RecoveryCodeForm(
                code="1234567",
                password="newpass123",
                confirm_password="newpass123",
            )
            assert form.validate() is False


class TestUserForm:
    def test_user_form_valid(self, app):
        from forms import UserForm

        with app.app_context():
            form = UserForm(
                full_name="New User",
                username="newuser",
                role="staff",
                password="password123",
            )
            assert form.validate() is True

    def test_user_form_short_username(self, app):
        from forms import UserForm

        with app.app_context():
            form = UserForm(
                full_name="New User",
                username="abc",
                role="staff",
            )
            assert form.validate() is False