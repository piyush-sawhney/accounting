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


class TestFilterFunctions:
    def test_get_filtered_invoices(self, app, test_invoice):
        from helpers import get_filtered_invoices
        from datetime import datetime

        with app.app_context():
            period_start = datetime(2026, 1, 1)
            period_end = datetime(2026, 12, 31)

            invoices, parties = get_filtered_invoices(period_start, period_end, None)

            assert isinstance(invoices, list)


class TestPendingInvoices:
    def test_get_pending_invoices_info(self, app, test_invoice):
        from helpers import get_pending_invoices_info

        with app.app_context():
            count, amount = get_pending_invoices_info()
            assert count >= 0
            assert amount >= 0


class TestTopParties:
    def test_calculate_top_parties(self, app, test_invoice):
        from helpers import calculate_top_parties

        with app.app_context():
            stats, top = calculate_top_parties([test_invoice])

            assert isinstance(stats, dict)


class TestTrendMonths:
    def test_get_trend_months(self, app):
        from helpers import get_trend_months

        with app.app_context():
            months = get_trend_months()

            assert len(months) == 6

    def test_get_month_name(self, app):
        from helpers import get_month_name

        with app.app_context():
            assert get_month_name(1) == "January"
            assert get_month_name(12) == "December"


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