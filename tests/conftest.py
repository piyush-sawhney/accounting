import os
import sys
import pytest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")


@pytest.fixture(scope="function")
def app():
    import forms
    from app import app as flask_app
    from models import db

    flask_app.config["TESTING"] = True
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test.db"
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["SERVER_NAME"] = None

    with flask_app.app_context():
        forms  # force load
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


@pytest.fixture
def test_user(app):
    from models import User, db

    user = User(
        username="testuser",
        full_name="Test User",
        role="admin",
        must_change_password=False,
        is_active=True,
    )
    user.set_password("testpass123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def test_party(app):
    from models import Party, db

    party = Party(
        name="Test Party",
        gstin="27AAACM1234A1Z5",
        pan="AAACM1234A",
        amc_code="AMC001",
        address="123 Test Address",
        state="Maharashtra",
        state_code="27",
        email="test@party.com",
        phone="9876543210",
    )
    db.session.add(party)
    db.session.commit()
    return party


@pytest.fixture
def test_invoice(app, test_party):
    from models import Invoice, InvoiceItem, db

    invoice = Invoice(
        invoice_no="INV/001",
        invoice_date=date(2026, 4, 1),
        party_id=test_party.id,
        tax_type="INTRA",
        place_of_supply="Maharashtra",
        sac_hsn_code="9971",
        locked=False,
        party_name=test_party.name,
        party_gstin=test_party.gstin,
    )
    db.session.add(invoice)
    db.session.flush()

    item = InvoiceItem(
        invoice_id=invoice.id,
        description="Test Service",
        taxable_value=10000.00,
        cgst_rate=9.0,
        cgst_amt=900.00,
        sgst_rate=9.0,
        sgst_amt=900.00,
        igst_rate=0,
        igst_amt=0,
    )
    db.session.add(item)
    db.session.commit()
    return invoice


@pytest.fixture
def auth_client(client, test_user):
    with client.session_transaction() as sess:
        sess["user_id"] = test_user.id
        sess["username"] = test_user.username
        sess["role"] = test_user.role
    return client