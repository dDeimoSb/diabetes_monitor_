from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='doctor_dashboard'),
    path('patients/attach/', views.attach_patient, name='doctor_attach_patient'),
    path('patients/<int:patient_id>/analytics/', views.patient_analytics, name='doctor_patient_analytics'),
    path('critical-events/', views.critical_events, name='doctor_critical_events'),
]
