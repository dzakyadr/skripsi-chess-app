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
    
    path('games/advanced/', views.advanced_search, name='advanced_search'), 
    
    path('games/bulk-delete/', views.game_bulk_delete, name='game_bulk_delete'),
    
    path('api/identify-opening/', views.api_identify_opening, name='api_identify_opening'),
    
    path('analysis/save/', views.save_analysis, name='save_analysis'),
]
    
