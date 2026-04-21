from sqlalchemy import func, case
from datetime import datetime, timedelta
from models import Invoice, Party, InvoiceItem
from app import db



def get_date_range(date_range):
    """Get start and end dates based on date_range parameter."""
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    if date_range == "this_month":
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = now
    elif date_range == "last_month":
        if current_month == 1:
            period_start = datetime(current_year - 1, 12, 1)
        else:
            period_start = datetime(current_year, current_month - 1, 1)
        period_end = now.replace(day=1) - timedelta(days=1)
    elif date_range == "this_quarter":
        quarter_start = ((current_month - 1) // 3) * 3 + 1
        period_start = datetime(current_year, quarter_start, 1)
        period_end = now
    else:  # Default to fiscal year
        period_start = datetime(current_year, 4, 1)
        period_end = now

    return period_start, period_end


def get_last_month_dates(period_start):
    """Get last month start and end dates."""
    last_month_start = (period_start - timedelta(days=1)).replace(day=1)
    last_month_end = period_start - timedelta(days=1)
    return last_month_start, last_month_end


def get_two_months_back_dates(last_month_start):
    """Get two months back start and end dates."""
    two_months_back_start = (last_month_start - timedelta(days=1)).replace(day=1)
    two_months_back_end = last_month_start - timedelta(days=1)
    return two_months_back_start, two_months_back_end


def get_three_months_back_dates(two_months_back_start):
    """Get three months back start and end dates."""
    three_months_start = (two_months_back_start - timedelta(days=1)).replace(day=1)
    three_months_end = two_months_back_start - timedelta(days=1)
    return three_months_start, three_months_end


def get_four_months_back_dates(three_months_start):
    """Get four months back start and end dates."""
    four_months_start = (three_months_start - timedelta(days=1)).replace(day=1)
    four_months_end = three_months_start - timedelta(days=1)
    return four_months_start, four_months_end


def get_last_3_months_dates(last_month_end):
    """Get last 3 months start and end dates."""
    last_3m_end = last_month_end
    if datetime.now().month > 3:
        last_3m_start = datetime(datetime.now().year, datetime.now().month - 3, 1)
    else:
        last_3m_start = datetime(datetime.now().year - 1, datetime.now().month + 9, 1)
    return last_3m_start, last_3m_end


def get_this_month_last_year_dates():
    """Get this month last year start and end dates."""
    now = datetime.now()
    this_month_last_year_start = datetime(now.year - 1, now.month, 1)
    if now.month == 12:
        this_month_last_year_end = datetime(now.year - 1, 12, 31)
    else:
        this_month_last_year_end = datetime(now.year - 1, now.month + 1, 1) - timedelta(
            days=1
        )
    return this_month_last_year_start, this_month_last_year_end


def get_filtered_invoices(period_start, period_end, party_id):
    """Get filtered invoices based on period and party."""
    query = Invoice.query.filter(Invoice.invoice_date >= period_start)

    if period_end:
        query = query.filter(Invoice.invoice_date <= period_end)

    if party_id and party_id.strip():
        try:
            query = query.filter(Invoice.party_id == int(party_id))
        except (ValueError, TypeError):
            pass

    invoices = query.order_by(Invoice.invoice_date.desc()).all()
    parties = Party.query.all()
    return invoices, parties


def calculate_revenue_and_gst(invoice_gst_data, credit_note_gst_data=None):
    """Calculate revenue and GST from invoice and credit note GST data."""
    if credit_note_gst_data is None:
        credit_note_gst_data = []

    this_month_revenue = sum(
        gst_data.get("subtotal", 0) or 0
        for inv, gst_data in invoice_gst_data
        if not inv.is_rcm
    )
    this_month_revenue -= sum(
        gst_data.get("subtotal", 0) or 0
        for cn, gst_data in credit_note_gst_data
    )

    this_month_gst = sum(
        (gst_data.get("cgst", 0) or 0)
        + (gst_data.get("sgst", 0) or 0)
        + (gst_data.get("igst", 0) or 0)
        for inv, gst_data in invoice_gst_data
        if not inv.is_rcm
    )
    this_month_gst -= sum(
        (gst_data.get("cgst", 0) or 0)
        + (gst_data.get("sgst", 0) or 0)
        + (gst_data.get("igst", 0) or 0)
        for cn, gst_data in credit_note_gst_data
    )
    invoice_count = len([inv for inv, _ in invoice_gst_data])
    unlocked_count = sum(1 for inv, _ in invoice_gst_data if not inv.locked)
    return this_month_revenue, this_month_gst, invoice_count, unlocked_count


def get_prefiltered_invoices(
    period_start,
    period_end,
    last_month_start,
    last_month_end,
    two_months_back_start,
    two_months_back_end,
    three_months_start,
    three_months_end,
    four_months_start,
    four_months_end,
    last_3m_start,
    last_3m_end,
    this_month_last_year_start,
    this_month_last_year_end,
):
    """Get pre-filtered invoices for various date ranges."""
    this_month_invs_all = Invoice.query.filter(
        Invoice.invoice_date >= period_start,
        Invoice.invoice_date <= period_end,
    ).all()

    last_month_invs_all = Invoice.query.filter(
        Invoice.invoice_date >= last_month_start,
        Invoice.invoice_date <= last_month_end,
    ).all()

    two_months_back_invs_all = Invoice.query.filter(
        Invoice.invoice_date >= two_months_back_start,
        Invoice.invoice_date <= two_months_back_end,
    ).all()

    three_months_back_invs_all = Invoice.query.filter(
        Invoice.invoice_date >= three_months_start,
        Invoice.invoice_date <= three_months_end,
    ).all()

    four_months_back_invs_all = Invoice.query.filter(
        Invoice.invoice_date >= four_months_start,
        Invoice.invoice_date <= four_months_end,
    ).all()

    last_3m_invs_all = Invoice.query.filter(
        Invoice.invoice_date >= last_3m_start,
        Invoice.invoice_date <= last_3m_end,
    ).all()

    this_month_last_year_invs_all = Invoice.query.filter(
        Invoice.invoice_date >= this_month_last_year_start,
        Invoice.invoice_date <= this_month_last_year_end,
    ).all()

    return (
        this_month_invs_all,
        last_month_invs_all,
        two_months_back_invs_all,
        three_months_back_invs_all,
        four_months_back_invs_all,
        last_3m_invs_all,
        this_month_last_year_invs_all,
    )


def precalculate_gst_data(
    this_month_invs_all,
    last_month_invs_all,
    two_months_back_invs_all,
    three_months_back_invs_all,
    four_months_back_invs_all,
    last_3m_invs_all,
    this_month_last_year_invs_all,
):
    """Pre-calculate GST data for all filtered invoices."""
    this_month_invs_with_gst = [
        (inv, inv.calculate_gst()) for inv in this_month_invs_all
    ]
    last_month_invs_with_gst = [
        (inv, inv.calculate_gst()) for inv in last_month_invs_all
    ]
    two_months_back_invs_with_gst = [
        (inv, inv.calculate_gst()) for inv in two_months_back_invs_all
    ]
    three_months_back_invs_with_gst = [
        (inv, inv.calculate_gst()) for inv in three_months_back_invs_all
    ]
    four_months_back_invs_with_gst = [
        (inv, inv.calculate_gst()) for inv in four_months_back_invs_all
    ]
    last_3m_invs_with_gst = [(inv, inv.calculate_gst()) for inv in last_3m_invs_all]
    this_month_last_year_invs_with_gst = [
        (inv, inv.calculate_gst()) for inv in this_month_last_year_invs_all
    ]

    return (
        this_month_invs_with_gst,
        last_month_invs_with_gst,
        two_months_back_invs_with_gst,
        three_months_back_invs_with_gst,
        four_months_back_invs_with_gst,
        last_3m_invs_with_gst,
        this_month_last_year_invs_with_gst,
    )


def calculate_party_growth_data(
    parties,
    period_start,
    period_end,
    last_month_start,
    last_month_end,
    two_months_back_start,
    two_months_back_end,
    three_months_start,
    three_months_end,
    four_months_start,
    four_months_end,
    last_3m_start,
    last_3m_end,
    this_month_last_year_start,
    this_month_last_year_end,
):
    """Calculate party growth data using SQL aggregations for performance."""
    
    # Define the aggregation query
    # We join Invoice and InvoiceItem and sum taxable_value for non-RCM invoices in specified ranges
    stats_query = db.session.query(
        Invoice.party_id,
        func.sum(case(((Invoice.invoice_date >= period_start) & (Invoice.invoice_date <= period_end) & (Invoice.is_rcm == False), InvoiceItem.taxable_value), else_=0)).label('this_month'),
        func.sum(case(((Invoice.invoice_date >= last_month_start) & (Invoice.invoice_date <= last_month_end) & (Invoice.is_rcm == False), InvoiceItem.taxable_value), else_=0)).label('last_month'),
        func.sum(case(((Invoice.invoice_date >= two_months_back_start) & (Invoice.invoice_date <= two_months_back_end) & (Invoice.is_rcm == False), InvoiceItem.taxable_value), else_=0)).label('two_months_ago'),
        func.sum(case(((Invoice.invoice_date >= three_months_start) & (Invoice.invoice_date <= three_months_end) & (Invoice.is_rcm == False), InvoiceItem.taxable_value), else_=0)).label('three_months_ago'),
        func.sum(case(((Invoice.invoice_date >= four_months_start) & (Invoice.invoice_date <= four_months_end) & (Invoice.is_rcm == False), InvoiceItem.taxable_value), else_=0)).label('four_months_ago'),
        func.sum(case(((Invoice.invoice_date >= last_3m_start) & (Invoice.invoice_date <= last_3m_end) & (Invoice.is_rcm == False), InvoiceItem.taxable_value), else_=0)).label('last_3m'),
        func.sum(case(((Invoice.invoice_date >= this_month_last_year_start) & (Invoice.invoice_date <= this_month_last_year_end) & (Invoice.is_rcm == False), InvoiceItem.taxable_value), else_=0)).label('this_month_last_year'),
    ).join(InvoiceItem).group_by(Invoice.party_id).all()

    party_stats = {row.party_id: row for row in stats_query}
    
    party_growth_data = []
    max_revenue = 0

    for party in parties:
        stats = party_stats.get(party.id)
        
        this_month_rev = float(stats.this_month) if stats else 0.0
        last_month_rev = float(stats.last_month) if stats else 0.0
        two_months_ago_rev = float(stats.two_months_ago) if stats else 0.0
        three_months_ago_rev = float(stats.three_months_ago) if stats else 0.0
        four_months_ago_rev = float(stats.four_months_ago) if stats else 0.0
        last_3m_rev = float(stats.last_3m) if stats else 0.0
        this_month_last_year_rev = float(stats.this_month_last_year) if stats else 0.0

        if this_month_rev > max_revenue:
            max_revenue = this_month_rev

        party_growth_data.append(
            {
                "name": party.name,
                "this_month": this_month_rev,
                "this_month_last_year": this_month_last_year_rev,
                "last_month": last_month_rev,
                "two_months_ago": two_months_ago_rev,
                "three_months_ago": three_months_ago_rev,
                "four_months_ago": four_months_ago_rev,
                "last_3m": last_3m_rev,
                "growth": 0,
                "trend": [],
            }
        )

    return party_growth_data, max_revenue


def sort_party_growth_data(party_growth_data, sort_by):
    """Sort party growth data."""
    if sort_by == "name":
        party_growth_data = sorted(
            party_growth_data, key=lambda x: x["name"], reverse=False
        )
    else:
        party_growth_data = sorted(
            party_growth_data, key=lambda x: x["this_month"], reverse=True
        )
    return party_growth_data


def add_missing_parties(party_growth_data, parties):
    """Add missing parties to party growth data."""
    # Show ALL parties (not just those with recent invoices)
    party_dict = {p.name: p for p in parties}
    for party in parties:
        party_name = party.name
        existing = next((x for x in party_growth_data if x["name"] == party_name), None)
        if not existing:
            party_growth_data.append(
                {
                    "name": party.name,
                    "this_month": 0,
                    "this_month_last_year": 0,
                    "last_month": 0,
                    "two_months_ago": 0,
                    "three_months_ago": 0,
                    "four_months_ago": 0,
                    "last_3m": 0,
                    "growth": 0,
                    "trend": [0, 0, 0, 0, 0, 0],
                }
            )
    return party_growth_data


def calculate_revenue_change(this_month_revenue, party_growth_data):
    """Calculate overall revenue change."""
    total_last_month = sum(p["last_month"] for p in party_growth_data)
    if total_last_month > 0:
        revenue_change = (
            (this_month_revenue - total_last_month) / total_last_month
        ) * 100
    else:
        revenue_change = 0
    return revenue_change


def get_pending_invoices_info():
    """Get pending invoices count and amount."""
    pending_invoices = Invoice.query.filter(Invoice.invoice_no.is_(None)).all()
    pending_count = len(pending_invoices)
    pending_amount = sum(
        inv.calculate_gst().get("total", 0) or 0 for inv in pending_invoices
    )
    return pending_count, pending_amount


def prepare_chart_data(month_names):
    """Prepare chart data."""
    now = datetime.now()
    chart_labels = []
    chart_data = []

    months = [
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
        "Jan",
        "Feb",
        "Mar",
    ]

    for i in range(5, -1, -1):
        m = now.month - i
        y = now.year
        if m < 1:
            m += 12
            y -= 1

        start = datetime(y, m, 1).date()
        if m == 12:
            end = datetime(y + 1, 1, 1).date()
        else:
            end = datetime(y, m + 1, 1).date()

        month_invoices = Invoice.query.filter(
            Invoice.invoice_date >= start, Invoice.invoice_date < end
        ).all()

        # Pre-calculate GST data for month invoices
        month_invoices_with_gst = [(inv, inv.calculate_gst()) for inv in month_invoices]

        revenue = sum(
            gst_data.get("subtotal", 0) or 0 for _, gst_data in month_invoices_with_gst
        )
        chart_labels.append(months[(m - 4 + 12) % 12])
        chart_data.append(revenue)

    return chart_labels, chart_data


def calculate_top_parties(invoices):
    """Calculate top parties."""
    this_month_party_stats = {}
    for inv in invoices:
        party_name = inv.party.name if inv.party else "Unknown"
        if party_name not in this_month_party_stats:
            this_month_party_stats[party_name] = {"count": 0, "revenue": 0}
        this_month_party_stats[party_name]["count"] += 1
        this_month_party_stats[party_name]["revenue"] += (
            inv.calculate_gst().get("subtotal", 0) or 0
        )

    top_parties = sorted(
        this_month_party_stats.items(), key=lambda x: x[1]["revenue"], reverse=True
    )[:5]

    return this_month_party_stats, top_parties


def get_trend_months():
    """Get trend months for display."""
    now = datetime.now()
    trend_months = []
    for i in range(5, -1, -1):
        trg_month = (now.month - i + 12) % 12 + 1
        trg_year = now.year if (now.month - i) > 0 else now.year - 1
        if now.month - i <= 0:
            trg_year = now.year - 1
        month_name = get_month_name(trg_month)[:3]
        trend_months.append(f"{month_name}")
    return trend_months


def get_month_name(month_num):
    """Get month name from month number."""
    months = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    return months[month_num - 1] if 1 <= month_num <= 12 else ""
