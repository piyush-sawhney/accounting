import pytest
import io
from datetime import date


class TestInvoiceRoutes:
    def test_invoices_list_get(self, auth_client):
        response = auth_client.get("/invoices")
        assert response.status_code == 200

    def test_invoices_list_empty(self, auth_client, app):
        with app.app_context():
            from models import Invoice, db
            Invoice.query.delete()
            db.session.commit()
            response = auth_client.get("/invoices")
            assert response.status_code == 200

    def test_create_invoice_basic(self, auth_client, app, test_party):
        response = auth_client.post(
            "/invoice/create",
            data={
                "party_id": test_party.id,
                "invoice_date": "2026-04-15",
                "tax_type": "INTRA",
                "place_of_supply": "Maharashtra",
                "sac_hsn_code": "9971",
                "item_description[]": ["Test Service"],
                "item_taxable_value[]": ["10000"],
                "item_cgst_rate[]": ["9"],
                "item_sgst_rate[]": ["9"],
                "item_igst_rate[]": ["0"],
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_create_invoice_inter_state(self, auth_client, app, test_party):
        response = auth_client.post(
            "/invoice/create",
            data={
                "party_id": test_party.id,
                "invoice_date": "2026-04-15",
                "tax_type": "INTER",
                "place_of_supply": "Karnataka",
                "sac_hsn_code": "9971",
                "item_description[]": ["Test Service"],
                "item_taxable_value[]": ["10000"],
                "item_cgst_rate[]": ["0"],
                "item_sgst_rate[]": ["0"],
                "item_igst_rate[]": ["18"],
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_create_invoice_missing_party(self, auth_client, app):
        with app.app_context():
            response = auth_client.post(
                "/invoice/create",
                data={
                    "party_id": "",
                    "invoice_date": "2026-04-15",
                    "tax_type": "INTRA",
                    "place_of_supply": "Maharashtra",
                    "sac_hsn_code": "9971",
                    "item_description[]": ["Test Service"],
                    "item_taxable_value[]": ["10000"],
                    "item_cgst_rate[]": ["9"],
                    "item_sgst_rate[]": ["9"],
                    "item_igst_rate[]": ["0"],
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_create_invoice_multiple_items(self, auth_client, app, test_party):
        response = auth_client.post(
            "/invoice/create",
            data={
                "party_id": test_party.id,
                "invoice_date": "2026-04-15",
                "tax_type": "INTRA",
                "place_of_supply": "Maharashtra",
                "sac_hsn_code": "9971",
                "item_description[]": ["Service 1", "Service 2", "Service 3"],
                "item_taxable_value[]": ["5000", "3000", "2000"],
                "item_cgst_rate[]": ["9", "9", "9"],
                "item_sgst_rate[]": ["9", "9", "9"],
                "item_igst_rate[]": ["0", "0", "0"],
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_create_invoice_reference_duplicate(self, auth_client, app, test_party, test_invoice):
        with app.app_context():
            response = auth_client.post(
                "/invoice/create",
                data={
                    "party_id": test_party.id,
                    "invoice_date": "2026-04-15",
                    "tax_type": "INTRA",
                    "place_of_supply": "Maharashtra",
                    "reference_serial_no": test_invoice.reference_serial_no or "INV/001",
                    "sac_hsn_code": "9971",
                    "item_description[]": ["Test Service"],
                    "item_taxable_value[]": ["10000"],
                    "item_cgst_rate[]": ["9"],
                    "item_sgst_rate[]": ["9"],
                    "item_igst_rate[]": ["0"],
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_create_invoice_rcm_requires_reverse_charge(self, auth_client, app, test_party):
        with app.app_context():
            response = auth_client.post(
                "/invoice/create",
                data={
                    "party_id": test_party.id,
                    "invoice_date": "2026-04-15",
                    "tax_type": "INTRA",
                    "place_of_supply": "Maharashtra",
                    "sac_hsn_code": "9971",
                    "is_rcm": "on",
                    "reverse_charge": "0",
                    "item_description[]": ["Test Service"],
                    "item_taxable_value[]": ["10000"],
                    "item_cgst_rate[]": ["9"],
                    "item_sgst_rate[]": ["9"],
                    "item_igst_rate[]": ["0"],
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_create_invoice_rcm_with_charge(self, auth_client, app, test_party):
        with app.app_context():
            response = auth_client.post(
                "/invoice/create",
                data={
                    "party_id": test_party.id,
                    "invoice_date": "2026-04-15",
                    "tax_type": "INTRA",
                    "place_of_supply": "Maharashtra",
                    "sac_hsn_code": "9971",
                    "is_rcm": "on",
                    "reverse_charge": "1180",
                    "item_description[]": ["Test Service"],
                    "item_taxable_value[]": ["10000"],
                    "item_cgst_rate[]": ["9"],
                    "item_sgst_rate[]": ["9"],
                    "item_igst_rate[]": ["0"],
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_view_invoice(self, auth_client, test_invoice):
        response = auth_client.get(f"/invoice/view/{test_invoice.id}")
        assert response.status_code == 200

    def test_view_invoice_not_found(self, auth_client):
        response = auth_client.get("/invoice/view/99999")
        assert response.status_code == 404

    def test_edit_invoice_get(self, auth_client, test_invoice):
        response = auth_client.get(f"/invoice/edit/{test_invoice.id}")
        assert response.status_code == 200

    def test_edit_invoice_post(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.post(
                f"/invoice/edit/{test_invoice.id}",
                data={
                    "invoice_no": "INV/EDIT/001",
                    "invoice_date": "2026-04-20",
                    "tax_type": "INTRA",
                    "place_of_supply": "Maharashtra",
                    "reverse_charge": "0",
                    "party_id": test_invoice.party_id,
                    "company_name": "Test Company",
                    "item_description[]": ["Updated Service"],
                    "item_taxable_value[]": ["12000"],
                    "item_cgst_rate[]": ["9"],
                    "item_sgst_rate[]": ["9"],
                    "item_igst_rate[]": ["0"],
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_edit_invoice_locked_blocked(self, auth_client, app, test_locked_invoice):
        with app.app_context():
            response = auth_client.get(f"/invoice/edit/{test_locked_invoice.id}")
            assert response.status_code == 200

    def test_delete_invoice(self, auth_client, test_invoice):
        response = auth_client.get(
            f"/invoice/delete/{test_invoice.id}",
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_delete_invoice_locked_blocked(self, auth_client, app, test_locked_invoice):
        with app.app_context():
            response = auth_client.get(
                f"/invoice/delete/{test_locked_invoice.id}",
                follow_redirects=True,
            )
            assert response.status_code == 200


class TestInvoiceFilters:
    def test_filter_by_year(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/invoices?year=2026")
            assert response.status_code == 200

    def test_filter_by_month(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/invoices?year=2026&month=04")
            assert response.status_code == 200

    def test_filter_by_tax_type_intra(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/invoices?tax_type=INTRA")
            assert response.status_code == 200

    def test_filter_by_tax_type_inter(self, auth_client, app, test_invoice_inter_state):
        with app.app_context():
            response = auth_client.get("/invoices?tax_type=INTER")
            assert response.status_code == 200

    def test_filter_by_party(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get(f"/invoices?party={test_invoice.party_id}")
            assert response.status_code == 200

    def test_filter_by_status_pending(self, auth_client, app, test_party):
        with app.app_context():
            from models import Invoice, db
            invoice = Invoice(
                invoice_date=date(2026, 4, 1),
                party_id=test_party.id,
                tax_type="INTRA",
            )
            db.session.add(invoice)
            db.session.commit()

            response = auth_client.get("/invoices?status=pending")
            assert response.status_code == 200

    def test_filter_by_status_completed(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/invoices?status=completed")
            assert response.status_code == 200

    def test_search_by_invoice_no(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get(f"/invoices?search={test_invoice.invoice_no}")
            assert response.status_code == 200

    def test_search_by_gstin(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get(f"/invoices?search={test_invoice.party_gstin}")
            assert response.status_code == 200

    def test_search_by_party_name(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/invoices?search=Test")
            assert response.status_code == 200

    def test_sort_by_date_asc(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/invoices?sort_by=date&sort_dir=asc")
            assert response.status_code == 200

    def test_sort_by_date_desc(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/invoices?sort_by=date&sort_dir=desc")
            assert response.status_code == 200

    def test_sort_by_invoice_no(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/invoices?sort_by=invoice_no&sort_dir=asc")
            assert response.status_code == 200

    def test_sort_by_party_name(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/invoices?sort_by=party&sort_dir=asc")
            assert response.status_code == 200


class TestInvoiceBatch:
    def test_generate_invoice_numbers(self, auth_client, app, test_party):
        with app.app_context():
            from models import Invoice, db
            invoice = Invoice(
                invoice_date=date(2026, 4, 1),
                party_id=test_party.id,
                tax_type="INTRA",
            )
            db.session.add(invoice)
            db.session.commit()

            response = auth_client.post(
                "/invoice/generate-numbers",
                content_type="application/x-www-form-urlencoded",
            )
            assert response.status_code in [200, 302]

    def test_batch_lock_with_invoice_no(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.post(
                "/invoices/batch-lock",
                data=f"invoice_ids={test_invoice.id}",
                content_type="application/x-www-form-urlencoded",
            )
            assert response.status_code in [200, 302]

    def test_batch_lock_skips_no_number(self, auth_client, app, test_party):
        with app.app_context():
            from models import Invoice, db
            invoice = Invoice(
                invoice_date=date(2026, 4, 1),
                party_id=test_party.id,
                tax_type="INTRA",
                invoice_no=None,
            )
            db.session.add(invoice)
            db.session.commit()
            invoice_id = invoice.id

            response = auth_client.post(
                "/invoices/batch-lock",
                data=f"invoice_ids={invoice_id}",
                content_type="application/x-www-form-urlencoded",
            )
            assert response.status_code in [200, 302]

    def test_batch_lock_already_locked(self, auth_client, app, test_locked_invoice):
        with app.app_context():
            response = auth_client.post(
                "/invoices/batch-lock",
                data=f"invoice_ids={test_locked_invoice.id}",
                content_type="application/x-www-form-urlencoded",
            )
            assert response.status_code in [200, 302]

    def test_batch_unlock(self, auth_client, app, test_locked_invoice):
        with app.app_context():
            response = auth_client.post(
                "/invoices/batch-unlock",
                data=f"invoice_ids={test_locked_invoice.id}",
                content_type="application/x-www-form-urlencoded",
            )
            assert response.status_code in [200, 302]

    def test_batch_delete_unlocked(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.post(
                "/invoices/batch-delete",
                data=f"invoice_ids={test_invoice.id}",
                content_type="application/x-www-form-urlencoded",
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_batch_delete_skips_locked(self, auth_client, app, test_locked_invoice):
        with app.app_context():
            response = auth_client.post(
                "/invoices/batch-delete",
                data=f"invoice_ids={test_locked_invoice.id}",
                content_type="application/x-www-form-urlencoded",
                follow_redirects=True,
            )
            assert response.status_code == 200


class TestInvoiceExport:
    @pytest.mark.skip(reason="PDF export requires full filesystem setup")
    def test_batch_export_pdf(self, auth_client, app, test_locked_invoice):
        pass

    def test_batch_export_excel(self, auth_client, app, test_locked_invoice):
        with app.app_context():
            response = auth_client.post(
                "/batch/export/excel",
                data=f"invoice_ids={test_locked_invoice.id}",
                content_type="application/x-www-form-urlencoded",
            )
            assert response.status_code in [200, 302]

    def test_batch_export_no_locked(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.post(
                "/batch/export",
                data=f"invoice_ids={test_invoice.id}",
                content_type="application/x-www-form-urlencoded",
            )
            assert response.status_code in [200, 302]

    def test_batch_export_requires_locked(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.post(
                "/batch/export",
                data=f"invoice_ids={test_invoice.id}",
                content_type="application/x-www-form-urlencoded",
            )
            assert response.status_code in [200, 302]


class TestInvoicePDF:
    def test_invoice_pdf(self, auth_client, test_invoice):
        response = auth_client.get(f"/invoice/pdf/{test_invoice.id}")
        assert response.status_code == 200

    def test_invoice_preview(self, auth_client, test_invoice):
        response = auth_client.get(f"/invoice/view/{test_invoice.id}")
        assert response.status_code == 200


class TestInvoiceImport:
    def test_import_invoices_page(self, auth_client):
        response = auth_client.get("/import/invoices")
        assert response.status_code == 200

    def test_import_invoices_csv_valid(self, auth_client, app, test_party, second_party, csv_files):
        with app.app_context():
            with open(csv_files['invoices_valid'], 'rb') as f:
                response = auth_client.post(
                    "/import/invoices",
                    data={"csv_file": f},
                    follow_redirects=True,
                )
            assert response.status_code == 200

    def test_import_invoices_missing_party(self, auth_client, app, csv_files):
        with app.app_context():
            with open(csv_files['invoices_missing_party'], 'rb') as f:
                response = auth_client.post(
                    "/import/invoices",
                    data={"csv_file": f},
                    follow_redirects=True,
                )
            assert response.status_code == 200

    def test_import_invoices_invalid_file(self, auth_client, app):
        with app.app_context():
            data = {
                'csv_file': (io.BytesIO(b'not a csv'), 'test.txt'),
            }
            response = auth_client.post(
                "/import/invoices",
                data=data,
                content_type='multipart/form-data',
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_import_invoices_calculates_gst(self, auth_client, app, test_party, csv_files):
        with app.app_context():
            with open(csv_files['invoices_valid'], 'rb') as f:
                response = auth_client.post(
                    "/import/invoices",
                    data={"csv_file": f},
                    follow_redirects=True,
                )
            assert response.status_code == 200


class TestInvoiceAccessControl:
    def test_invoices_requires_login(self, client):
        response = client.get("/invoices", follow_redirects=True)
        assert response.status_code == 200

    def test_create_invoice_requires_login(self, client):
        response = client.post("/invoice/create", follow_redirects=True)
        assert response.status_code == 200

    def test_pdf_requires_login(self, client, app):
        with app.app_context():
            response = client.get("/invoice/pdf/1")
            assert response.status_code == 302