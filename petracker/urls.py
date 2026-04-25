from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from tracker.views import RateLimitedLoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', RateLimitedLoginView.as_view(template_name='tracker/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('', include('tracker.urls')),
]
