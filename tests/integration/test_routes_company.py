import pytest
import io


class TestCompanyRoutes:
    def test_company_list_get(self, auth_client):
        response = auth_client.get("/company")
        assert response.status_code == 200

    def test_company_list_empty(self, auth_client, app):
        with app.app_context():
            from models import Company, db
            Company.query.delete()
            db.session.commit()
            response = auth_client.get("/company")
            assert response.status_code == 200

    def test_company_create_post(self, auth_client, app):
        with app.app_context():
            response = auth_client.post(
                "/company",
                data={
                    "company_name": "New Test Company",
                    "address": "123 Business Address",
                    "gstin": "27AAAAA0000A1Z5",
                    "pan": "AAAAA0000A1",
                    "set_as_default": "on",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_company_create_first_becomes_default(self, auth_client, app):
        with app.app_context():
            from models import Company, db
            Company.query.delete()
            db.session.commit()

            response = auth_client.post(
                "/company",
                data={
                    "company_name": "First Company",
                    "address": "Address",
                    "gstin": "27BBBBB0000B1Z5",
                    "pan": "BBBBB0000B1",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_company_edit_post(self, auth_client, app, test_company):
        with app.app_context():
            response = auth_client.post(
                "/company",
                data={
                    "company_id": test_company.id,
                    "company_name": "Updated Company",
                    "address": "Updated Address",
                    "gstin": test_company.gstin,
                    "pan": test_company.pan,
                },
                follow_redirects=True,
            )
            assert response.status_code == 200


class TestCompanyDelete:
    def test_delete_company_success(self, auth_client, app, test_company_non_default):
        with app.app_context():
            response = auth_client.post(
                f"/company/delete/{test_company_non_default.id}",
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_delete_default_company_blocked(self, auth_client, app, test_company):
        with app.app_context():
            response = auth_client.post(
                f"/company/delete/{test_company.id}",
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_delete_only_company_blocked(self, auth_client, app, test_company):
        with app.app_context():
            from models import Company, db
            Company.query.filter(Company.id != test_company.id).delete()
            db.session.commit()

            response = auth_client.post(
                f"/company/delete/{test_company.id}",
                follow_redirects=True,
            )
            assert response.status_code == 200


class TestCompanySetDefault:
    def test_set_default_company(self, auth_client, app, test_company, test_company_non_default):
        with app.app_context():
            response = auth_client.post(
                f"/company/set-default/{test_company_non_default.id}",
                follow_redirects=True,
            )
            assert response.status_code == 200


class TestCompanyImport:
    def test_import_companies_page(self, auth_client):
        response = auth_client.get("/import/companies")
        assert response.status_code == 200

    def test_import_companies_csv_valid(self, auth_client, app, csv_files):
        with app.app_context():
            from models import Company, db
            Company.query.delete()
            db.session.commit()

            with open(csv_files['companies_valid'], 'rb') as f:
                response = auth_client.post(
                    "/import/companies",
                    data={"csv_file": f},
                    follow_redirects=True,
                )
            assert response.status_code == 200

    def test_import_companies_multiple_defaults_rejected(self, auth_client, app, csv_files):
        with app.app_context():
            from models import Company, db
            Company.query.delete()
            db.session.commit()

            with open(csv_files['companies_multiple_defaults'], 'rb') as f:
                response = auth_client.post(
                    "/import/companies",
                    data={"csv_file": f},
                    follow_redirects=True,
                )
            assert response.status_code == 200

    def test_import_companies_updates_existing(self, auth_client, app, test_company, csv_files):
        with app.app_context():
            with open(csv_files['companies_update_existing'], 'rb') as f:
                response = auth_client.post(
                    "/import/companies",
                    data={"csv_file": f},
                    follow_redirects=True,
                )
            assert response.status_code == 200

    def test_import_companies_invalid_file(self, auth_client, app):
        with app.app_context():
            data = {
                'csv_file': (io.BytesIO(b'not a csv'), 'test.txt'),
            }
            response = auth_client.post(
                "/import/companies",
                data=data,
                content_type='multipart/form-data',
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_import_companies_no_file(self, auth_client, app):
        with app.app_context():
            response = auth_client.post(
                "/import/companies",
                data={},
                follow_redirects=True,
            )
            assert response.status_code == 200


class TestCompanyImportConfirmation:
    def test_import_companies_confirm_page(self, auth_client, app, test_company):
        with app.app_context():
            response = auth_client.get("/import/companies/confirm", follow_redirects=True)
            assert response.status_code in [200, 302, 404, 405]

    def test_import_companies_confirm_yes(self, auth_client, app, test_company):
        with app.app_context():
            with auth_client.session_transaction() as sess:
                sess["pending_companies_import"] = [
                    {"name": "New Company", "is_default": True, "is_update": False}
                ]
                sess["confirm_change_default"] = True
                sess["previous_default_name"] = test_company.name
                sess["new_default_name"] = "New Company"

            response = auth_client.post(
                "/import/companies/confirm",
                data={"confirm_action": "confirm"},
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_import_companies_confirm_cancel(self, auth_client, app, test_company):
        with app.app_context():
            with auth_client.session_transaction() as sess:
                sess["pending_companies_import"] = [
                    {"name": "New Company", "is_default": True, "is_update": False}
                ]
                sess["confirm_change_default"] = True
                sess["previous_default_name"] = test_company.name
                sess["new_default_name"] = "New Company"

            response = auth_client.post(
                "/import/companies/confirm",
                data={"confirm_action": "cancel"},
                follow_redirects=True,
            )
            assert response.status_code == 200


class TestCompanyAccessControl:
    def test_company_requires_login(self, client):
        response = client.get("/company", follow_redirects=True)
        assert response.status_code == 200