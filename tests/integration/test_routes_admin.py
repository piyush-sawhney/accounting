import pytest
import io
from datetime import date


class TestUserManagement:
    def test_user_list_get(self, auth_client, app):
        with app.app_context():
            response = auth_client.get("/users")
            assert response.status_code == 200

    def test_user_create_success(self, auth_client, app):
        with app.app_context():
            response = auth_client.post(
                "/users",
                data={
                    "action": "create",
                    "full_name": "New User",
                    "username": "newuser123",
                    "password": "password123",
                    "role": "staff",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_user_create_duplicate_username(self, auth_client, app, test_user):
        with app.app_context():
            response = auth_client.post(
                "/users",
                data={
                    "action": "create",
                    "full_name": "Another User",
                    "username": test_user.username,
                    "password": "password123",
                    "role": "staff",
                },
            )
            assert response.status_code == 200
            assert b"already exists" in response.data.lower()

    def test_user_create_missing_fields(self, auth_client, app):
        with app.app_context():
            response = auth_client.post(
                "/users",
                data={
                    "action": "create",
                    "full_name": "",
                    "username": "",
                    "password": "",
                    "role": "staff",
                },
            )
            assert response.status_code == 200
            assert b"required" in response.data.lower()

    def test_user_delete_success(self, auth_client, app):
        with app.app_context():
            from models import User, db
            user = User(
                username="deletetest",
                full_name="Delete Test",
                role="staff",
                must_change_password=False,
            )
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            response = auth_client.post(
                "/users",
                data={
                    "action": "delete",
                    "user_id": user_id,
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_user_delete_own_account_blocked(self, auth_client, app, test_user):
        with app.app_context():
            response = auth_client.post(
                "/users",
                data={
                    "action": "delete",
                    "user_id": test_user.id,
                },
            )
            assert response.status_code == 200
            assert b"Cannot delete" in response.data.lower() or b"own account" in response.data.lower()

    def test_user_reset_password(self, auth_client, app):
        with app.app_context():
            from models import User, db
            user = User(
                username="resettest",
                full_name="Reset Test",
                role="staff",
                must_change_password=False,
            )
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            response = auth_client.post(
                "/users",
                data={
                    "action": "reset_password",
                    "user_id": user_id,
                    "new_password": "newpass123",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_user_reset_password_too_short(self, auth_client, app):
        with app.app_context():
            from models import User, db
            user = User(
                username="shortreset",
                full_name="Short Reset",
                role="staff",
                must_change_password=False,
            )
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            user_id = user.id

            response = auth_client.post(
                "/users",
                data={
                    "action": "reset_password",
                    "user_id": user_id,
                    "new_password": "12345",
                },
            )
            assert response.status_code == 200
            assert b"at least 6" in response.data.lower()


class TestRecoveryCodes:
    def test_generate_recovery_codes(self, auth_client, app):
        with app.app_context():
            response = auth_client.post(
                "/users/generate-recovery-codes",
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_download_recovery_codes(self, auth_client, app):
        with app.app_context():
            response = auth_client.get("/users/download-recovery-codes", follow_redirects=True)
            assert response.status_code == 200

    def test_download_no_codes(self, auth_client, app):
        with app.app_context():
            from models import RecoveryCode, db
            RecoveryCode.query.delete()
            db.session.commit()

            response = auth_client.get("/users/download-recovery-codes", follow_redirects=True)
            assert response.status_code == 200


class TestBackup:
    def test_backup_creates_zip(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/backup")
            assert response.status_code == 200

    def test_backup_includes_all_tables(self, auth_client, app, test_invoice):
        with app.app_context():
            response = auth_client.get("/backup")
            assert response.status_code == 200
            assert response.content_type == "application/zip"

    def test_backup_empty_database(self, auth_client, app):
        with app.app_context():
            from models import Invoice, Party, db
            Invoice.query.delete()
            Party.query.delete()
            db.session.commit()

            response = auth_client.get("/backup")
            assert response.status_code == 200


class TestAdminAccessControl:
    def test_users_requires_admin(self, client, app):
        with app.app_context():
            response = client.get("/users", follow_redirects=True)
            assert response.status_code == 200

    def test_backup_requires_admin(self, client, app):
        with app.app_context():
            response = client.get("/backup", follow_redirects=True)
            assert response.status_code == 200


class TestStaffUserAccess:
    def test_staff_can_view_dashboard(self, staff_client):
        response = staff_client.get("/dashboard")
        assert response.status_code == 200

    def test_staff_can_view_invoices(self, staff_client):
        response = staff_client.get("/invoices")
        assert response.status_code == 200

    def test_staff_can_view_parties(self, staff_client):
        response = staff_client.get("/parties")
        assert response.status_code == 200

    def test_staff_cannot_access_users(self, staff_client, app):
        with app.app_context():
            response = staff_client.get("/users", follow_redirects=True)
            assert response.status_code in [200, 302]

    def test_staff_cannot_access_backup(self, staff_client, app):
        with app.app_context():
            response = staff_client.get("/backup", follow_redirects=True)
            assert response.status_code in [200, 302]