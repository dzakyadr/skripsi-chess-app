from django.contrib import admin
from .models import Game, PlayerProfile, PlayerAlias

# --- 1. CONFIG PLAYER ALIAS (Agar bisa diedit di dalam Profil) ---
class PlayerAliasInline(admin.TabularInline):
    model = PlayerAlias
    extra = 1

# --- 2. ADMIN PLAYER PROFILE ---
@admin.register(PlayerProfile)
class PlayerProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'count_aliases')
    search_fields = ('name',)
    inlines = [PlayerAliasInline]

    def count_aliases(self, obj):
        return obj.aliases.count()
    count_aliases.short_description = "Jumlah Username"

# --- 3. ADMIN PLAYER ALIAS (Opsional, biar bisa cari via username) ---
@admin.register(PlayerAlias)
class PlayerAliasAdmin(admin.ModelAdmin):
    list_display = ('username', 'profile', 'platform')
    search_fields = ('username', 'profile__name')

# --- 4. ADMIN GAME ---
@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('white_player', 'black_player', 'result', 'game_date', 'event')
    list_filter = ('result', 'game_date')
    search_fields = ('white_player', 'black_player', 'event')
    ordering = ('-game_date',)