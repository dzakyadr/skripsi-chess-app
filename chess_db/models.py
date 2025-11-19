# Di dalam chess_db/models.py

from django.db import models

class Game(models.Model):
    # --- Ini kita kembalikan, sangat penting untuk filter! ---
    RESULT_CHOICES = [
        ('1-0', 'Putih Menang'),
        ('0-1', 'Hitam Menang'),
        ('1/2-1/2', 'Remis'),
        ('*', 'Lainnya/Belum Selesai'),
    ]

    # Basic info (sudah bagus)
    event = models.CharField(max_length=100, blank=True, null=True)
    site = models.CharField(max_length=100, blank=True, null=True)
    game_date = models.DateField(blank=True, null=True) # Perubahan bagusmu tetap di sini
    round = models.CharField(max_length=10, blank=True, null=True)

    # Players (sudah bagus)
    white_player = models.CharField(max_length=100)
    black_player = models.CharField(max_length=100)
    white_elo = models.IntegerField(blank=True, null=True)
    black_elo = models.IntegerField(blank=True, null=True)

    result = models.CharField(
        max_length=10, 
        choices=RESULT_CHOICES, 
        blank=True, 
        null=True
    )
    pgn = models.TextField(help_text="Notasi permainan lengkap (PGN)")

    # Optional meta (sudah bagus)
    eco_code = models.CharField(max_length=10, blank=True, null=True)
    opening = models.CharField(max_length=150, blank=True, null=True)
    
    tags = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        # --- Kita buat jadi "Aman dari None" ---
        date_str = self.game_date.strftime('%Y-%m-%d') if self.game_date else '????'
        return f"{self.white_player} vs {self.black_player} ({date_str})"

    class Meta:
        ordering = ['-game_date']
        


class Meta:
    indexes = [
        models.Index(fields=['white_player']),
        models.Index(fields=['black_player']),
        models.Index(fields=['event']),
    ]
