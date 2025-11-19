from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import UploadPgnForm, GameEditForm, GameNotesForm
from .models import Game
import chess.pgn
import io
from datetime import datetime
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.views.decorators.http import require_POST
from collections import defaultdict
import chess


def upload_pgn(request):
    if request.method == 'POST':
        form = UploadPgnForm(request.POST, request.FILES)
        if form.is_valid():
            pgn_file = request.FILES['pgn_file']

            # --- Perbaikanmu yang bagus: errors='ignore' ---
            raw_text = pgn_file.read().decode('utf-8', errors='ignore')
            pgn_io = io.StringIO(raw_text)

            games_processed_count = 0

            # --- INI KITA KEMBALIKAN: while loop agar bisa baca BANYAK game ---
            while True:
                try:
                    # Kita baca game satu per satu dari file
                    game_obj = chess.pgn.read_game(pgn_io)
                except Exception as e:
                    messages.error(request, f"Error saat parsing PGN: {e}")
                    break  # Hentikan jika ada error di file

                if game_obj is None:
                    break  # Berhenti jika sudah tidak ada game lagi

                headers = game_obj.headers

                # --- Perbaikanmu yang bagus: Parsing ELO yang aman ---
                white_elo = int(headers.get('WhiteElo', 0)) if headers.get(
                    'WhiteElo', '').isdigit() else None
                black_elo = int(headers.get('BlackElo', 0)) if headers.get(
                    'BlackElo', '').isdigit() else None

                # --- Perbaikanmu yang bagus: Parsing Tanggal yang aman ---
                game_date = None
                date_str = headers.get('Date', '')
                try:
                    if date_str and '.' in date_str:
                        parts = date_str.split('.')
                        year = int(parts[0]) if parts[0].isdigit(
                        ) else 1970  # Default jika '????'
                        month = int(parts[1]) if len(
                            parts) > 1 and parts[1].isdigit() else 1
                        day = int(parts[2]) if len(
                            parts) > 2 and parts[2].isdigit() else 1
                        game_date = datetime(year, month, day).date()
                except Exception:
                    pass  # Biarkan game_date tetap None jika error

                # Simpan game ke database
                g = Game.objects.create(
                    event=headers.get('Event', ''),
                    site=headers.get('Site', ''),
                    game_date=game_date,
                    round=headers.get('Round', ''),
                    white_player=headers.get('White', 'Unknown'),
                    black_player=headers.get('Black', 'Unknown'),
                    white_elo=white_elo,
                    black_elo=black_elo,
                    # Cocokkan dengan model 'choices'
                    result=headers.get('Result', '*'),

                    # --- Ini kita perbaiki: simpan PGN per game, BUKAN file mentah ---
                    pgn=str(game_obj),

                    eco_code=headers.get('ECO', ''),
                    opening=headers.get('Opening', ''),
                )
                games_processed_count += 1

            if games_processed_count > 0:
                messages.success(
                    request, f"Sukses! Berhasil mengimpor {games_processed_count} permainan.")
            else:
                messages.warning(
                    request, "File PGN tidak valid atau tidak berisi permainan.")

            # --- Perbaikanmu yang bagus: redirect ke daftar game ---
            return redirect('game_list')

    else:  # Ini adalah request GET (pertama kali buka halaman)
        form = UploadPgnForm()
    return render(request, 'chess_db/upload_pgn.html', {'form': form})

# --- Fungsi ini sudah bagus, tidak perlu diubah ---


def game_list(request):
    # Ambil semua game
    qs = Game.objects.all()

    # ---------------------------------------------------------
    # 1) Search (Pencarian) - BAGIAN INI TETAP SAMA
    # ---------------------------------------------------------
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(white_player__icontains=q) |
            Q(black_player__icontains=q) |
            Q(event__icontains=q) |
            Q(opening__icontains=q)
        )

    # ---------------------------------------------------------
    # 2) Sorting (Pengurutan) - BAGIAN INI KITA UBAH TOTAL
    # ---------------------------------------------------------
    # Kita tidak lagi pakai 'order' (asc/desc) terpisah.
    # Kita gabungkan logikanya dalam satu kamus (dictionary).
    
    sort_param = request.GET.get('sort', 'newest') # Default: 'newest'

    sort_options = {
        'newest': '-game_date',      # Terbaru (Tanggal Descending)
        'oldest': 'game_date',       # Terlama (Tanggal Ascending)
        'white_az': 'white_player',  # Putih A-Z
        'white_za': '-white_player', # Putih Z-A
        'black_az': 'black_player',  # Hitam A-Z
        'black_za': '-black_player', # Hitam Z-A
        'event_az': 'event',         # Event A-Z
        'id': '-id',                 # ID (Default fallback)
    }

    # Ambil nama kolom dari kamus. Jika tidak ketemu, pakai '-game_date'
    order_by_field = sort_options.get(sort_param, '-game_date')
    
    # Terapkan pengurutan
    qs = qs.order_by(order_by_field)

    # ---------------------------------------------------------
    # 3) Pagination (Halaman) - BAGIAN INI TETAP SAMA
    # ---------------------------------------------------------
    try:
        per_page = int(request.GET.get('per_page', 10))
        if per_page <= 0 or per_page > 200:
            per_page = 10
    except (ValueError, TypeError):
        per_page = 10

    paginator = Paginator(qs, per_page)
    page = request.GET.get('page', 1)
    
    try:
        games_page = paginator.page(page)
    except PageNotAnInteger:
        games_page = paginator.page(1)
    except EmptyPage:
        games_page = paginator.page(paginator.num_pages)

    # 4) Offset untuk nomor urut global
    try:
        current_page_number = int(games_page.number)
    except Exception:
        current_page_number = 1
    offset = (current_page_number - 1) * per_page

    # ---------------------------------------------------------
    # 5) Context - KITA UPDATE SEDIKIT
    # ---------------------------------------------------------
    context = {
        'games': games_page,
        'q': q,
        'sort': sort_param,  # Kita kirim nilai sort (misal: 'newest', 'white_az')
        # 'order': order,    <-- HAPUS INI (Sudah tidak dipakai)
        'per_page': per_page,
        'paginator': paginator,
        'offset': offset,
    }
    
    return render(request, 'chess_db/game_list.html', context)



def game_detail(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    
    if request.method == 'POST':
        # Cek apakah ini POST untuk notes (kita pakai instance=game agar dia meng-update, bukan membuat baru)
        notes_form = GameNotesForm(request.POST, instance=game)
        if notes_form.is_valid():
            notes_form.save()
            messages.success(request, "Catatan berhasil disimpan!")
            return redirect('game_detail', game_id=game.id) # Refresh halaman
    else:
        # Jika cuma melihat, isi form dengan notes yang sudah ada di database
        notes_form = GameNotesForm(instance=game)

    # Kita akan siapkan daftar yang lebih canggih
    # Isinya bukan cuma FEN, tapi [nomor_langkah, notasi, FEN]
    move_data_list = []
    
    try:
        pgn_io = io.StringIO(game.pgn)
        g = chess.pgn.read_game(pgn_io)
        board = g.board() # Ini adalah "otak" catur virtual

        # 1. Tambahkan POSISI AWAL (index 0)
        move_data_list.append({
            "move_number": "Start",
            "notation": "Posisi Awal",
            "fen": board.fen(),
            "from": None, # <-- TAMBAHKAN INI
            "to": None    # <-- TAMBAHKAN INI
        })

        # 2. Loop semua langkah di PGN
        for move in g.mainline_moves():
            if board.turn == chess.WHITE:
                move_number_str = f"{board.fullmove_number}."
            else:
                move_number_str = f"{board.fullmove_number}..."

            notation_str = board.san(move)
            
            # --- AMBIL KOORDINAT GERAKAN ---
            from_sq = chess.square_name(move.from_square) # misal: "e2"
            to_sq = chess.square_name(move.to_square)     # misal: "e4"
            
            board.push(move)

            # Simpan semua data
            move_data_list.append({
                "move_number": move_number_str,
                "notation": notation_str,
                "fen": board.fen(),
                "from": from_sq, # <-- KIRIM KE TEMPLATE
                "to": to_sq      # <-- KIRIM KE TEMPLATE
            })

    except Exception as e:
        print(f"Error: {e}")
        move_data_list = []

    context = {
        'game': game,
        'move_data_list': move_data_list, 
    }
    return render(request, 'chess_db/game_detail.html', context)


def game_edit(request, game_id):
    # Ambil game yang mau diedit, atau tampilkan 404 jika tidak ada
    game = get_object_or_404(Game, pk=game_id)

    if request.method == 'POST':
        # Jika pengguna MENYIMPAN form (request POST)
        form = GameEditForm(request.POST, instance=game)
        if form.is_valid():
            form.save()  # Simpan perubahan ke database
            messages.success(request, "Game berhasil diperbarui!")
            # Kembali ke halaman detail
            return redirect('game_detail', game_id=game.id)
    else:
        form = GameEditForm(instance=game)

    context = {
        'form': form,
        'game': game
    }
    return render(request, 'chess_db/game_edit.html', context)


@require_POST
def game_delete(request, game_id):
    game = get_object_or_404(Game, pk=game_id)

    game_title = f"{game.white_player} vs {game.black_player}"
    game.delete()

    messages.success(request, f"Game '{game_title}' telah berhasil dihapus.")

    return redirect('game_list')
def opening_explorer(request):
    all_games = Game.objects.all()
    move_stats = defaultdict(lambda: {
        'total': 0, 'wins': 0, 'draws': 0, 'losses': 0
    })

    board = chess.Board() 

    for game in all_games:
        pgn_io = io.StringIO(game.pgn)
        try:
            game_obj = chess.pgn.read_game(pgn_io)
            if not game_obj:
                continue
            # Cara baru yang lebih aman:
            moves = list(game_obj.mainline_moves())
            if not moves:
                continue 
            first_move = moves[0]

            if first_move:
                move_san = board.san(first_move)
                stats = move_stats[move_san]
                stats['total'] += 1

                if game.result == '1-0':
                    stats['wins'] += 1
                elif game.result == '0-1':
                    stats['losses'] += 1
                elif game.result == '1/2-1/2':
                    stats['draws'] += 1
        except Exception as e:
            print(f"Skipping game {game.id} due to parsing error: {e}")

    stats_list = []
    for move_san, data in move_stats.items():
        stats_list.append({
            'move': move_san,
            'total': data['total'],
            'wins': data['wins'],
            'draws': data['draws'],
            'losses': data['losses'],
        })

    context = {
        'stats_list': stats_list
    }

    return render(request, 'chess_db/opening_explorer.html', context)
