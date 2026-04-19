from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('people/', views.people, name='people'),
    path('firms/', views.firms, name='firms'),
    path('firms/<int:company_id>/', views.firm_detail, name='firm_detail'),
]
