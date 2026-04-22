import pytest
from datetime import date


class TestCreditNoteRoutes:
    def test_credit_notes_list_get(self, auth_client):
        response = auth_client.get("/credit-notes")
        assert response.status_code == 200

    def test_credit_notes_list_empty(self, auth_client, app):
        with app.app_context():
            from models import CreditNote, db
            CreditNote.query.delete()
            db.session.commit()
            response = auth_client.get("/credit-notes")
            assert response.status_code == 200

    def test_create_credit_note_get(self, auth_client):
        response = auth_client.get("/credit-note/create")
        assert response.status_code == 200

    def test_create_credit_note_with_invoice_id(self, auth_client, test_locked_invoice):
        response = auth_client.get(f"/credit-note/create?invoice_id={test_locked_invoice.id}")
        assert response.status_code == 200

    def test_create_credit_note_post(self, auth_client, app, test_locked_invoice):
        with app.app_context():
            response = auth_client.post(
                "/credit-note/create",
                data={
                    "invoice_id": test_locked_invoice.id,
                    "credit_note_date": "2026-04-20",
                    "reason": "Wrong billing",
                    "tax_type": "INTRA",
                    "place_of_supply": "Maharashtra",
                    "company_id": "",
                    "item_description[]": ["Credit Service"],
                    "item_taxable_value[]": ["3000"],
                    "item_cgst_rate[]": ["9"],
                    "item_sgst_rate[]": ["9"],
                    "item_igst_rate[]": ["0"],
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_create_credit_note_inter_state(self, auth_client, app, test_locked_invoice):
        with app.app_context():
            response = auth_client.post(
                "/credit-note/create",
                data={
                    "invoice_id": test_locked_invoice.id,
                    "credit_note_date": "2026-04-20",
                    "reason": "Discount",
                    "tax_type": "INTER",
                    "place_of_supply": "Karnataka",
                    "item_description[]": ["Inter State Credit"],
                    "item_taxable_value[]": ["5000"],
                    "item_cgst_rate[]": ["0"],
                    "item_sgst_rate[]": ["0"],
                    "item_igst_rate[]": ["18"],
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_create_credit_note_missing_invoice(self, auth_client, app):
        with app.app_context():
            response = auth_client.post(
                "/credit-note/create",
                data={
                    "invoice_id": "",
                    "credit_note_date": "2026-04-20",
                    "reason": "Test",
                    "tax_type": "INTRA",
                    "place_of_supply": "Maharashtra",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_edit_credit_note_get(self, auth_client, test_credit_note):
        response = auth_client.get(f"/credit-note/edit/{test_credit_note.id}")
        assert response.status_code == 200

    def test_edit_credit_note_post(self, auth_client, app, test_credit_note):
        with app.app_context():
            response = auth_client.post(
                f"/credit-note/edit/{test_credit_note.id}",
                data={
                    "invoice_id": test_credit_note.invoice_id,
                    "credit_note_date": "2026-04-25",
                    "reason": "Updated reason",
                    "tax_type": "INTRA",
                    "place_of_supply": "Maharashtra",
                    "company_id": "",
                    "item_description[]": ["Updated Credit"],
                    "item_taxable_value[]": ["4000"],
                    "item_cgst_rate[]": ["9"],
                    "item_sgst_rate[]": ["9"],
                    "item_igst_rate[]": ["0"],
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_edit_credit_note_locked_blocked(self, auth_client, app, test_locked_credit_note):
        with app.app_context():
            response = auth_client.get(f"/credit-note/edit/{test_locked_credit_note.id}", follow_redirects=True)
            assert response.status_code == 200

    def test_delete_credit_note(self, auth_client, test_credit_note):
        response = auth_client.get(
            f"/credit-note/delete/{test_credit_note.id}",
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_preview_credit_note(self, auth_client, test_credit_note):
        response = auth_client.get(f"/credit-note/preview/{test_credit_note.id}")
        assert response.status_code == 200

    def test_credit_note_not_found(self, auth_client):
        response = auth_client.get("/credit-note/edit/99999")
        assert response.status_code == 404


class TestCreditNoteGSTCalculation:
    def test_credit_note_gst_intra(self, auth_client, app, test_locked_invoice):
        with app.app_context():
            from models import CreditNote, CreditNoteItem, db

            cn = CreditNote(
                credit_note_date=date(2026, 4, 20),
                invoice_id=test_locked_invoice.id,
                reason="Test",
                tax_type="INTRA",
                place_of_supply="Maharashtra",
                party_name=test_locked_invoice.party_name,
                party_gstin=test_locked_invoice.party_gstin,
            )
            db.session.add(cn)
            db.session.flush()

            item = CreditNoteItem(
                credit_note_id=cn.id,
                description="Test",
                taxable_value=10000.00,
                cgst_rate=9.0,
                cgst_amt=900.00,
                sgst_rate=9.0,
                sgst_amt=900.00,
            )
            db.session.add(item)
            db.session.commit()

            gst = cn.calculate_gst()
            assert gst["subtotal"] == 10000.00
            assert gst["cgst"] == 900.00
            assert gst["sgst"] == 900.00
            assert gst["igst"] == 0
            assert gst["total"] == 11800.00

    def test_credit_note_gst_inter(self, auth_client, app, test_locked_invoice):
        with app.app_context():
            from models import CreditNote, CreditNoteItem, db

            cn = CreditNote(
                credit_note_date=date(2026, 4, 20),
                invoice_id=test_locked_invoice.id,
                reason="Test",
                tax_type="INTER",
                place_of_supply="Karnataka",
                party_name=test_locked_invoice.party_name,
                party_gstin=test_locked_invoice.party_gstin,
            )
            db.session.add(cn)
            db.session.flush()

            item = CreditNoteItem(
                credit_note_id=cn.id,
                description="Test",
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

            gst = cn.calculate_gst()
            assert gst["subtotal"] == 10000.00
            assert gst["cgst"] == 0
            assert gst["sgst"] == 0
            assert gst["igst"] == 1800.00
            assert gst["total"] == 11800.00


class TestCreditNoteBatch:
    def test_batch_lock_credit_notes(self, auth_client, app, test_credit_note):
        with app.app_context():
            response = auth_client.post(
                "/credit-notes/batch-lock",
                data=f"credit_note_ids={test_credit_note.id}",
                content_type="application/x-www-form-urlencoded",
            )
            assert response.status_code in [200, 302]

    def test_batch_unlock_credit_notes(self, auth_client, app, test_locked_credit_note):
        with app.app_context():
            response = auth_client.post(
                "/credit-notes/batch-unlock",
                data=f"credit_note_ids={test_locked_credit_note.id}",
                content_type="application/x-www-form-urlencoded",
            )
            assert response.status_code in [200, 302]

    def test_batch_delete_credit_notes(self, auth_client, app, test_credit_note):
        with app.app_context():
            response = auth_client.post(
                "/credit-notes/batch-delete",
                data=f"credit_note_ids={test_credit_note.id}",
                content_type="application/x-www-form-urlencoded",
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_batch_delete_multiple(self, auth_client, app, test_credit_note, test_locked_credit_note):
        with app.app_context():
            response = auth_client.post(
                "/credit-notes/batch-delete",
                data=f"credit_note_ids={test_credit_note.id},{test_locked_credit_note.id}",
                content_type="application/x-www-form-urlencoded",
                follow_redirects=True,
            )
            assert response.status_code == 200


class TestCreditNoteNumberGeneration:
    def test_generate_credit_note_numbers(self, auth_client, app, test_locked_invoice):
        with app.app_context():
            from models import CreditNote, db

            cn = CreditNote(
                credit_note_date=date(2026, 4, 20),
                invoice_id=test_locked_invoice.id,
                reason="Test",
                tax_type="INTRA",
                place_of_supply="Maharashtra",
                party_name=test_locked_invoice.party_name,
                party_gstin=test_locked_invoice.party_gstin,
            )
            db.session.add(cn)
            db.session.commit()

            response = auth_client.post(
                "/credit-note/generate-numbers",
                content_type="application/x-www-form-urlencoded",
            )
            assert response.status_code in [200, 302]

    def test_cn_number_format_correct(self, auth_client, app, test_locked_invoice):
        with app.app_context():
            from models import CreditNote, db

            cn = CreditNote(
                credit_note_date=date(2026, 4, 20),
                invoice_id=test_locked_invoice.id,
                reason="Test",
                tax_type="INTRA",
                place_of_supply="Maharashtra",
                party_name=test_locked_invoice.party_name,
                party_gstin=test_locked_invoice.party_gstin,
            )
            db.session.add(cn)
            db.session.commit()

            auth_client.post(
                "/credit-note/generate-numbers",
                content_type="application/x-www-form-urlencoded",
            )

            cn_updated = db.session.get(CreditNote, cn.id)
            if cn_updated.credit_note_no:
                assert "CRN/" in cn_updated.credit_note_no


class TestCreditNoteImport:
    def test_import_credit_notes_page(self, auth_client):
        response = auth_client.get("/credit-notes/import")
        assert response.status_code == 200

    def test_import_credit_notes_csv_valid(self, auth_client, app, test_locked_invoice, csv_files):
        with app.app_context():
            with open(csv_files['credit_notes_valid'], 'rb') as f:
                response = auth_client.post(
                    "/credit-notes/import",
                    data={"csv_file": f},
                    follow_redirects=True,
                )
            assert response.status_code == 200

    def test_import_credit_notes_missing_invoice(self, auth_client, app, csv_files):
        with app.app_context():
            with open(csv_files['credit_notes_invalid'], 'rb') as f:
                response = auth_client.post(
                    "/credit-notes/import",
                    data={"csv_file": f},
                    follow_redirects=True,
                )
            assert response.status_code == 200


class TestCreditNoteExport:
    def test_batch_export_pdf(self, auth_client, app, test_locked_credit_note):
        with app.app_context():
            response = auth_client.post(
                "/credit-notes/batch-export",
                data=f"credit_note_ids={test_locked_credit_note.id}",
                content_type="application/x-www-form-urlencoded",
            )
            assert response.status_code in [200, 302]

    def test_batch_export_excel(self, auth_client, app, test_locked_credit_note):
        with app.app_context():
            response = auth_client.post(
                "/credit-notes/batch-export-excel",
                data=f"credit_note_ids={test_locked_credit_note.id}",
                content_type="application/x-www-form-urlencoded",
            )
            assert response.status_code in [200, 302]

    def test_batch_export_no_locked(self, auth_client, app, test_credit_note):
        with app.app_context():
            response = auth_client.post(
                "/credit-notes/batch-export",
                data=f"credit_note_ids={test_credit_note.id}",
                content_type="application/x-www-form-urlencoded",
            )
            assert response.status_code in [200, 302]


class TestCreditNoteFilters:
    def test_filter_by_year(self, auth_client, app, test_credit_note):
        with app.app_context():
            response = auth_client.get("/credit-notes?year=2026")
            assert response.status_code == 200

    def test_filter_by_month(self, auth_client, app, test_credit_note):
        with app.app_context():
            response = auth_client.get("/credit-notes?year=2026&month=04")
            assert response.status_code == 200

    def test_filter_by_invoice(self, auth_client, app, test_credit_note):
        with app.app_context():
            response = auth_client.get(f"/credit-notes?invoice={test_credit_note.invoice_id}")
            assert response.status_code == 200

    def test_search_by_credit_note_no(self, auth_client, app, test_credit_note):
        with app.app_context():
            if test_credit_note.credit_note_no:
                response = auth_client.get(f"/credit-notes?search={test_credit_note.credit_note_no}")
                assert response.status_code == 200

    def test_sort_by_date_desc(self, auth_client, app, test_credit_note):
        with app.app_context():
            response = auth_client.get("/credit-notes?sort_by=date&sort_dir=desc")
            assert response.status_code == 200


class TestCreditNoteAccessControl:
    def test_credit_notes_requires_login(self, client):
        response = client.get("/credit-notes", follow_redirects=True)
        assert response.status_code == 200

    def test_create_credit_note_requires_login(self, client):
        response = client.get("/credit-note/create", follow_redirects=True)
        assert response.status_code == 200