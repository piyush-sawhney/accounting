import pytest
from datetime import datetime, date, timedelta


class TestDateHelperFunctions:
    def test_get_date_range_this_month(self, app):
        from helpers import get_date_range

        with app.app_context():
            period_start, period_end = get_date_range("this_month")

            assert period_start.day == 1
            assert period_end <= datetime.now()

    def test_get_date_range_last_month(self, app):
        from helpers import get_date_range

        with app.app_context():
            period_start, period_end = get_date_range("last_month")

            assert period_start.day == 1

    def test_get_date_range_this_quarter(self, app):
        from helpers import get_date_range

        with app.app_context():
            period_start, period_end = get_date_range("this_quarter")

            assert period_start.day == 1

    def test_get_date_range_fiscal_year(self, app):
        from helpers import get_date_range

        with app.app_context():
            period_start, period_end = get_date_range("fiscal_year")

            assert period_start.month == 4
            assert period_start.day == 1

    def test_get_date_range_invalid(self, app):
        from helpers import get_date_range

        with app.app_context():
            period_start, period_end = get_date_range("invalid_range")

            assert period_start.month == 4
            assert period_end <= datetime.now()

    def test_get_date_range_january_edge(self, app):
        from helpers import get_date_range

        with app.app_context():
            period_start, period_end = get_date_range("last_month")

            if datetime.now().month == 1:
                assert period_start.month == 12
                assert period_start.year == datetime.now().year - 1


class TestRevenueCalculation:
    def test_calculate_revenue_and_gst(self, app, test_invoice):
        from helpers import calculate_revenue_and_gst

        with app.app_context():
            invoice = test_invoice
            gst_data = [(invoice, invoice.calculate_gst())]
            revenue, gst, count, unlocked = calculate_revenue_and_gst(gst_data)

            assert revenue == 10000.00
            assert gst == 1800.00
            assert count == 1
            assert unlocked == 1

    def test_calculate_revenue_and_gst_with_credit_notes(self, app, test_locked_invoice):
        from helpers import calculate_revenue_and_gst
        from models import CreditNote, CreditNoteItem, db

        with app.app_context():
            cn = CreditNote(
                credit_note_date=date(2026, 4, 15),
                invoice_id=test_locked_invoice.id,
                reason="Test",
                tax_type="INTRA",
                party_name=test_locked_invoice.party_name,
                party_gstin=test_locked_invoice.party_gstin,
            )
            db.session.add(cn)
            db.session.flush()

            cn_item = CreditNoteItem(
                credit_note_id=cn.id,
                description="Test",
                taxable_value=2000.00,
                cgst_rate=9.0,
                cgst_amt=180.00,
                sgst_rate=9.0,
                sgst_amt=180.00,
            )
            db.session.add(cn_item)
            db.session.commit()

            invoice_gst_data = [(test_locked_invoice, test_locked_invoice.calculate_gst())]
            credit_note_gst_data = [(cn, cn.calculate_gst())]

            revenue, gst, count, unlocked = calculate_revenue_and_gst(
                invoice_gst_data, credit_note_gst_data
            )

            assert revenue < 15000.00


class TestFilterFunctions:
    def test_get_filtered_invoices(self, app, test_invoice):
        from helpers import get_filtered_invoices
        from datetime import datetime

        with app.app_context():
            period_start = datetime(2026, 1, 1)
            period_end = datetime(2026, 12, 31)

            invoices, parties = get_filtered_invoices(period_start, period_end, None)

            assert isinstance(invoices, list)

    def test_get_filtered_invoices_with_party_id(self, app, test_invoice):
        from helpers import get_filtered_invoices
        from datetime import datetime

        with app.app_context():
            period_start = datetime(2026, 1, 1)
            period_end = datetime(2026, 12, 31)

            invoices, parties = get_filtered_invoices(
                period_start, period_end, str(test_invoice.party_id)
            )

            assert isinstance(invoices, list)

    def test_get_filtered_invoices_invalid_party_id(self, app, test_invoice):
        from helpers import get_filtered_invoices
        from datetime import datetime

        with app.app_context():
            period_start = datetime(2026, 1, 1)
            period_end = datetime(2026, 12, 31)

            invoices, parties = get_filtered_invoices(
                period_start, period_end, "invalid"
            )

            assert isinstance(invoices, list)


class TestPendingInvoices:
    def test_get_pending_invoices_info(self, app, test_invoice):
        from helpers import get_pending_invoices_info

        with app.app_context():
            count, amount = get_pending_invoices_info()
            assert count >= 0
            assert amount >= 0

    def test_get_pending_invoices_with_pending(self, app, test_party):
        from helpers import get_pending_invoices_info
        from models import Invoice, db

        with app.app_context():
            invoice = Invoice(
                invoice_date=date(2026, 4, 1),
                party_id=test_party.id,
                tax_type="INTRA",
            )
            db.session.add(invoice)
            db.session.commit()

            count, amount = get_pending_invoices_info()
            assert count >= 1


class TestTopParties:
    def test_calculate_top_parties(self, app, test_invoice):
        from helpers import calculate_top_parties

        with app.app_context():
            stats, top = calculate_top_parties([test_invoice])

            assert isinstance(stats, dict)

    def test_calculate_top_parties_empty(self, app):
        from helpers import calculate_top_parties

        with app.app_context():
            stats, top = calculate_top_parties([])

            assert isinstance(stats, dict)
            assert len(top) == 0


class TestTrendMonths:
    def test_get_trend_months(self, app):
        from helpers import get_trend_months

        with app.app_context():
            months = get_trend_months()

            assert len(months) == 6

    def test_get_trend_months_format(self, app):
        from helpers import get_trend_months

        with app.app_context():
            months = get_trend_months()

            assert all(len(m) <= 4 for m in months)

    def test_get_month_name(self, app):
        from helpers import get_month_name

        with app.app_context():
            assert get_month_name(1) == "January"
            assert get_month_name(12) == "December"

    def test_get_month_name_invalid(self, app):
        from helpers import get_month_name

        with app.app_context():
            assert get_month_name(0) == ""
            assert get_month_name(13) == ""


class TestRevenueChange:
    def test_calculate_revenue_change(self, app):
        from helpers import calculate_revenue_change

        with app.app_context():
            result = calculate_revenue_change(1000, [
                {"this_month": 1000, "last_month": 800}
            ])

            assert result == 25.0

    def test_calculate_revenue_change_zero_last_month(self, app):
        from helpers import calculate_revenue_change

        with app.app_context():
            result = calculate_revenue_change(1000, [
                {"this_month": 1000, "last_month": 0}
            ])

            assert result == 0

    def test_calculate_revenue_change_negative(self, app):
        from helpers import calculate_revenue_change

        with app.app_context():
            result = calculate_revenue_change(800, [
                {"this_month": 800, "last_month": 1000}
            ])

            assert result == -20.0


class TestPartyGrowthData:
    def test_sort_party_growth_data_by_name(self, app):
        from helpers import sort_party_growth_data

        with app.app_context():
            data = [
                {"name": "Zebra Corp", "this_month": 1000},
                {"name": "Alpha Corp", "this_month": 500},
            ]

            result = sort_party_growth_data(data, "name")

            assert result[0]["name"] == "Alpha Corp"

    def test_sort_party_growth_data_by_revenue(self, app):
        from helpers import sort_party_growth_data

        with app.app_context():
            data = [
                {"name": "Zebra Corp", "this_month": 1000},
                {"name": "Alpha Corp", "this_month": 5000},
            ]

            result = sort_party_growth_data(data, "revenue")

            assert result[0]["name"] == "Alpha Corp"

    def test_add_missing_parties(self, app, test_party):
        from helpers import add_missing_parties

        with app.app_context():
            data = []
            result = add_missing_parties(data, [test_party])

            assert len(result) == 1

    def test_add_missing_parties_with_existing(self, app, test_party):
        from helpers import add_missing_parties

        with app.app_context():
            data = [{"name": test_party.name, "this_month": 1000}]
            result = add_missing_parties(data, [test_party])

            assert len(result) == 1


class TestChartData:
    def test_prepare_chart_data(self, app):
        from helpers import prepare_chart_data

        with app.app_context():
            month_names = ["Apr", "May", "Jun"]
            labels, data = prepare_chart_data(month_names)

            assert isinstance(labels, list)
            assert isinstance(data, list)

    def test_prepare_chart_data_no_invoices(self, app):
        from helpers import prepare_chart_data

        with app.app_context():
            month_names = ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]
            labels, data = prepare_chart_data(month_names)

            assert isinstance(labels, list)
            assert isinstance(data, list)


class TestDateHelpers:
    def test_get_last_month_dates(self, app):
        from helpers import get_last_month_dates

        with app.app_context():
            period_start = datetime(2026, 4, 1)
            start, end = get_last_month_dates(period_start)

            assert start.month == 3
            assert end.month == 3

    def test_get_two_months_back_dates(self, app):
        from helpers import get_two_months_back_dates

        with app.app_context():
            last_month_start = datetime(2026, 3, 1)
            start, end = get_two_months_back_dates(last_month_start)

            assert start.month == 2

    def test_get_last_3_months_dates(self, app):
        from helpers import get_last_3_months_dates

        with app.app_context():
            last_month_end = datetime(2026, 4, 30)
            start, end = get_last_3_months_dates(last_month_end)

            assert start <= end

    def test_get_this_month_last_year_dates(self, app):
        from helpers import get_this_month_last_year_dates

        with app.app_context():
            start, end = get_this_month_last_year_dates()

            assert start.year == datetime.now().year - 1
            assert end.year == datetime.now().year - 1