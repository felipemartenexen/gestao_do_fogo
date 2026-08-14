from django.urls import path

from . import access, views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("acesso/", access.access_control, name="access_control"),
    path("acesso/<int:user_id>/", access.update_user, name="update_user"),
]
