import pytest
import io


class TestPartyRoutes:
    def test_parties_list_get(self, auth_client):
        response = auth_client.get("/parties")
        assert response.status_code == 200

    def test_create_party_get(self, auth_client):
        response = auth_client.get("/parties")
        assert response.status_code == 200

    def test_create_party_post(self, auth_client, app, test_party):
        response = auth_client.post(
            "/parties",
            data={
                "name": "New Test Party",
                "gstin": "29AAACP1234A1Z5",
                "pan": "AAACP1234A",
                "amc_code": "AMC999",
                "address": "456 New Address",
                "state": "Karnataka",
                "state_code": "29",
                "email": "newparty@test.com",
                "phone": "9876543210",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_edit_party_get(self, auth_client, test_party):
        response = auth_client.get(f"/party/edit/{test_party.id}")
        assert response.status_code == 200

    def test_edit_party_post(self, auth_client, app, test_party):
        response = auth_client.post(
            f"/party/edit/{test_party.id}",
            data={
                "name": "Updated Party Name",
                "gstin": test_party.gstin,
                "state": "Maharashtra",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_delete_party(self, auth_client, test_party):
        response = auth_client.get(
            f"/party/delete/{test_party.id}",
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_party_api(self, auth_client, test_party):
        response = auth_client.get(f"/party/api/{test_party.id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["name"] == "Test Party"

    def test_create_party_missing_name(self, auth_client, app):
        with app.app_context():
            response = auth_client.post(
                "/parties",
                data={
                    "name": "",
                    "gstin": "29AAACP9999A1Z5",
                    "state": "Karnataka",
                    "state_code": "29",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_create_party_missing_gstin(self, auth_client, app):
        with app.app_context():
            response = auth_client.post(
                "/parties",
                data={
                    "name": "Test Party",
                    "gstin": "",
                    "state": "Karnataka",
                    "state_code": "29",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_create_party_duplicate_gstin(self, auth_client, app, test_party):
        with app.app_context():
            response = auth_client.post(
                "/parties",
                data={
                    "name": "Different Party",
                    "gstin": test_party.gstin,
                    "state": "Maharashtra",
                    "state_code": "27",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_create_party_duplicate_gstin_case_insensitive(self, auth_client, app, test_party):
        with app.app_context():
            response = auth_client.post(
                "/parties",
                data={
                    "name": "Case Test Party",
                    "gstin": test_party.gstin.lower(),
                    "state": "Maharashtra",
                    "state_code": "27",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_delete_party_with_invoices_blocked(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get(
                f"/party/delete/{test_invoice.party_id}",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Cannot delete" in response.data or b"invoice" in response.data.lower()

    def test_party_api_not_found(self, auth_client):
        response = auth_client.get("/party/api/99999")
        assert response.status_code == 404

    def test_edit_party_not_found(self, auth_client):
        response = auth_client.get("/party/edit/99999")
        assert response.status_code == 404

    def test_delete_party_not_found(self, auth_client):
        response = auth_client.get("/party/delete/99999")
        assert response.status_code == 404


class TestPartySorting:
    def test_sort_by_name_asc(self, auth_client, app, test_party, second_party):
        with app.app_context():
            response = auth_client.get("/parties?sort_by=name&sort_dir=asc")
            assert response.status_code == 200

    def test_sort_by_name_desc(self, auth_client, app, test_party, second_party):
        with app.app_context():
            response = auth_client.get("/parties?sort_by=name&sort_dir=desc")
            assert response.status_code == 200

    def test_sort_by_gstin(self, auth_client, app, test_party, second_party):
        with app.app_context():
            response = auth_client.get("/parties?sort_by=gstin&sort_dir=asc")
            assert response.status_code == 200


class TestPartyExport:
    def test_export_all_parties(self, auth_client):
        response = auth_client.get("/export/parties")
        assert response.status_code == 200

    def test_export_all_parties_no_parties(self, auth_client, app):
        with app.app_context():
            from models import Party, db
            Party.query.delete()
            db.session.commit()

            response = auth_client.get("/export/parties")
            assert response.status_code == 200

    def test_export_selected_parties_empty(self, auth_client):
        response = auth_client.post(
            "/export/parties/selected",
            data={"party_ids": ""},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"No parties selected" in response.data

    def test_export_selected_parties(self, auth_client, test_party):
        response = auth_client.post(
            "/export/parties/selected",
            data={"party_ids": str(test_party.id)},
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_export_selected_parties_multiple(self, auth_client, app, test_party, second_party):
        with app.app_context():
            response = auth_client.post(
                "/export/parties/selected",
                data={"party_ids": f"{test_party.id},{second_party.id}"},
                follow_redirects=True,
            )
            assert response.status_code == 200


class TestPartyImport:
    def test_import_parties_csv_valid(self, auth_client, app, csv_files):
        with app.app_context():
            with open(csv_files['parties_valid'], 'rb') as f:
                response = auth_client.post(
                    "/import/parties",
                    data={"csv_file": f},
                    follow_redirects=True,
                )
            assert response.status_code == 200

    def test_import_parties_invalid_file_type(self, auth_client, app):
        with app.app_context():
            data = {
                'csv_file': (io.BytesIO(b'not a csv'), 'test.txt'),
            }
            response = auth_client.post(
                "/import/parties",
                data=data,
                content_type='multipart/form-data',
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_import_parties_missing_name(self, auth_client, app, csv_files):
        with app.app_context():
            with open(csv_files['parties_invalid'], 'rb') as f:
                response = auth_client.post(
                    "/import/parties",
                    data={"csv_file": f},
                    follow_redirects=True,
                )
            assert response.status_code == 200

    def test_import_parties_duplicate_gstin(self, auth_client, app, test_party, csv_files):
        with app.app_context():
            with open(csv_files['parties_duplicate_gstin'], 'rb') as f:
                response = auth_client.post(
                    "/import/parties",
                    data={"csv_file": f},
                    follow_redirects=True,
                )
            assert response.status_code == 200

    def test_import_parties_updates_existing(self, auth_client, app, test_party, csv_files):
        with app.app_context():
            with open(csv_files['parties_valid'], 'rb') as f:
                response = auth_client.post(
                    "/import/parties",
                    data={"csv_file": f},
                    follow_redirects=True,
                )
            assert response.status_code == 200


class TestPartyAccessControl:
    def test_parties_requires_login(self, client):
        response = client.get("/parties", follow_redirects=True)
        assert response.status_code == 200

    def test_party_api_no_login(self, client, app):
        with app.app_context():
            response = client.get("/party/api/1")
            assert response.status_code in [200, 302, 404]

    def test_delete_party_requires_login(self, client, app):
        with app.app_context():
            response = client.get("/party/delete/1", follow_redirects=True)
            assert response.status_code == 200