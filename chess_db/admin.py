# chess_db/admin.py

from django.contrib import admin
from .models import Game  # <-- Impor model Game yang baru kita buat

# Daftarkan model Game agar muncul di halaman admin

@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('white_player','black_player','game_date','result')
    search_fields = ('white_player','black_player','event','opening','pgn')
    list_filter = ('game_date','event')
