from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='patient_dashboard'),
    path('attachments/', views.attachments, name='patient_attachments'),
    path('entries/add/', views.add_entry, name='patient_add_entry'),
    path('entries/<int:entry_id>/edit/', views.edit_entry, name='patient_edit_entry'),
    path('entries/<int:entry_id>/delete/', views.delete_entry, name='patient_delete_entry'),
    path('history/', views.history, name='patient_history'),
    path('charts/', views.charts, name='patient_charts'),
]
