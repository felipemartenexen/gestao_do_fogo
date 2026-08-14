from django.urls import path

from . import views

app_name = "firemap"

urlpatterns = [
    path("", views.map_page, name="map"),
    path("camadas/<slug:layer_id>/", views.layer_tiles, name="layer_tiles"),
    path("estatisticas/<slug:layer_id>/", views.layer_stats, name="layer_stats"),
    path("municipios/", views.municipalities, name="municipalities"),
]
