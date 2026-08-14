from django.urls import path

from . import views

app_name = "researchers"

urlpatterns = [
    path("", views.researcher_list, name="list"),
    path("mapa/dados/", views.researcher_map_data, name="map_data"),
    # a edição em si acontece em /users/profile/; estas rotas existem para links antigos
    # continuarem funcionando e para o POST da seção de pesquisador
    path("meu-perfil/", views.my_profile, name="my_profile"),
    path("meu-perfil/salvar/", views.save_profile, name="save_profile"),
    path("<slug:slug>/", views.researcher_detail, name="detail"),
]
