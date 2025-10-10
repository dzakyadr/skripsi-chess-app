# chess_db/views.py (KODE YANG BENAR)

from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import UploadPgnForm
from .models import Game
import chess.pgn
import io
from datetime import datetime

def upload_pgn(request):
    if request.method == 'POST':
        form = UploadPgnForm(request.POST, request.FILES)
        if form.is_valid():
            pgn_file = request.FILES['pgn_file']

            try:
                pgn_text = pgn_file.read().decode('utf-8')
                pgn_stream = io.StringIO(pgn_text)

                games_processed_count = 0
                while True:
                    game_data = chess.pgn.read_game(pgn_stream)
                    if game_data is None:
                        break

                    headers = game_data.headers

                    try:
                        game_date_obj = datetime.strptime(headers.get('Date', '????.??.??'), '%Y.%m.%d').date()
                    except ValueError:
                        game_date_obj = datetime.now().date()

                    try:
                        white_elo = int(headers.get('WhiteElo', 0))
                    except ValueError:
                        white_elo = None

                    try:
                        black_elo = int(headers.get('BlackElo', 0))
                    except ValueError:
                        black_elo = None

                    new_game = Game(
                        event=headers.get('Event', 'Unknown Event'),
                        site=headers.get('Site', '?'),
                        game_date=game_date_obj,
                        round=headers.get('Round', '?'),
                        white_player=headers.get('White', '?'),
                        black_player=headers.get('Black', '?'),
                        white_elo=white_elo,
                        black_elo=black_elo,
                        result=headers.get('Result', '*'),
                        eco_code=headers.get('ECO', '?'),
                        opening=headers.get('Opening', '?'),
                        pgn=str(game_data)
                    )
                    new_game.save()
                    games_processed_count += 1

                if games_processed_count > 0:
                    messages.success(request, f"Sukses! Berhasil mengimpor {games_processed_count} permainan catur.")
                else:
                    messages.warning(request, "File PGN valid, namun tidak ditemukan permainan di dalamnya.")

            except Exception as e:
                messages.error(request, f"Terjadi error saat memproses file: {e}")

            return redirect('upload_pgn')
    else:
        form = UploadPgnForm()

    return render(request, 'chess_db/upload_pgn.html', {'form': form})