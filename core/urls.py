from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('materials/', views.materials, name='materials'),
    path('prediabetes-test/', views.prediabetes_test, name='prediabetes_test'),
    path('profile/', views.profile, name='profile'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('export/', views.export_data, name='export'),
]
