import pytest


class TestInvoiceRoutes:
    def test_invoices_list_get(self, auth_client):
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

    def test_view_invoice(self, auth_client, test_invoice):
        response = auth_client.get(f"/invoice/{test_invoice.id}")
        assert response.status_code == 200

    def test_delete_invoice(self, auth_client, test_invoice):
        response = auth_client.get(
            f"/invoice/delete/{test_invoice.id}",
            follow_redirects=True,
        )
        assert response.status_code == 200


class TestInvoiceBatch:
    def test_generate_invoice_numbers(self, auth_client, test_invoice):
        response = auth_client.post(
            "/invoice/generate-numbers",
            data=f'invoice_ids={test_invoice.id}',
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code in [200, 302]

    def test_batch_lock(self, auth_client, test_invoice):
        response = auth_client.post(
            "/invoice/batch-lock",
            data=f'invoice_ids={test_invoice.id}',
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code in [200, 302]

    def test_batch_unlock(self, auth_client, test_invoice):
        response = auth_client.post(
            "/invoice/batch-unlock",
            data=f'invoice_ids={test_invoice.id}',
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code in [200, 302]

    def test_batch_delete(self, auth_client, test_invoice):
        response = auth_client.post(
            "/invoice/batch-delete",
            data=f'invoice_ids={test_invoice.id}',
            content_type="application/x-www-form-urlencoded",
            follow_redirects=True,
        )
        assert response.status_code == 200


class TestInvoiceExport:
    def test_batch_export_csv(self, auth_client, test_invoice):
        response = auth_client.post(
            "/batch/export",
            data=f'invoice_ids={test_invoice.id}',
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code in [200, 302]

    def test_batch_export_excel(self, auth_client, test_invoice):
        response = auth_client.post(
            "/batch/export/excel",
            data=f'invoice_ids={test_invoice.id}',
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code in [200, 302]


class TestInvoicePDF:
    def test_invoice_pdf(self, auth_client, test_invoice):
        response = auth_client.get(f"/invoice/pdf/{test_invoice.id}")
        assert response.status_code == 200


class TestInvoiceSync:
    def test_batch_sync(self, auth_client, test_invoice):
        response = auth_client.post(
            "/invoice/batch-sync",
            data=f'invoice_ids={test_invoice.id}',
            content_type="application/x-www-form-urlencoded",
            follow_redirects=True,
        )
        assert response.status_code == 200