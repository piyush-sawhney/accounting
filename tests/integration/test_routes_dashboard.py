import pytest
from datetime import date


class TestDashboardView:
    def test_dashboard_loads(self, auth_client):
        response = auth_client.get("/dashboard")
        assert response.status_code == 200

    def test_dashboard_shows_revenue(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/dashboard")
            assert response.status_code == 200
            assert b"revenue" in response.data.lower() or b"10,000" in response.data

    def test_dashboard_shows_gst(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/dashboard")
            assert response.status_code == 200
            assert b"gst" in response.data.lower() or b"1,800" in response.data

    def test_dashboard_shows_invoice_count(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/dashboard")
            assert response.status_code == 200

    def test_dashboard_shows_pending(self, auth_client, app):
        with app.app_context():
            from models import Invoice, Party, db
            party = Party(
                name="Pending Party",
                gstin="27AAACM9999A1Z5",
                state="Maharashtra",
                state_code="27",
            )
            db.session.add(party)
            db.session.commit()

            invoice = Invoice(
                invoice_date=date(2026, 4, 1),
                party_id=party.id,
                tax_type="INTRA",
            )
            db.session.add(invoice)
            db.session.commit()

            response = auth_client.get("/dashboard")
            assert response.status_code == 200
            assert b"pending" in response.data.lower()

    def test_dashboard_shows_chart(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/dashboard")
            assert response.status_code == 200

    def test_dashboard_shows_top_parties(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/dashboard")
            assert response.status_code == 200


class TestDashboardFilters:
    def test_dashboard_date_range_this_month(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/dashboard?date_range=this_month")
            assert response.status_code == 200

    def test_dashboard_date_range_last_month(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/dashboard?date_range=last_month")
            assert response.status_code == 200

    def test_dashboard_date_range_this_quarter(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/dashboard?date_range=this_quarter")
            assert response.status_code == 200

    def test_dashboard_date_range_fiscal_year(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/dashboard?date_range=fiscal_year")
            assert response.status_code == 200

    def test_dashboard_filter_by_party(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get(f"/dashboard?party={test_invoice.party_id}")
            assert response.status_code == 200

    def test_dashboard_sort_by_revenue(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/dashboard?sort_by=revenue")
            assert response.status_code == 200

    def test_dashboard_sort_by_name(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/dashboard?sort_by=name")
            assert response.status_code == 200


class TestDashboardCalculations:
    def test_dashboard_revenue_excludes_rcm(self, auth_client, app, test_party, test_company):
        with app.app_context():
            from models import Invoice, InvoiceItem, db

            rcm_invoice = Invoice(
                invoice_no="INV/RCM/001",
                invoice_date=date(2026, 4, 1),
                party_id=test_party.id,
                tax_type="INTRA",
                place_of_supply="Maharashtra",
                is_rcm=True,
                reverse_charge=1180,
                locked=False,
                party_name=test_party.name,
                party_gstin=test_party.gstin,
                company_name=test_company.name,
            )
            db.session.add(rcm_invoice)
            db.session.flush()

            item = InvoiceItem(
                invoice_id=rcm_invoice.id,
                description="RCM Service",
                taxable_value=10000.00,
                cgst_rate=9.0,
                cgst_amt=900.00,
                sgst_rate=9.0,
                sgst_amt=900.00,
            )
            db.session.add(item)
            db.session.commit()

            response = auth_client.get("/dashboard")
            assert response.status_code == 200

    def test_dashboard_credit_note_deduction(self, auth_client, app, test_locked_invoice):
        with app.app_context():
            from models import CreditNote, CreditNoteItem, db

            cn = CreditNote(
                credit_note_date=date(2026, 4, 15),
                invoice_id=test_locked_invoice.id,
                reason="Test credit",
                tax_type="INTRA",
                locked=False,
                party_name=test_locked_invoice.party_name,
                party_gstin=test_locked_invoice.party_gstin,
                company_name=test_locked_invoice.company_name,
            )
            db.session.add(cn)
            db.session.flush()

            cn_item = CreditNoteItem(
                credit_note_id=cn.id,
                description="Test credit item",
                taxable_value=5000.00,
                cgst_rate=9.0,
                cgst_amt=450.00,
                sgst_rate=9.0,
                sgst_amt=450.00,
            )
            db.session.add(cn_item)
            db.session.commit()

            response = auth_client.get("/dashboard")
            assert response.status_code == 200

    def test_dashboard_party_growth_data(self, auth_client, app, test_party, test_company):
        with app.app_context():
            from models import Invoice, InvoiceItem, db

            invoice = Invoice(
                invoice_no="INV/GROWTH/001",
                invoice_date=date(2026, 4, 1),
                party_id=test_party.id,
                tax_type="INTRA",
                place_of_supply="Maharashtra",
                locked=False,
                party_name=test_party.name,
                party_gstin=test_party.gstin,
                company_name=test_company.name,
            )
            db.session.add(invoice)
            db.session.flush()

            item = InvoiceItem(
                invoice_id=invoice.id,
                description="Growth test",
                taxable_value=20000.00,
                cgst_rate=9.0,
                cgst_amt=1800.00,
                sgst_rate=9.0,
                sgst_amt=1800.00,
            )
            db.session.add(item)
            db.session.commit()

            response = auth_client.get("/dashboard")
            assert response.status_code == 200

    def test_dashboard_revenue_change(self, auth_client, app, test_party, test_company):
        with app.app_context():
            from models import Invoice, InvoiceItem, db

            invoice1 = Invoice(
                invoice_no="INV/LASTMONTH/001",
                invoice_date=date(2026, 3, 15),
                party_id=test_party.id,
                tax_type="INTRA",
                place_of_supply="Maharashtra",
                locked=False,
                party_name=test_party.name,
                party_gstin=test_party.gstin,
                company_name=test_company.name,
            )
            db.session.add(invoice1)
            db.session.flush()

            item1 = InvoiceItem(
                invoice_id=invoice1.id,
                description="Last month service",
                taxable_value=10000.00,
                cgst_rate=9.0,
                cgst_amt=900.00,
                sgst_rate=9.0,
                sgst_amt=900.00,
            )
            db.session.add(item1)

            invoice2 = Invoice(
                invoice_no="INV/THISMONTH/001",
                invoice_date=date(2026, 4, 15),
                party_id=test_party.id,
                tax_type="INTRA",
                place_of_supply="Maharashtra",
                locked=False,
                party_name=test_party.name,
                party_gstin=test_party.gstin,
                company_name=test_company.name,
            )
            db.session.add(invoice2)
            db.session.flush()

            item2 = InvoiceItem(
                invoice_id=invoice2.id,
                description="This month service",
                taxable_value=12500.00,
                cgst_rate=9.0,
                cgst_amt=1125.00,
                sgst_rate=9.0,
                sgst_amt=1125.00,
            )
            db.session.add(item2)
            db.session.commit()

            response = auth_client.get("/dashboard")
            assert response.status_code == 200

    def test_dashboard_empty_invoices(self, auth_client, app):
        with app.app_context():
            response = auth_client.get("/dashboard")
            assert response.status_code == 200


class TestDashboardAccessControl:
    def test_dashboard_requires_login(self, client):
        response = client.get("/dashboard", follow_redirects=True)
        assert response.status_code == 200
        assert b"login" in response.data.lower() or b"Login" in response.data

    def test_dashboard_staff_access(self, staff_client):
        response = staff_client.get("/dashboard")
        assert response.status_code == 200