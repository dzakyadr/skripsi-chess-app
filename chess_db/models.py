# chess_db/models.py

from django.db import models

class Game(models.Model):
    # Informasi umum tentang pertandingan
    event = models.CharField(max_length=100, blank=True, null=True, help_text="Nama turnamen atau event")
    site = models.CharField(max_length=100, blank=True, null=True, help_text="Lokasi pertandingan")
    game_date = models.DateField(help_text="Tanggal permainan dimainkan")
    round = models.CharField(max_length=10, blank=True, null=True, help_text="Babak ke berapa")

    # Informasi pemain
    white_player = models.CharField(max_length=100, help_text="Nama pemain Putih")
    black_player = models.CharField(max_length=100, help_text="Nama pemain Hitam")
    white_elo = models.IntegerField(blank=True, null=True, help_text="Rating ELO pemain Putih")
    black_elo = models.IntegerField(blank=True, null=True, help_text="Rating ELO pemain Hitam")

    # Hasil dan data permainan
    RESULT_CHOICES = [
        ('1-0', 'White Wins'),
        ('0-1', 'Black Wins'),
        ('1/2-1/2', 'Draw'),
        ('*', 'Ongoing/Unknown'),
    ]
    result = models.CharField(max_length=10, choices=RESULT_CHOICES, help_text="Hasil akhir permainan")
    
    # Kolom ini akan menyimpan seluruh notasi permainan dalam format PGN
    pgn = models.TextField(help_text="Notasi permainan lengkap dalam format PGN")

    # Informasi tambahan (opsional tapi sangat berguna)
    eco_code = models.CharField(max_length=10, blank=True, null=True, help_text="Kode ECO pembukaan catur")
    opening = models.CharField(max_length=150, blank=True, null=True, help_text="Nama pembukaan catur")

    # Timestamp otomatis
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.white_player} vs {self.black_player} ({self.game_date.year})"

    class Meta:
        ordering = ['-game_date'] # Urutkan permainan dari yang paling baru