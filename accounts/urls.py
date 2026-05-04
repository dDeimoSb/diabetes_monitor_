from django.urls import path
from . import views
from .role_views import role_redirect_view

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('redirect/', role_redirect_view, name='role_redirect'),
    path('logout/', views.logout_view, name='logout'),
]
