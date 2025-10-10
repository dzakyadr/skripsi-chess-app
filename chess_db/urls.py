# chess_db/urls.py (KODE YANG BENAR)

from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_pgn, name='upload_pgn'),
]