from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('people/', views.people, name='people'),
    path('firms/', views.firms, name='firms'),
    path('firms/<int:company_id>/', views.firm_detail, name='firm_detail'),
    path('firms/<int:company_id>/report/', views.firm_report, name='firm_report'),
    path('signals/', views.signals, name='signals'),
    path('search/', views.search, name='search'),
    path('api/search/', views.api_search, name='api_search'),
    path('scrape-logs/', views.scrape_logs, name='scrape_logs'),
    path('scrape-logs/<int:run_id>/delete/', views.delete_run, name='delete_run'),
    path('scrape-logs/<int:run_id>/delete-firm/', views.delete_firm_snapshot, name='delete_firm_snapshot'),
    path('data-review/', views.data_review, name='data_review'),
    path('data-review/batch/<str:batch_id>/approve/', views.batch_approve, name='batch_approve'),
    path('data-review/batch/<str:batch_id>/reject/', views.batch_reject, name='batch_reject'),
    path('data-review/batch/<str:batch_id>/edit/', views.batch_edit, name='batch_edit'),
    path('profile/',    views.profile,     name='profile'),
    path('users/',      views.user_admin,  name='user_admin'),
    path('watchlist/toggle/<int:company_id>/', views.watchlist_toggle, name='watchlist_toggle'),
    path('people/<int:person_id>/', views.person_profile, name='person_profile'),
]
