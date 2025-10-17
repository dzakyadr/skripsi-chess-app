# Di dalam chess_db/urls.py

from django.urls import path
from . import views


urlpatterns = [
    # URL untuk halaman utama (daftar game), kita taruh di paling atas
    path('', views.game_list, name='game_list'), 
    
    # URL untuk upload yang sudah kita buat sebelumnya
    path('upload/', views.upload_pgn, name='upload_pgn'),
    
    path('game/<int:game_id>/', views.game_detail, name='game_detail'),
]