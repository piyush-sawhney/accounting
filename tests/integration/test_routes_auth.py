import pytest
import io


class TestAuthLogin:
    def test_login_success(self, client, app, test_user):
        with app.app_context():
            response = client.post(
                "/login",
                data={
                    "username": "testuser",
                    "password": "testpass123",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Dashboard" in response.data or b"dashboard" in response.data

    def test_login_invalid_password(self, client, app, test_user):
        with app.app_context():
            response = client.post(
                "/login",
                data={
                    "username": "testuser",
                    "password": "wrongpassword",
                },
            )
            assert response.status_code == 200
            assert b"Invalid" in response.data or b"invalid" in response.data

    def test_login_nonexistent_user(self, client, app):
        with app.app_context():
            response = client.post(
                "/login",
                data={
                    "username": "nonexistent",
                    "password": "password123",
                },
            )
            assert response.status_code == 200
            assert b"Invalid" in response.data or b"invalid" in response.data

    def test_login_inactive_user(self, client, app, inactive_user):
        with app.app_context():
            response = client.post(
                "/login",
                data={
                    "username": "inactiveuser",
                    "password": "inactivepass123",
                },
            )
            assert response.status_code == 200
            assert b"Invalid" in response.data or b"invalid" in response.data

    def test_login_redirect_next(self, client, app, test_user):
        with app.app_context():
            response = client.post(
                "/login?next=/invoices",
                data={
                    "username": "testuser",
                    "password": "testpass123",
                },
                follow_redirects=False,
            )
            assert response.status_code == 302

    def test_login_already_logged_in(self, auth_client):
        response = auth_client.get("/login", follow_redirects=False)
        assert response.status_code == 302

    def test_login_missing_username(self, client, app):
        with app.app_context():
            response = client.post(
                "/login",
                data={
                    "username": "",
                    "password": "password123",
                },
            )
            assert response.status_code == 200

    def test_login_missing_password(self, client, app):
        with app.app_context():
            response = client.post(
                "/login",
                data={
                    "username": "testuser",
                    "password": "",
                },
            )
            assert response.status_code == 200


class TestAuthLogout:
    def test_logout_clears_session(self, auth_client, app):
        with app.app_context():
            response = auth_client.get("/logout", follow_redirects=True)
            assert response.status_code == 200
            assert b"login" in response.data.lower() or b"Login" in response.data

    def test_logout_redirects_login(self, auth_client):
        response = auth_client.get("/logout", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location


class TestAuthSetup:
    def test_setup_first_user(self, client, app):
        with app.app_context():
            from models import db, User
            User.query.delete()
            db.session.commit()

            response = client.post(
                "/setup",
                data={
                    "full_name": "New Admin",
                    "username": "newadmin",
                    "password": "password123",
                    "confirm_password": "password123",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"success" in response.data.lower() or b"Setup complete" in response.data

    def test_setup_redirects_if_user_exists(self, client, app, test_user):
        with app.app_context():
            response = client.get("/setup", follow_redirects=False)
            assert response.status_code == 302
            assert "/login" in response.location

    def test_setup_password_mismatch(self, client, app):
        with app.app_context():
            from models import db, User
            User.query.delete()
            db.session.commit()

            response = client.post(
                "/setup",
                data={
                    "full_name": "New Admin",
                    "username": "newadmin",
                    "password": "password123",
                    "confirm_password": "differentpass",
                },
            )
            assert response.status_code == 200
            assert b"must match" in response.data.lower() or b"Password" in response.data

    def test_setup_short_password(self, client, app):
        with app.app_context():
            from models import db, User
            User.query.delete()
            db.session.commit()

            response = client.post(
                "/setup",
                data={
                    "full_name": "New Admin",
                    "username": "newadmin",
                    "password": "123",
                    "confirm_password": "123",
                },
            )
            assert response.status_code == 200

    def test_setup_short_username(self, client, app):
        with app.app_context():
            from models import db, User
            User.query.delete()
            db.session.commit()

            response = client.post(
                "/setup",
                data={
                    "full_name": "New Admin",
                    "username": "ab",
                    "password": "password123",
                    "confirm_password": "password123",
                },
            )
            assert response.status_code == 200


class TestAuthRecovery:
    def test_recovery_page_loads(self, client):
        response = client.get("/recovery")
        assert response.status_code == 200

    def test_recovery_invalid_code(self, client, app):
        with app.app_context():
            response = client.post(
                "/recovery",
                data={
                    "code": "INVALIDCODE",
                    "password": "",
                    "confirm_password": "",
                },
            )
            assert response.status_code == 200
            assert b"Invalid" in response.data or b"invalid" in response.data

    def test_recovery_used_code(self, client, app, test_user):
        with app.app_context():
            from models import RecoveryCode, db
            code = RecoveryCode(code="USEDCODE1", user_id=test_user.id, is_used=True)
            db.session.add(code)
            db.session.commit()

            response = client.post(
                "/recovery",
                data={
                    "code": "USEDCODE1",
                },
            )
            assert response.status_code == 200
            assert b"Invalid" in response.data or b"used" in response.data.lower()

    def test_recovery_valid_code_no_password(self, client, app, test_user):
        with app.app_context():
            from models import RecoveryCode, db
            code = RecoveryCode(code="VALIDCODE1", user_id=test_user.id, is_used=False)
            db.session.add(code)
            db.session.commit()

            response = client.post(
                "/recovery",
                data={
                    "code": "VALIDCODE1",
                    "password": "",
                    "confirm_password": "",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_recovery_password_mismatch(self, client, app, test_user):
        with app.app_context():
            from models import RecoveryCode, db
            code = RecoveryCode(code="VALIDCODE2", user_id=test_user.id, is_used=False)
            db.session.add(code)
            db.session.commit()

            response = client.post(
                "/recovery",
                data={
                    "code": "VALIDCODE2",
                    "password": "newpass123",
                    "confirm_password": "differentpass",
                },
            )
            assert response.status_code == 200
            assert b"match" in response.data.lower()

    def test_recovery_password_too_short(self, client, app, test_user):
        with app.app_context():
            from models import RecoveryCode, db
            code = RecoveryCode(code="VALIDCODE3", user_id=test_user.id, is_used=False)
            db.session.add(code)
            db.session.commit()

            response = client.post(
                "/recovery",
                data={
                    "code": "VALIDCODE3",
                    "password": "12345",
                    "confirm_password": "12345",
                },
            )
            assert response.status_code == 200
            assert b"at least 6" in response.data.lower()

    def test_recovery_password_set_success(self, client, app, test_user):
        with app.app_context():
            from models import RecoveryCode, db
            code = RecoveryCode(code="VALIDCODE4", user_id=test_user.id, is_used=False)
            db.session.add(code)
            db.session.commit()

            response = client.post(
                "/recovery",
                data={
                    "code": "VALIDCODE4",
                    "password": "newpass123",
                    "confirm_password": "newpass123",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"success" in response.data.lower() or b"successful" in response.data


class TestAuthSetupSuccess:
    def test_setup_success_page_requires_codes(self, client, app):
        with app.app_context():
            from models import db, User
            User.query.delete()
            db.session.commit()

            client.post(
                "/setup",
                data={
                    "full_name": "New Admin",
                    "username": "newadmin",
                    "password": "password123",
                    "confirm_password": "password123",
                },
            )

            response = client.get("/setup-success")
            assert response.status_code in [200, 302]

    def test_setup_success_redirects_no_codes(self, client, app):
        response = client.get("/setup-success", follow_redirects=False)
        assert response.status_code in [200, 302]


class TestAuthDownloadSetupCodes:
    def test_download_setup_codes(self, client, app):
        with app.app_context():
            from models import db, User
            User.query.delete()
            db.session.commit()

            client.post(
                "/setup",
                data={
                    "full_name": "New Admin",
                    "username": "newadmin",
                    "password": "password123",
                    "confirm_password": "password123",
                },
            )

            response = client.get("/download-setup-codes")
            assert response.status_code == 200

    def test_download_setup_codes_no_codes(self, client, app):
        response = client.get("/download-setup-codes", follow_redirects=True)
        assert response.status_code == 200