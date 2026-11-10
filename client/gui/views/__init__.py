"""
Skillora Client GUI Views Package (client/gui/views)
Exports all 5 core application views:
- DashboardView (F17)
- CompanyView (F18)
- MathStudioView (F19)
- CodingSandboxView (F20)
- InterviewView (F21)
"""

from client.gui.views.dashboard_view import DashboardView
from client.gui.views.company_view import CompanyView
from client.gui.views.math_studio_view import MathStudioView
from client.gui.views.coding_sandbox_view import CodingSandboxView
from client.gui.views.interview_view import InterviewView

__all__ = [
    "DashboardView",
    "CompanyView",
    "MathStudioView",
    "CodingSandboxView",
    "InterviewView",
]
