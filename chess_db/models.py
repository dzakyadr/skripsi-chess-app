from django.db import models

class Game(models.Model):
    RESULT_CHOICES = [
        ('1-0', 'Putih Menang'),
        ('0-1', 'Hitam Menang'),
        ('1/2-1/2', 'Remis'),
        ('*', 'Lainnya/Belum Selesai'),
    ]

    event = models.CharField(max_length=100, blank=True, null=True)
    site = models.CharField(max_length=100, blank=True, null=True)
    game_date = models.DateField(blank=True, null=True)
    round = models.CharField(max_length=10, blank=True, null=True)

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

    eco_code = models.CharField(max_length=10, blank=True, null=True)
    opening = models.CharField(max_length=150, blank=True, null=True)    
    tags = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
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
    
    
class PlayerProfile(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="Nama asli atau nama utama")
    
    def __str__(self):
        return self.name

# 3. MODEL ALIAS (INI JUGA)
class PlayerAlias(models.Model):
    profile = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE, related_name='aliases')
    username = models.CharField(max_length=100, help_text="Username di PGN (misal: DrNykterstein)")
    platform = models.CharField(max_length=50, blank=True, null=True)
    
    def __str__(self):
        return f"{self.username} -> {self.profile.name}"
