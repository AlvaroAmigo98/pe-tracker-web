from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('people/', views.people, name='people'),
    path('firms/', views.firms, name='firms'),
    path('firms/<int:company_id>/', views.firm_detail, name='firm_detail'),
    path('firms/<int:company_id>/report/', views.firm_report, name='firm_report'),
    path('signals/', views.signals, name='signals'),
    path('search/', views.search, name='search'),
    path('watchlist/toggle/<int:company_id>/', views.watchlist_toggle, name='watchlist_toggle'),
]
