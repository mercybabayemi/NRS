from analysis.components.audit_data import audit_data
from analysis.components.header import view_header
from analysis.views import industries

def dashboard_view():
    view_header("Dashboard", "Financial Footprint vs. Tax Declarations", False, None)
