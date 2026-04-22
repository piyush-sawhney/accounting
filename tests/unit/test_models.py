import pytest
from datetime import date, datetime
from decimal import Decimal


class TestPartyModel:
    def test_party_to_dict(self, app, test_party):
        with app.app_context():
            result = test_party.to_dict()

            assert result["name"] == "Test Party"
            assert result["gstin"] == "27AAACM1234A1Z5"
            assert result["pan"] == "AAACM1234A"
            assert result["amc_code"] == "AMC001"
            assert result["state"] == "Maharashtra"
            assert result["state_code"] == "27"

    def test_party_to_dict_with_nulls(self, app):
        from models import Party, db

        with app.app_context():
            party = Party(
                name="Minimal Party",
                gstin="27AAACM9999A1Z5",
            )
            db.session.add(party)
            db.session.commit()

            result = party.to_dict()
            assert result["name"] == "Minimal Party"
            assert result["pan"] is None
            assert result["amc_code"] is None
            assert result["address"] is None


class TestInvoiceModel:
    def test_invoice_to_dict(self, app, test_invoice):
        with app.app_context():
            assert test_invoice.invoice_no == "INV/001"
            assert test_invoice.tax_type == "INTRA"

    def test_invoice_calculate_gst_intra(self, app, test_party):
        from models import Invoice, InvoiceItem, db

        with app.app_context():
            invoice = Invoice(
                invoice_no="INV/002",
                invoice_date=date(2026, 4, 1),
                party_id=test_party.id,
                tax_type="INTRA",
                sac_hsn_code="9971",
                party_name=test_party.name,
                party_gstin=test_party.gstin,
            )
            db.session.add(invoice)
            db.session.flush()

            item = InvoiceItem(
                invoice_id=invoice.id,
                description="Test Service",
                taxable_value=10000.00,
                cgst_rate=9.0,
                cgst_amt=900.00,
                sgst_rate=9.0,
                sgst_amt=900.00,
            )
            db.session.add(item)
            db.session.commit()

            gst = invoice.calculate_gst()

            assert gst["subtotal"] == 10000.00
            assert gst["cgst"] == 900.00
            assert gst["sgst"] == 900.00
            assert gst["igst"] == 0
            assert gst["total"] == 11800.00

    def test_invoice_calculate_gst_inter(self, app, test_party):
        from models import Invoice, InvoiceItem, db

        with app.app_context():
            invoice = Invoice(
                invoice_no="INV/003",
                invoice_date=date(2026, 4, 1),
                party_id=test_party.id,
                tax_type="INTER",
                sac_hsn_code="9971",
                party_name=test_party.name,
                party_gstin=test_party.gstin,
            )
            db.session.add(invoice)
            db.session.flush()

            item = InvoiceItem(
                invoice_id=invoice.id,
                description="Test Service",
                taxable_value=10000.00,
                cgst_rate=0,
                cgst_amt=0,
                sgst_rate=0,
                sgst_amt=0,
                igst_rate=18.0,
                igst_amt=1800.00,
            )
            db.session.add(item)
            db.session.commit()

            gst = invoice.calculate_gst()

            assert gst["subtotal"] == 10000.00
            assert gst["cgst"] == 0
            assert gst["sgst"] == 0
            assert gst["igst"] == 1800.00
            assert gst["total"] == 11800.00

    def test_invoice_calculate_gst_multiple_items(self, app, test_party):
        from models import Invoice, InvoiceItem, db

        with app.app_context():
            invoice = Invoice(
                invoice_no="INV/004",
                invoice_date=date(2026, 4, 1),
                party_id=test_party.id,
                tax_type="INTRA",
                party_name=test_party.name,
                party_gstin=test_party.gstin,
            )
            db.session.add(invoice)
            db.session.flush()

            item1 = InvoiceItem(
                invoice_id=invoice.id,
                description="Service 1",
                taxable_value=10000.00,
                cgst_rate=9.0,
                cgst_amt=900.00,
                sgst_rate=9.0,
                sgst_amt=900.00,
            )
            item2 = InvoiceItem(
                invoice_id=invoice.id,
                description="Service 2",
                taxable_value=5000.00,
                cgst_rate=9.0,
                cgst_amt=450.00,
                sgst_rate=9.0,
                sgst_amt=450.00,
            )
            db.session.add(item1)
            db.session.add(item2)
            db.session.commit()

            gst = invoice.calculate_gst()

            assert gst["subtotal"] == 15000.00
            assert gst["cgst"] == 1350.00
            assert gst["sgst"] == 1350.00
            assert gst["total"] == 17700.00

    def test_invoice_calculate_gst_rounding(self, app, test_party):
        from models import Invoice, InvoiceItem, db

        with app.app_context():
            invoice = Invoice(
                invoice_no="INV/005",
                invoice_date=date(2026, 4, 1),
                party_id=test_party.id,
                tax_type="INTRA",
                party_name=test_party.name,
                party_gstin=test_party.gstin,
            )
            db.session.add(invoice)
            db.session.flush()

            item = InvoiceItem(
                invoice_id=invoice.id,
                description="Service",
                taxable_value=3333.33,
                cgst_rate=9.0,
                sgst_rate=9.0,
            )
            db.session.add(item)
            db.session.commit()

            gst = invoice.calculate_gst()
            assert gst["subtotal"] == 3333.33
            assert "total" in gst


class TestUserModel:
    def test_user_set_password(self, app):
        from models import User, db

        with app.app_context():
            user = User(username="newuser", full_name="New User", role="staff")
            user.set_password("password123")

            assert user.password_hash is not None
            assert user.password_hash != "password123"
            assert user.must_change_password is False

    def test_user_check_password(self, app):
        from models import User

        with app.app_context():
            user = User(username="newuser", full_name="New User", role="staff")
            user.set_password("password123")

            assert user.check_password("password123") is True
            assert user.check_password("wrongpass") is False

    def test_user_to_dict(self, app, test_user):
        with app.app_context():
            result = test_user.to_dict()

            assert result["username"] == "testuser"
            assert result["role"] == "admin"
            assert "password_hash" not in result

    def test_user_to_dict_includes_active_status(self, app, test_user):
        with app.app_context():
            result = test_user.to_dict()
            assert "is_active" in result
            assert result["is_active"] is True

    def test_user_to_dict_includes_must_change_password(self, app, test_user):
        with app.app_context():
            result = test_user.to_dict()
            assert "must_change_password" in result


class TestSettingsModel:
    def test_settings_get_default(self, app):
        from models import ConfigStore

        with app.app_context():
            result = ConfigStore.get("nonexistent_key", "default_value")
            assert result == "default_value"

    def test_settings_set_and_get(self, app):
        from models import ConfigStore

        with app.app_context():
            ConfigStore.set("test_key", "test_value")
            result = ConfigStore.get("test_key")

            assert result == "test_value"

    def test_settings_override(self, app):
        from models import ConfigStore

        with app.app_context():
            ConfigStore.set("test_key", "first_value")
            ConfigStore.set("test_key", "second_value")
            result = ConfigStore.get("test_key")

            assert result == "second_value"


class TestCreditNoteModel:
    def test_credit_note_calculate_gst(self, app, test_invoice):
        from models import CreditNote, CreditNoteItem, db

        with app.app_context():
            credit_note = CreditNote(
                credit_note_no="CN/001",
                credit_note_date=date(2026, 4, 1),
                invoice_id=test_invoice.id,
                reason="Wrong billing",
                tax_type="INTRA",
                party_name=test_invoice.party_name,
                party_gstin=test_invoice.party_gstin,
            )
            db.session.add(credit_note)
            db.session.flush()

            item = CreditNoteItem(
                credit_note_id=credit_note.id,
                description="Test Service",
                taxable_value=5000.00,
                cgst_rate=9.0,
                cgst_amt=450.00,
                sgst_rate=9.0,
                sgst_amt=450.00,
            )
            db.session.add(item)
            db.session.commit()

            gst = credit_note.calculate_gst()

            assert gst["subtotal"] == 5000.00
            assert gst["cgst"] == 450.00
            assert gst["sgst"] == 450.00
            assert gst["total"] == 5900.00

    def test_credit_note_serialization(self, app, test_credit_note):
        with app.app_context():
            assert test_credit_note.id is not None
            assert test_credit_note.reason is not None
            assert len(test_credit_note.items) > 0


class TestInvoiceItemModel:
    def test_invoice_item_to_dict(self, app, test_invoice):
        from models import InvoiceItem

        with app.app_context():
            item = InvoiceItem.query.first()
            result = item.to_dict()

            assert result["description"] == "Test Service"
            assert result["taxable_value"] == 10000.00
            assert result["cgst_rate"] == 9.0
            assert result["total"] == 11800.00

    def test_invoice_item_to_dict_with_igst(self, app, test_invoice_inter_state):
        from models import InvoiceItem

        with app.app_context():
            item = InvoiceItem.query.first()
            result = item.to_dict()

            assert result["igst_rate"] == 18.0
            assert result["igst_amt"] == 3600.00


class TestRecoveryCodeModel:
    def test_generate_recovery_code(self):
        from models import generate_recovery_code

        code = generate_recovery_code()

        assert len(code) == 8
        assert isinstance(code, str)

    def test_generate_recovery_code_unique(self):
        from models import generate_recovery_code

        codes = [generate_recovery_code() for _ in range(10)]
        assert len(set(codes)) > 1

    def test_recovery_code_to_dict(self, app, test_user):
        from models import RecoveryCode, db

        with app.app_context():
            code = RecoveryCode(code="A1B2C3D4", user_id=test_user.id)
            db.session.add(code)
            db.session.commit()

            result = code.to_dict()

            assert result["code"] == "A1B2-C3D4"
            assert result["is_used"] is False

    def test_recovery_code_to_dict_used(self, app, test_user):
        from models import RecoveryCode, db

        with app.app_context():
            code = RecoveryCode(code="E5F6G7H8", user_id=test_user.id, is_used=True)
            db.session.add(code)
            db.session.commit()

            result = code.to_dict()
            assert result["is_used"] is True


class TestConfigStoreModel:
    def test_config_store_get_set(self, app):
        from models import ConfigStore

        with app.app_context():
            ConfigStore.set("theme", "dark")
            result = ConfigStore.get("theme")

            assert result == "dark"

    def test_config_store_default(self, app):
        from models import ConfigStore

        with app.app_context():
            result = ConfigStore.get("missing", "fallback")
            assert result == "fallback"

    def test_config_store_none_value(self, app):
        from models import ConfigStore

        with app.app_context():
            ConfigStore.set("empty_key", None)
            result = ConfigStore.get("empty_key")
            assert result is None


class TestCompanyModel:
    def test_company_creation(self, app, test_company):
        from models import Company

        with app.app_context():
            company = Company.query.first()
            assert company.name == "Test Company"
            assert company.is_default is True


class TestInvoiceSequenceModel:
    def test_invoice_sequence_create(self, app):
        from models import InvoiceSequence, db

        with app.app_context():
            seq = InvoiceSequence(fy="2026-27", last_number=0)
            db.session.add(seq)
            db.session.commit()

            assert seq.fy == "2026-27"
            assert seq.last_number == 0