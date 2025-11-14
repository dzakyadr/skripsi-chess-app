from django import forms
from .models import Game

class UploadPgnForm(forms.Form):
    pgn_file = forms.FileField(label="Pilih File PGN (.pgn)")
    
class GameEditForm(forms.ModelForm):
    class Meta:
        model = Game
        fields = [
            'event', 'site', 'game_date', 'round',
            'white_player', 'black_player', 'white_elo', 'black_elo',
            'result', 'eco_code', 'opening'
        ]
        
        widgets = {
            'game_date': forms.DateInput(attrs={'type': 'date'}),
        }