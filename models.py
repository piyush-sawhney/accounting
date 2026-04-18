from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import secrets
import hashlib

db = SQLAlchemy()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, hashed):
    return hash_password(password) == hashed


def generate_recovery_code():
    return secrets.token_hex(4).upper()  # e.g., "A1B2C3D4"


class Settings(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)

    @staticmethod
    def get(key, default=None):
        setting = Settings.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set(key, value):
        setting = Settings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = Settings(key=key, value=value)
            db.session.add(setting)
        db.session.commit()


class Party(db.Model):
    __tablename__ = "parties"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    gstin = db.Column(db.String(20), unique=True, nullable=False)
    pan = db.Column(db.String(20), nullable=True)
    amc_code = db.Column(db.String(50), nullable=True)
    address = db.Column(db.Text, nullable=True)
    state = db.Column(db.String(50), nullable=True)
    state_code = db.Column(db.String(5), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    invoices = db.relationship("Invoice", backref="party", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "gstin": self.gstin,
            "pan": self.pan,
            "amc_code": self.amc_code,
            "address": self.address,
            "state": self.state,
            "state_code": self.state_code,
            "email": self.email,
            "phone": self.phone,
        }


class Invoice(db.Model):
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    invoice_no = db.Column(db.String(50), unique=True, nullable=True)
    reference_serial_no = db.Column(db.String(50), nullable=True)
    invoice_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    party_id = db.Column(db.Integer, db.ForeignKey("parties.id"), nullable=False)

    tax_type = db.Column(db.String(10), nullable=False)
    place_of_supply = db.Column(db.String(50), nullable=True)
    sac_hsn_code = db.Column(db.String(20), nullable=True)

    total_in_words = db.Column(db.String(500), nullable=True)
    reverse_charge = db.Column(db.Float, nullable=True, default=0)
    is_rcm = db.Column(db.Boolean, nullable=True, default=False)
    distributor_code = db.Column(db.String(100), nullable=True)

    # Local Party Copy for immutability
    party_name = db.Column(db.String(200), nullable=True)
    party_address = db.Column(db.Text, nullable=True)
    party_gstin = db.Column(db.String(20), nullable=True)
    party_pan = db.Column(db.String(20), nullable=True)
    party_state = db.Column(db.String(50), nullable=True)
    party_state_code = db.Column(db.String(5), nullable=True)

    locked = db.Column(db.Boolean, nullable=True, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    items = db.relationship(
        "InvoiceItem", backref="invoice", lazy=True, cascade="all, delete-orphan"
    )

    def calculate_gst(self):
        subtotal = Decimal("0")
        total_cgst = Decimal("0")
        total_sgst = Decimal("0")
        total_igst = Decimal("0")

        for item in self.items:
            item_total = Decimal(str(item.taxable_value))
            subtotal += item_total

            if self.tax_type == "INTER":
                item_gst = item_total * (Decimal(str(item.igst_rate)) / Decimal("100"))
                total_igst += item_gst
            else:
                item_cgst = item_total * (Decimal(str(item.cgst_rate)) / Decimal("100"))
                item_sgst = item_total * (Decimal(str(item.sgst_rate)) / Decimal("100"))
                total_cgst += item_cgst
                total_sgst += item_sgst

        return {
            "subtotal": float(
                subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            ),
            "cgst": float(total_cgst.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "sgst": float(total_sgst.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "igst": float(total_igst.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "total": float(
                (subtotal + total_cgst + total_sgst + total_igst).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            ),
        }


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="staff")  # admin or staff
    must_change_password = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def set_password(self, password):
        self.password_hash = hash_password(password)
        self.must_change_password = False

    def check_password(self, password):
        return verify_password(password, self.password_hash)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "must_change_password": self.must_change_password,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M")
            if self.created_at
            else None,
        }


class RecoveryCode(db.Model):
    __tablename__ = "recovery_codes"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="recovery_codes")

    def to_dict(self):
        return {
            "code": self.code[:4] + "-" + self.code[4:]
            if len(self.code) > 4
            else self.code,
            "is_used": self.is_used,
            "used_at": self.used_at.strftime("%Y-%m-%d %H:%M")
            if self.used_at
            else None,
            "created_at": self.created_at.strftime("%Y-%m-%d")
            if self.created_at
            else None,
        }


class ConfigStore(db.Model):
    __tablename__ = "config_store"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)

    @staticmethod
    def get(key, default=None):
        setting = ConfigStore.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set(key, value):
        setting = ConfigStore.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = ConfigStore(key=key, value=value)
            db.session.add(setting)
        db.session.commit()

    def to_dict(self):
        gst_data = self.calculate_gst()
        return {
            "id": self.id,
            "invoice_no": self.invoice_no,
            "reference_serial_no": self.reference_serial_no,
            "invoice_date": self.invoice_date.strftime("%Y-%m-%d"),
            "party_id": self.party_id,
            "party": self.party.to_dict() if self.party else None,
            "tax_type": self.tax_type,
            "place_of_supply": self.place_of_supply,
            "sac_hsn_code": self.sac_hsn_code,
            "items": [item.to_dict() for item in self.items],
            "gst_data": gst_data,
            "total_in_words": self.total_in_words,
            "reverse_charge": self.reverse_charge,
            "is_rcm": self.is_rcm,
            "distributor_code": self.distributor_code,
            "party_name": self.party_name,
            "party_address": self.party_address,
            "party_gstin": self.party_gstin,
            "party_pan": self.party_pan,
            "party_state": self.party_state,
            "party_state_code": self.party_state_code,
        }


class InvoiceItem(db.Model):
    __tablename__ = "invoice_items"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    description = db.Column(db.String(500), nullable=False)

    taxable_value = db.Column(db.Float, nullable=False, default=0)

    cgst_rate = db.Column(db.Float, nullable=True, default=0)
    cgst_amt = db.Column(db.Float, nullable=True, default=0)
    sgst_rate = db.Column(db.Float, nullable=True, default=0)
    sgst_amt = db.Column(db.Float, nullable=True, default=0)
    igst_rate = db.Column(db.Float, nullable=True, default=0)
    igst_amt = db.Column(db.Float, nullable=True, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "taxable_value": self.taxable_value,
            "cgst_rate": self.cgst_rate,
            "cgst_amt": self.cgst_amt,
            "sgst_rate": self.sgst_rate,
            "sgst_amt": self.sgst_amt,
            "igst_rate": self.igst_rate,
            "igst_amt": self.igst_amt,
            "total": self.taxable_value + self.cgst_amt + self.sgst_amt + self.igst_amt,
        }


class CreditNote(db.Model):
    __tablename__ = "credit_notes"

    id = db.Column(db.Integer, primary_key=True)
    credit_note_no = db.Column(db.String(50), unique=True, nullable=True)
    credit_note_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)

    reason = db.Column(db.String(100), nullable=False)
    tax_type = db.Column(db.String(10), nullable=False)
    place_of_supply = db.Column(db.String(50), nullable=True)

    total_in_words = db.Column(db.String(500), nullable=True)

    party_name = db.Column(db.String(200), nullable=True)
    party_address = db.Column(db.Text, nullable=True)
    party_gstin = db.Column(db.String(20), nullable=True)
    party_pan = db.Column(db.String(20), nullable=True)
    party_state = db.Column(db.String(50), nullable=True)
    party_state_code = db.Column(db.String(5), nullable=True)

    locked = db.Column(db.Boolean, nullable=True, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    invoice = db.relationship("Invoice", backref="credit_notes")
    items = db.relationship(
        "CreditNoteItem", backref="credit_note", lazy=True, cascade="all, delete-orphan"
    )

    def calculate_gst(self):
        subtotal = Decimal("0")
        total_cgst = Decimal("0")
        total_sgst = Decimal("0")
        total_igst = Decimal("0")

        for item in self.items:
            item_total = Decimal(str(item.taxable_value))
            subtotal += item_total

            if self.tax_type == "INTER":
                item_gst = item_total * (Decimal(str(item.igst_rate)) / Decimal("100"))
                total_igst += item_gst
            else:
                item_cgst = item_total * (Decimal(str(item.cgst_rate)) / Decimal("100"))
                item_sgst = item_total * (Decimal(str(item.sgst_rate)) / Decimal("100"))
                total_cgst += item_cgst
                total_sgst += item_sgst

        return {
            "subtotal": float(
                subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            ),
            "cgst": float(total_cgst.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "sgst": float(total_sgst.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "igst": float(total_igst.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "total": float(
                (subtotal + total_cgst + total_sgst + total_igst).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            ),
        }

    def to_dict(self):
        gst_data = self.calculate_gst()
        return {
            "id": self.id,
            "credit_note_no": self.credit_note_no,
            "credit_note_date": self.credit_note_date.strftime("%Y-%m-%d"),
            "invoice_id": self.invoice_id,
            "invoice": self.invoice.to_dict() if self.invoice else None,
            "reason": self.reason,
            "tax_type": self.tax_type,
            "place_of_supply": self.place_of_supply,
            "items": [item.to_dict() for item in self.items],
            "gst_data": gst_data,
            "total_in_words": self.total_in_words,
            "party_name": self.party_name,
            "party_gstin": self.party_gstin,
            "party_state": self.party_state,
            "party_state_code": self.party_state_code,
        }


class CreditNoteItem(db.Model):
    __tablename__ = "credit_note_items"

    id = db.Column(db.Integer, primary_key=True)
    credit_note_id = db.Column(
        db.Integer, db.ForeignKey("credit_notes.id"), nullable=False
    )
    description = db.Column(db.String(500), nullable=False)

    taxable_value = db.Column(db.Float, nullable=False, default=0)

    cgst_rate = db.Column(db.Float, nullable=True, default=0)
    cgst_amt = db.Column(db.Float, nullable=True, default=0)
    sgst_rate = db.Column(db.Float, nullable=True, default=0)
    sgst_amt = db.Column(db.Float, nullable=True, default=0)
    igst_rate = db.Column(db.Float, nullable=True, default=0)
    igst_amt = db.Column(db.Float, nullable=True, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "taxable_value": self.taxable_value,
            "cgst_rate": self.cgst_rate,
            "cgst_amt": self.cgst_amt,
            "sgst_rate": self.sgst_rate,
            "sgst_amt": self.sgst_amt,
            "igst_rate": self.igst_rate,
            "igst_amt": self.igst_amt,
            "total": self.taxable_value + self.cgst_amt + self.sgst_amt + self.igst_amt,
        }
