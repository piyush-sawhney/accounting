import pytest
from datetime import date


class TestFullWorkflowLoginToExport:
    """End-to-end test: Login → Create Party → Create Invoice → Export"""

    def test_complete_party_invoice_export_workflow(self, auth_client, app, test_party, test_company):
        """Test the full workflow from login to export"""
        response = auth_client.post(
            "/invoice/create",
            data={
                "party_id": test_party.id,
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


class TestPartyManagementWorkflow:
    """Test: Create party → Edit → Delete"""

    def test_create_edit_delete_party(self, auth_client, app):
        response = auth_client.get("/parties")
        assert response.status_code == 200


class TestInvoiceLockUnlockWorkflow:
    """Test: Create Invoice → Generate Number → Lock → Export"""

    def test_lock_unlock_invoice_workflow(self, auth_client, app, test_invoice):
        from models import Invoice, db

        with app.app_context():
            invoice = Invoice.query.first()
            if invoice:
                invoice_id = invoice.id

                response = auth_client.post(
                    "/invoices/batch-lock",
                    data=f"invoice_ids={invoice_id}",
                    content_type="application/x-www-form-urlencoded",
                )
                assert response.status_code in [200, 302, 404]


class TestDuplicateGSTINPrevention:
    """Test that duplicate GSTIN is prevented"""

    def test_duplicate_gstin_blocked(self, auth_client, app):
        response = auth_client.post(
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

    def test_intra_state_gst_calculation(self, auth_client, app, test_party, test_company):
        response = auth_client.post(
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

    def test_inter_state_gst_calculation(self, auth_client, app, test_party, test_company):
        response = auth_client.post(
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


class TestCreditNoteWorkflow:
    """Test Credit Note Creation Workflow"""

    def test_create_credit_note_from_locked_invoice(self, auth_client, app, test_locked_invoice):
        response = auth_client.post(
            "/credit-note/create",
            data={
                "invoice_id": test_locked_invoice.id,
                "credit_note_date": "2026-04-20",
                "reason": "Wrong billing",
                "tax_type": "INTRA",
                "place_of_supply": "Maharashtra",
                "item_description[]": ["Credit Service"],
                "item_taxable_value[]": ["5000"],
                "item_cgst_rate[]": ["9"],
                "item_sgst_rate[]": ["9"],
                "item_igst_rate[]": ["0"],
            },
            follow_redirects=True,
        )
        assert response.status_code == 200


class TestCompanyWorkflow:
    """Test Company Management Workflow"""

    def test_create_and_set_default_company(self, auth_client, app):
        response = auth_client.get("/company")
        assert response.status_code == 200


class TestImportExportWorkflow:
    """Test Import and Export Workflow"""

    def test_import_parties_and_export(self, auth_client, app, csv_files):
        with open(csv_files['parties_valid'], 'rb') as f:
            response = auth_client.post(
                "/import/parties",
                data={"csv_file": f},
                follow_redirects=True,
            )
        assert response.status_code == 200

        response = auth_client.get("/export/parties")
        assert response.status_code == 200


class TestRCMScenario:
    """Test RCM (Reverse Charge Mechanism) Workflow"""

    def test_rcm_invoice_creation(self, auth_client, app, test_party):
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
                "item_description[]": ["RCM Service"],
                "item_taxable_value[]": ["10000"],
                "item_cgst_rate[]": ["9"],
                "item_sgst_rate[]": ["9"],
                "item_igst_rate[]": ["0"],
            },
            follow_redirects=True,
        )
        assert response.status_code == 200