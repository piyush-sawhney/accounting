import os
import sys
import pytest
from datetime import date
from unittest.mock import patch
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ["DATABASE_URL"] = "sqlite:///test_fixture.db"


@pytest.fixture(scope="function", autouse=True)
def mock_pdfkit():
    """Mock pdfkit to avoid external dependency issues"""
    with patch('pdfkit.from_string', return_value=b'fake_pdf_content'):
        yield


@pytest.fixture(scope="function")
def app():
    import forms
    from app import app as flask_app
    from models import db

    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    flask_app.config["TESTING"] = True
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    flask_app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "poolclass": None,
        "connect_args": {"check_same_thread": False}
    }
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["SERVER_NAME"] = None
    flask_app.config["SECRET_KEY"] = "test-secret-key"
    flask_app.config["SESSION_COOKIE_NAME"] = "test_session"

    with flask_app.app_context():
        db.create_all()
        forms
        yield flask_app
        db.session.remove()
        try:
            db.drop_all()
        except:
            pass
        try:
            os.close(db_fd)
            os.unlink(db_path)
        except:
            pass


@pytest.fixture(scope="function")
def client(app):
    return app.test_client(use_cookies=True)


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
def auth_client(client, test_user, test_company, app):
    """Create authenticated test client with user session"""
    with app.test_request_context():
        with client.session_transaction() as sess:
            sess["user_id"] = test_user.id
            sess["username"] = test_user.username
            sess["role"] = test_user.role
    return client


@pytest.fixture
def test_company(app):
    from models import Company, db

    company = Company(
        name="Test Company",
        address="123 Business Park",
        gstin="27AAAAA0000A1Z5",
        pan="AAAAA0000A1",
        is_default=True,
    )
    db.session.add(company)
    db.session.commit()
    return company


@pytest.fixture
def test_company_non_default(app):
    from models import Company, db

    company = Company(
        name="Second Company",
        address="456 Tech Hub",
        gstin="29BBBBB1111B2Z5",
        pan="BBBBB1111B2",
        is_default=False,
    )
    db.session.add(company)
    db.session.commit()
    return company


@pytest.fixture
def test_locked_invoice(app, test_party, test_company):
    from models import Invoice, InvoiceItem, db

    invoice = Invoice(
        invoice_no="INV/LOCKED/001",
        invoice_date=date(2026, 4, 10),
        party_id=test_party.id,
        tax_type="INTRA",
        place_of_supply="Maharashtra",
        sac_hsn_code="9971",
        locked=True,
        party_name=test_party.name,
        party_gstin=test_party.gstin,
        party_address=test_party.address,
        party_pan=test_party.pan,
        party_state=test_party.state,
        party_state_code=test_party.state_code,
        company_name=test_company.name,
        company_address=test_company.address,
        company_gstin=test_company.gstin,
        company_pan=test_company.pan,
    )
    db.session.add(invoice)
    db.session.flush()

    item = InvoiceItem(
        invoice_id=invoice.id,
        description="Locked Service",
        taxable_value=15000.00,
        cgst_rate=9.0,
        cgst_amt=1350.00,
        sgst_rate=9.0,
        sgst_amt=1350.00,
        igst_rate=0,
        igst_amt=0,
    )
    db.session.add(item)
    db.session.commit()
    return invoice


@pytest.fixture
def test_invoice_inter_state(app, test_party):
    from models import Invoice, InvoiceItem, db

    invoice = Invoice(
        invoice_no="INV/INTER/001",
        invoice_date=date(2026, 4, 5),
        party_id=test_party.id,
        tax_type="INTER",
        place_of_supply="Karnataka",
        sac_hsn_code="9971",
        locked=False,
        party_name=test_party.name,
        party_gstin=test_party.gstin,
    )
    db.session.add(invoice)
    db.session.flush()

    item = InvoiceItem(
        invoice_id=invoice.id,
        description="Inter State Service",
        taxable_value=20000.00,
        cgst_rate=0,
        cgst_amt=0,
        sgst_rate=0,
        sgst_amt=0,
        igst_rate=18.0,
        igst_amt=3600.00,
    )
    db.session.add(item)
    db.session.commit()
    return invoice


@pytest.fixture
def test_credit_note(app, test_locked_invoice):
    from models import CreditNote, CreditNoteItem, db

    credit_note = CreditNote(
        credit_note_no="CN/001",
        credit_note_date=date(2026, 4, 15),
        invoice_id=test_locked_invoice.id,
        reason="Wrong billing",
        tax_type="INTRA",
        place_of_supply="Maharashtra",
        locked=False,
        party_name=test_locked_invoice.party_name,
        party_gstin=test_locked_invoice.party_gstin,
        party_address=test_locked_invoice.party_address,
        party_pan=test_locked_invoice.party_pan,
        party_state=test_locked_invoice.party_state,
        party_state_code=test_locked_invoice.party_state_code,
        company_name=test_locked_invoice.company_name,
        company_address=test_locked_invoice.company_address,
        company_gstin=test_locked_invoice.company_gstin,
        company_pan=test_locked_invoice.company_pan,
    )
    db.session.add(credit_note)
    db.session.flush()

    item = CreditNoteItem(
        credit_note_id=credit_note.id,
        description="Credit for Service",
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
    return credit_note


@pytest.fixture
def test_locked_credit_note(app, test_locked_invoice):
    from models import CreditNote, CreditNoteItem, db

    credit_note = CreditNote(
        credit_note_no="CN/LOCKED/001",
        credit_note_date=date(2026, 4, 16),
        invoice_id=test_locked_invoice.id,
        reason="Discount adjustment",
        tax_type="INTRA",
        place_of_supply="Maharashtra",
        locked=True,
        party_name=test_locked_invoice.party_name,
        party_gstin=test_locked_invoice.party_gstin,
        party_address=test_locked_invoice.party_address,
        party_pan=test_locked_invoice.party_pan,
        party_state=test_locked_invoice.party_state,
        party_state_code=test_locked_invoice.party_state_code,
        company_name=test_locked_invoice.company_name,
        company_address=test_locked_invoice.company_address,
        company_gstin=test_locked_invoice.company_gstin,
        company_pan=test_locked_invoice.company_pan,
    )
    db.session.add(credit_note)
    db.session.flush()

    item = CreditNoteItem(
        credit_note_id=credit_note.id,
        description="Discount credit",
        taxable_value=2000.00,
        cgst_rate=9.0,
        cgst_amt=180.00,
        sgst_rate=9.0,
        sgst_amt=180.00,
        igst_rate=0,
        igst_amt=0,
    )
    db.session.add(item)
    db.session.commit()
    return credit_note


@pytest.fixture
def admin_user(app):
    from models import User, db

    user = User(
        username="adminuser",
        full_name="Admin User",
        role="admin",
        must_change_password=False,
        is_active=True,
    )
    user.set_password("adminpass123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def staff_user(app):
    from models import User, db

    user = User(
        username="staffuser",
        full_name="Staff User",
        role="staff",
        must_change_password=False,
        is_active=True,
    )
    user.set_password("staffpass123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def inactive_user(app):
    from models import User, db

    user = User(
        username="inactiveuser",
        full_name="Inactive User",
        role="staff",
        must_change_password=False,
        is_active=False,
    )
    user.set_password("inactivepass123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def csv_files():
    """Provides paths to CSV test files"""
    import os
    fixtures_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'fixtures'
    )
    return {
        'parties_valid': os.path.join(fixtures_dir, 'parties_valid.csv'),
        'parties_invalid': os.path.join(fixtures_dir, 'parties_invalid.csv'),
        'parties_duplicate_gstin': os.path.join(fixtures_dir, 'parties_duplicate_gstin.csv'),
        'invoices_valid': os.path.join(fixtures_dir, 'invoices_valid.csv'),
        'invoices_invalid': os.path.join(fixtures_dir, 'invoices_invalid.csv'),
        'invoices_missing_party': os.path.join(fixtures_dir, 'invoices_missing_party.csv'),
        'invoices_rcm': os.path.join(fixtures_dir, 'invoices_rcm.csv'),
        'credit_notes_valid': os.path.join(fixtures_dir, 'credit_notes_valid.csv'),
        'credit_notes_invalid': os.path.join(fixtures_dir, 'credit_notes_invalid.csv'),
        'companies_valid': os.path.join(fixtures_dir, 'companies_valid.csv'),
        'companies_multiple_defaults': os.path.join(fixtures_dir, 'companies_multiple_defaults.csv'),
        'companies_update_existing': os.path.join(fixtures_dir, 'companies_update_existing.csv'),
    }


@pytest.fixture
def staff_client(client, staff_user, test_company, app):
    with app.test_request_context():
        with client.session_transaction() as sess:
            sess["user_id"] = staff_user.id
            sess["username"] = staff_user.username
            sess["role"] = staff_user.role
    return client


@pytest.fixture
def second_party(app):
    from models import Party, db

    party = Party(
        name="Second Party",
        gstin="29AAACP5678A1Z5",
        pan="AAACP5678A",
        amc_code="AMC002",
        address="456 New Address",
        state="Karnataka",
        state_code="29",
        email="second@party.com",
        phone="9876543211",
    )
    db.session.add(party)
    db.session.commit()
    return party