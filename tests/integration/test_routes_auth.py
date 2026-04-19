import pytest


class TestAuthRoutes:
    def test_index_page_redirects_without_login(self, client):
        response = client.get("/")
        assert response.status_code == 302

    def test_logout(self, client, test_user):
        with client.session_transaction() as sess:
            sess["user_id"] = test_user.id
            sess["username"] = test_user.username

        response = client.get("/logout", follow_redirects=True)
        assert response.status_code == 200


class TestSetupRoutes:
    def test_setup_page_redirects_when_users_exist(self, client, test_user):
        response = client.get("/setup", follow_redirects=True)
        assert response.status_code == 200


class TestRecoveryRoutes:
    def test_recovery_page_get(self, client):
        response = client.get("/recovery")
        assert response.status_code == 200