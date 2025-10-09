# chess_db/admin.py

from django.contrib import admin
from .models import Game  # <-- Impor model Game yang baru kita buat

# Daftarkan model Game agar muncul di halaman admin
admin.site.register(Game)