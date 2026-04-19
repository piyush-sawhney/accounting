from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    SubmitField,
    TextAreaField,
    SelectField,
    DateField,
    FloatField,
    IntegerField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    Email,
    EqualTo,
    ValidationError,
    Regexp,
    NumberRange,
)
from models import User, Party


class LoginForm(FlaskForm):
    username = StringField(
        "Username", validators=[DataRequired(), Length(min=4, max=25)]
    )
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember Me")
    submit = SubmitField("Sign In")


class SetupForm(FlaskForm):
    full_name = StringField(
        "Full Name", validators=[DataRequired(), Length(min=2, max=100)]
    )
    username = StringField(
        "Username", validators=[DataRequired(), Length(min=4, max=25)]
    )
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Confirm Password", validators=[DataRequired(), EqualTo("password")]
    )
    submit = SubmitField("Setup Account")

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError(
                "Username already exists. Please choose a different one."
            )


class PartyForm(FlaskForm):
    name = StringField(
        "Party Name", validators=[DataRequired(), Length(min=2, max=200)]
    )
    gstin = StringField(
        "GSTIN",
        validators=[
            DataRequired(),
            Length(min=15, max=15),
            Regexp(
                r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$",
                message="Invalid GSTIN format",
            ),
        ],
    )
    pan = StringField("PAN", validators=[Length(max=20)])
    amc_code = StringField("AMC Code", validators=[Length(max=50)])
    address = TextAreaField("Address")
    state = StringField("State", validators=[Length(max=50)])
    state_code = StringField("State Code", validators=[Length(max=5)])
    email = StringField("Email", validators=[Length(max=100), Email()])
    phone = StringField("Phone", validators=[Length(max=20)])
    submit = SubmitField("Save Party")

    def validate_gstin(self, gstin):
        party = Party.query.filter_by(gstin=gstin.data.upper()).first()
        if party:
            raise ValidationError("Party with this GSTIN already exists.")


class InvoiceForm(FlaskForm):
    reference_serial_no = StringField(
        "Reference Serial Number", validators=[Length(max=50)]
    )
    invoice_date = DateField(
        "Invoice Date", validators=[DataRequired()], format="%Y-%m-%d"
    )
    tax_type = SelectField(
        "Tax Type",
        choices=[("INTRA", "Intra State"), ("INTER", "Inter State")],
        validators=[DataRequired()],
    )
    place_of_supply = StringField("Place of Supply", validators=[Length(max=50)])
    sac_hsn_code = StringField(
        "SAC/HSN Code", validators=[DataRequired(), Length(max=20)]
    )
    reverse_charge = FloatField(
        "Reverse Charge %", validators=[NumberRange(min=0, max=100)], default=0
    )
    is_rcm = BooleanField("Reverse Charge Mechanism")
    distributor_code = StringField("Distributor Code", validators=[Length(max=100)])
    submit = SubmitField("Create Invoice")

    def validate(self, extra_validators=None):
        # Call parent validation
        if not super().validate(extra_validators):
            return False

        # Custom validation: if RCM is enabled, reverse charge must be > 0
        if self.is_rcm.data and (
            self.reverse_charge.data is None or self.reverse_charge.data <= 0
        ):
            self.reverse_charge.errors.append(
                "Reverse Charge percentage is required when RCM is enabled."
            )
            return False

        return True


class CreditNoteForm(FlaskForm):
    credit_note_date = DateField(
        "Credit Note Date", validators=[DataRequired()], format="%Y-%m-%d"
    )
    reason = StringField("Reason", validators=[DataRequired(), Length(min=5, max=200)])
    tax_type = SelectField(
        "Tax Type",
        choices=[("INTRA", "Intra State"), ("INTER", "Inter State")],
        validators=[DataRequired()],
    )
    place_of_supply = StringField("Place of Supply", validators=[Length(max=50)])
    submit = SubmitField("Create Credit Note")


class RecoveryCodeForm(FlaskForm):
    code = StringField(
        "Recovery Code", validators=[DataRequired(), Length(min=8, max=8)]
    )
    password = PasswordField("New Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Confirm Password", validators=[DataRequired(), EqualTo("password")]
    )
    submit = SubmitField("Reset Password")


class UserForm(FlaskForm):
    full_name = StringField(
        "Full Name", validators=[DataRequired(), Length(min=2, max=100)]
    )
    username = StringField(
        "Username", validators=[DataRequired(), Length(min=4, max=25)]
    )
    role = SelectField(
        "Role",
        choices=[("staff", "Staff"), ("admin", "Admin")],
        validators=[DataRequired()],
    )
    password = PasswordField("Password", validators=[Length(min=6)])
    submit = SubmitField("Save User")

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user and (not hasattr(self, "user_id") or user.id != self.user_id):
            raise ValidationError(
                "Username already exists. Please choose a different one."
            )
