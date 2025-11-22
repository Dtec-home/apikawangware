from django.urls import path
from . import views

app_name = 'mpesa'

urlpatterns = [
    path('callback/', views.mpesa_callback, name='callback'),
]