import pytest


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


class TestPartyExport:
    def test_export_all_parties(self, auth_client):
        response = auth_client.get("/export/parties")
        assert response.status_code == 200

    def test_export_selected_parties_empty(self, auth_client):
        response = auth_client.post(
            "/export/parties/selected",
            data={"party_ids": ""},
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_export_selected_parties(self, auth_client, test_party):
        response = auth_client.post(
            "/export/parties/selected",
            data={"party_ids": str(test_party.id)},
            follow_redirects=True,
        )
        assert response.status_code == 200