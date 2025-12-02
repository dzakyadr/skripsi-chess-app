# Di dalam chess_db/urls.py

from django.urls import path
from . import views


urlpatterns = [
    path('', views.game_list, name='game_list'), 
    
    path('upload/', views.upload_pgn, name='upload_pgn'),
    
    path('game/<int:game_id>/', views.game_detail, name='game_detail'),
    
    path('game/<int:game_id>/edit/', views.game_edit, name='game_edit'),
    
    path('game/<int:game_id>/delete/', views.game_delete, name='game_delete'),
    
    path('explorer/', views.opening_explorer, name='opening_explorer'),
    
    path('analysis/', views.analysis_board, name='analysis_board'),
    
    path('api/opening-stats/', views.api_opening_stats, name='api_opening_stats'),
]
    
