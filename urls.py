from django.urls import path
from . import views

urlpatterns = [
    path('add-site/', views.add_site, name='add_site'),
    path('login/', views.login_view, name='login'),
]