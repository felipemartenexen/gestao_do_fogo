from django.urls import path

from . import views

app_name = "content"

urlpatterns = [
    path("", views.news_list, name="news_list"),
    path("nova/", views.news_create, name="news_create"),
    path("<int:page_id>/", views.news_edit, name="news_edit"),
    path("<int:page_id>/publicacao/", views.news_toggle, name="news_toggle"),
]
