from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.views.generic import RedirectView

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('domains/', views.list_domains, name='list_domains'),
    path('domains/<int:domain_id>/', views.domain_detail, name='domain_detail'),
    path('add-site/', views.add_site, name='add_site'),
    path('users/', views.list_users, name='list_users'),
    path('add-user/', views.add_user, name='add_user'),
    path('', RedirectView.as_view(url='/login/', permanent=False)),
]
