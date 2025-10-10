from django import forms

class UploadPgnForm(forms.Form):
    pgn_file = forms.FileField(label="Pilih File PGN (.pgn)")