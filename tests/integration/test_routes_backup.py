import pytest
import zipfile
import io
import csv
from datetime import date


class TestBackupRoute:
    def test_backup_requires_admin(self, client):
        response = client.get("/backup")
        assert response.status_code == 302

    def test_backup_requires_login(self, client):
        response = client.get("/backup", follow_redirects=True)
        assert b"Please log in" in response.data or b"login" in response.data.lower()

    def test_backup_requires_admin_role(self, client, test_user):
        test_user.role = "staff"
        from models import db
        db.session.commit()

        with client.session_transaction() as sess:
            sess["user_id"] = test_user.id
            sess["username"] = test_user.username
            sess["role"] = "staff"

        response = client.get("/backup")
        assert response.status_code == 302

    def test_backup_as_admin(self, auth_client):
        response = auth_client.get("/backup")
        assert response.status_code == 200
        assert response.content_type == "application/zip"

    def test_backup_contains_parties_csv(self, auth_client, test_party):
        response = auth_client.get("/backup")
        assert response.status_code == 200

        zip_data = io.BytesIO(response.data)
        with zipfile.ZipFile(zip_data, "r") as zf:
            assert "parties.csv" in zf.namelist()

            with zf.open("parties.csv") as f:
                reader = csv.DictReader(io.StringIO(f.read().decode("utf-8")))
                rows = list(reader)
                assert len(rows) == 1
                assert rows[0]["gstin"] == test_party.gstin
                assert rows[0]["name"] == test_party.name

    def test_backup_contains_invoices_csv(self, auth_client, test_invoice):
        response = auth_client.get("/backup")
        assert response.status_code == 200

        zip_data = io.BytesIO(response.data)
        with zipfile.ZipFile(zip_data, "r") as zf:
            assert "invoices.csv" in zf.namelist()

            with zf.open("invoices.csv") as f:
                reader = csv.DictReader(io.StringIO(f.read().decode("utf-8")))
                rows = list(reader)
                assert len(rows) >= 1

    def test_backup_contains_credit_notes_csv(self, auth_client, test_invoice):
        from models import CreditNote, CreditNoteItem, db

        cn = CreditNote(
            credit_note_no="CN/001",
            credit_note_date=date(2026, 4, 1),
            invoice_id=test_invoice.id,
            reason="Test Reason",
            tax_type="INTRA",
            place_of_supply="Maharashtra",
            party_name=test_invoice.party_name,
            party_gstin=test_invoice.party_gstin,
        )
        db.session.add(cn)
        db.session.flush()

        item = CreditNoteItem(
            credit_note_id=cn.id,
            description="Test Service",
            taxable_value=5000.00,
            cgst_rate=9.0,
            cgst_amt=450.00,
            sgst_rate=9.0,
            sgst_amt=450.00,
            igst_rate=0,
            igst_amt=0,
        )
        db.session.add(item)
        db.session.commit()

        response = auth_client.get("/backup")
        assert response.status_code == 200

        zip_data = io.BytesIO(response.data)
        with zipfile.ZipFile(zip_data, "r") as zf:
            assert "credit_notes.csv" in zf.namelist()

    def test_backup_contains_users_csv(self, auth_client, test_user):
        response = auth_client.get("/backup")
        assert response.status_code == 200

        zip_data = io.BytesIO(response.data)
        with zipfile.ZipFile(zip_data, "r") as zf:
            assert "users.csv" in zf.namelist()

            with zf.open("users.csv") as f:
                reader = csv.DictReader(io.StringIO(f.read().decode("utf-8")))
                rows = list(reader)
                assert len(rows) >= 1

    def test_backup_contains_settings_csv(self, auth_client):
        response = auth_client.get("/backup")
        assert response.status_code == 200

        zip_data = io.BytesIO(response.data)
        with zipfile.ZipFile(zip_data, "r") as zf:
            assert "settings.csv" in zf.namelist()

    def test_backup_contains_manifest(self, auth_client):
        response = auth_client.get("/backup")
        assert response.status_code == 200

        zip_data = io.BytesIO(response.data)
        with zipfile.ZipFile(zip_data, "r") as zf:
            assert "manifest.txt" in zf.namelist()

            with zf.open("manifest.txt") as f:
                content = f.read().decode("utf-8")
                assert "Backup created:" in content

    def test_backup_filename_has_timestamp(self, auth_client):
        response = auth_client.get("/backup")
        assert response.status_code == 200

        from datetime import datetime
        expected_prefix = "gst_backup_"
        expected_date = datetime.now().strftime("%Y%m%d")

        assert expected_prefix in response.headers.get("Content-Disposition", "")
        assert expected_date in response.headers.get("Content-Disposition", "")

    def test_backup_empty_database(self, auth_client):
        response = auth_client.get("/backup")
        assert response.status_code == 200

        zip_data = io.BytesIO(response.data)
        with zipfile.ZipFile(zip_data, "r") as zf:
            with zf.open("parties.csv") as f:
                reader = csv.DictReader(io.StringIO(f.read().decode("utf-8")))
                rows = list(reader)
                assert len(rows) == 0

            with zf.open("invoices.csv") as f:
                reader = csv.DictReader(io.StringIO(f.read().decode("utf-8")))
                rows = list(reader)
                assert len(rows) == 0


class TestBackupImportCompatibility:
    def test_parties_csv_format_for_import(self, auth_client, test_party):
        response = auth_client.get("/backup")
        zip_data = io.BytesIO(response.data)

        with zipfile.ZipFile(zip_data, "r") as zf:
            with zf.open("parties.csv") as f:
                reader = csv.DictReader(io.StringIO(f.read().decode("utf-8")))
                headers = reader.fieldnames
                assert "gstin" in headers
                assert "name" in headers
                assert "pan" in headers
                assert "amc_code" in headers
                assert "address" in headers
                assert "state" in headers
                assert "state_code" in headers

    def test_invoices_csv_format_for_import(self, auth_client, test_invoice, test_party):
        response = auth_client.get("/backup")
        zip_data = io.BytesIO(response.data)

        with zipfile.ZipFile(zip_data, "r") as zf:
            with zf.open("invoices.csv") as f:
                reader = csv.DictReader(io.StringIO(f.read().decode("utf-8")))
                headers = reader.fieldnames
                assert "invoice_no" in headers
                assert "invoice_date" in headers
                assert "party_gstin" in headers
                assert "description" in headers
                assert "taxable_value" in headers
                assert "tax_type" in headers
                assert "cgst_rate" in headers
                assert "sgst_rate" in headers
                assert "igst_rate" in headers
                assert "place_of_supply" in headers


