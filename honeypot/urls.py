from django.urls import path
from . import views

urlpatterns = [
    path('wp-admin/', views.fake_login, name='honeypot-wpadmin'),
    path('wp-login.php', views.fake_login, name='honeypot-wplogin'),
    path('admin/login/', views.fake_login, name='honeypot-admin'),
    path('hidden-admin/', views.fake_login, name='honeypot-hidden'),
    path('.env', views.fake_login, name='honeypot-env'),
    path('config.php', views.fake_login, name='honeypot-config'),
]