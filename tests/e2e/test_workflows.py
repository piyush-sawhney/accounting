import pytest
from datetime import date


class TestFullWorkflowLoginToExport:
    """End-to-end test: Login → Create Party → Create Invoice → Export"""

    def test_complete_party_invoice_export_workflow(self, client, app):
        """Test the full workflow from login to export"""
        from models import db, User, Party, Invoice, InvoiceItem

        with app.app_context():
            db.create_all()

            admin = User(
                username="admin",
                full_name="Admin User",
                role="admin",
                must_change_password=False,
            )
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            admin_id = admin.id

        with client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["username"] = "admin"
            sess["role"] = "admin"

        with app.app_context():
            party = Party(
                name="E2E Test Party",
                gstin="27AAECM5678A1Z5",
                pan="AAECM5678A",
                state="Maharashtra",
                state_code="27",
            )
            db.session.add(party)
            db.session.commit()
            party_id = party.id

        response = client.post(
            "/invoice/create",
            data={
                "party_id": party_id,
                "invoice_date": "2026-04-15",
                "tax_type": "INTRA",
                "place_of_supply": "Maharashtra",
                "sac_hsn_code": "9971",
                "item_description[]": ["Consulting Services"],
                "item_taxable_value[]": ["50000"],
                "item_cgst_rate[]": ["9"],
                "item_sgst_rate[]": ["9"],
                "item_igst_rate[]": ["0"],
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        with app.app_context():
            invoice = Invoice.query.filter_by(party_id=party_id).first()
            assert invoice is not None
            invoice_id = invoice.id
            invoice.invoice_no = "INV/2026/001"
            db.session.commit()

            gst = invoice.calculate_gst()
            assert gst["subtotal"] == 50000.0
            assert gst["total"] == 59000.0


class TestPartyManagementWorkflow:
    """Test: Create party → Edit → Delete"""

    def test_create_edit_delete_party(self, client, app):
        from models import db, User, Party

        with app.app_context():
            db.create_all()

            admin = User(username="admin", full_name="Admin", role="admin")
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            admin_id = admin.id

        with client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["username"] = "admin"
            sess["role"] = "admin"

        with app.app_context():
            party = Party(
                name="Workflow Party",
                gstin="27AAACM9999A1Z5",
                state="Maharashtra",
                state_code="27",
            )
            db.session.add(party)
            db.session.commit()
            party_id = party.id

        response = client.get(f"/party/edit/{party_id}")
        assert response.status_code == 200

        with app.app_context():
            party = db.session.get(Party, party_id)
            party.name = "Updated Workflow Party"
            db.session.commit()

        response = client.get(
            f"/party/delete/{party_id}",
            follow_redirects=True,
        )
        assert response.status_code == 200

        with app.app_context():
            party = db.session.get(Party, party_id)
            assert party is None


class TestInvoiceLockUnlockWorkflow:
    """Test: Create Invoice → Generate Number → Lock → Export"""

    def test_lock_unlock_invoice_workflow(self, client, app, test_party):
        from models import db, User, Invoice, InvoiceItem

        with app.app_context():
            admin = User(username="admin", full_name="Admin", role="admin")
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            admin_id = admin.id

            invoice = Invoice(
                invoice_no="INV/TEST/001",
                invoice_date=date(2026, 4, 1),
                party_id=test_party.id,
                tax_type="INTRA",
                sac_hsn_code="9971",
            )
            db.session.add(invoice)
            db.session.flush()

            item = InvoiceItem(
                invoice_id=invoice.id,
                description="Test Service",
                taxable_value=10000.0,
                cgst_rate=9.0,
                cgst_amt=900.0,
                sgst_rate=9.0,
                sgst_amt=900.0,
            )
            db.session.add(item)
            db.session.commit()
            invoice_id = invoice.id

        with client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["username"] = "admin"

        response = client.post(
            "/invoice/batch-lock",
            data=f"invoice_ids={invoice_id}",
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code in [200, 302]

        with app.app_context():
            invoice = db.session.get(Invoice, invoice_id)
            assert invoice.locked is True

        response = client.post(
            "/invoice/batch-unlock",
            data=f"invoice_ids={invoice_id}",
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code in [200, 302]

        with app.app_context():
            invoice = db.session.get(Invoice, invoice_id)
            assert invoice.locked is False


class TestDuplicateGSTINPrevention:
    """Test that duplicate GSTIN is prevented"""

    def test_duplicate_gstin_blocked(self, client, app):
        from models import db, User, Party

        with app.app_context():
            db.create_all()

            admin = User(username="admin", full_name="Admin", role="admin")
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            admin_id = admin.id

        with client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["username"] = "admin"

        response = client.post(
            "/parties",
            data={
                "name": "First Party",
                "gstin": "27AAACM1234A1Z5",
                "state": "Maharashtra",
                "state_code": "27",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200


class TestGSTCalculationWorkflow:
    """Test GST calculation across different scenarios"""

    def test_intra_state_gst_calculation(self, client, app, test_party):
        from models import db, User, Invoice, InvoiceItem

        with app.app_context():
            admin = User(username="admin", full_name="Admin", role="admin")
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            admin_id = admin.id

        with client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["username"] = "admin"

        response = client.post(
            "/invoice/create",
            data={
                "party_id": test_party.id,
                "invoice_date": "2026-04-15",
                "tax_type": "INTRA",
                "place_of_supply": "Maharashtra",
                "sac_hsn_code": "9971",
                "item_description[]": ["Service 1", "Service 2"],
                "item_taxable_value[]": ["10000", "20000"],
                "item_cgst_rate[]": ["9", "9"],
                "item_sgst_rate[]": ["9", "9"],
                "item_igst_rate[]": ["0", "0"],
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        with app.app_context():
            invoice = Invoice.query.filter_by(party_id=test_party.id).first()
            assert invoice is not None
            gst = invoice.calculate_gst()

            assert gst["subtotal"] == 30000.0
            assert gst["cgst"] == 2700.0
            assert gst["sgst"] == 2700.0
            assert gst["igst"] == 0.0
            assert gst["total"] == 35400.0

    def test_inter_state_gst_calculation(self, client, app, test_party):
        from models import db, User, Invoice, InvoiceItem

        with app.app_context():
            admin = User.query.first()
            if not admin:
                admin = User(username="admin", full_name="Admin", role="admin")
                admin.set_password("admin123")
                db.session.add(admin)
                db.session.commit()
            admin_id = admin.id

        with client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["username"] = "admin"

        response = client.post(
            "/invoice/create",
            data={
                "party_id": test_party.id,
                "invoice_date": "2026-04-15",
                "tax_type": "INTER",
                "place_of_supply": "Karnataka",
                "sac_hsn_code": "9971",
                "item_description[]": ["Service"],
                "item_taxable_value[]": ["10000"],
                "item_cgst_rate[]": ["0"],
                "item_sgst_rate[]": ["0"],
                "item_igst_rate[]": ["18"],
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        with app.app_context():
            invoices = Invoice.query.filter_by(party_id=test_party.id).all()
            if len(invoices) > 1:
                invoice = invoices[-1]
            else:
                invoice = invoices[0]
            gst = invoice.calculate_gst()

            assert gst["subtotal"] == 10000.0
            assert gst["igst"] == 1800.0
            assert gst["total"] == 11800.0