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
            'result', 'eco_code', 'opening', 'tags'
        ]
        
        widgets = {
            'game_date': forms.DateInput(attrs={'type': 'date'}),
            'tags': forms.TextInput(attrs={'placeholder': '#Taktik, #Blunder'}),
            'notes': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Tulis catatan atau analisismu di sini...'}),
        }
        
class GameNotesForm(forms.ModelForm):
    class Meta:
        model = Game
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={
                'rows': 4, 
                'placeholder': 'Tulis analisis atau catatanmu di sini...',
                'style': 'width: 100%; padding: 10px; border-radius: 4px; border: 1px solid #ccc;'
            }),
        }
        labels = {
            'notes': '' # Kita hilangkan label teks "Notes" agar lebih bersih
        }