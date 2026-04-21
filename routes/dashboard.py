from flask import Blueprint, render_template, request
from datetime import datetime
from models import Invoice, Party, db, CreditNote
from helpers import (

    get_date_range,
    get_last_month_dates,
    get_two_months_back_dates,
    get_three_months_back_dates,
    get_four_months_back_dates,
    get_last_3_months_dates,
    get_this_month_last_year_dates,
    get_filtered_invoices,
    calculate_revenue_and_gst,
    calculate_party_growth_data,
    sort_party_growth_data,
    add_missing_parties,
    calculate_revenue_change,
    get_pending_invoices_info,
    prepare_chart_data,
    calculate_top_parties,
    get_trend_months,
    get_month_name,
)
from utils import login_required, get_current_company


dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    date_range = request.args.get("date_range", "this_month")
    party_id = request.args.get("party")
    search = request.args.get("search", "").strip()
    sort_by = request.args.get("sort_by", "revenue")

    period_start, period_end = get_date_range(date_range)
    last_month_start, last_month_end = get_last_month_dates(period_start)
    two_months_back_start, two_months_back_end = get_two_months_back_dates(last_month_start)
    three_months_start, three_months_end = get_three_months_back_dates(two_months_back_start)
    four_months_start, four_months_end = get_four_months_back_dates(three_months_start)
    last_3m_start, last_3m_end = get_last_3_months_dates(last_month_end)
    this_month_last_year_start, this_month_last_year_end = get_this_month_last_year_dates()

    this_month_last_year_label = f"{get_month_name(datetime.now().month)} {datetime.now().year - 1}"

    invoices, parties = get_filtered_invoices(period_start, period_end, party_id)
    invoice_gst_data = [(inv, inv.calculate_gst()) for inv in invoices]

    credit_notes = CreditNote.query.filter(
        CreditNote.credit_note_date >= period_start,
        CreditNote.credit_note_date <= period_end,
    ).all()
    credit_note_gst_data = [(cn, cn.calculate_gst()) for cn in credit_notes]

    this_month_revenue, this_month_gst, invoice_count, unlocked_count = (
        calculate_revenue_and_gst(invoice_gst_data, credit_note_gst_data)
    )

    party_growth_data, max_revenue = calculate_party_growth_data(
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
    )

    party_growth_data = sort_party_growth_data(party_growth_data, sort_by)
    party_growth_data = add_missing_parties(party_growth_data, parties)
    revenue_change = calculate_revenue_change(this_month_revenue, party_growth_data)
    pending_count, pending_amount = get_pending_invoices_info()

    month_names = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    chart_labels, chart_data = prepare_chart_data(month_names)
    this_month_party_stats, top_parties = calculate_top_parties(invoices)

    company = get_current_company()
    company_name = company.name if company else ""
    greeting = "Good Morning" if datetime.now().hour < 12 else "Good Afternoon" if datetime.now().hour < 17 else "Good Evening"
    trend_months = get_trend_months()

    return render_template(
        "dashboard.html",
        invoices=invoices[:5],
        parties=parties,
        pending_count=pending_count,
        pending_amount=pending_amount,
        this_month_revenue=this_month_revenue,
        this_month_gst=this_month_gst,
        invoice_count=invoice_count,
        revenue_change=revenue_change,
        chart_labels=chart_labels,
        chart_data=chart_data,
        top_parties=top_parties,
        date_range=date_range,
        selected_party=party_id,
        greeting=greeting,
        company_name=company_name,
        party_growth_data=party_growth_data,
        max_revenue=max_revenue,
        sort_by=sort_by,
        trend_months=trend_months,
        current_year=datetime.now().year,
        this_month_last_year_label=this_month_last_year_label,
    )
