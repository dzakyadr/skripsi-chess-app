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
    """
    Dukungan query params:
      - q: search string (search in white_player, black_player, event, opening)
      - sort: field to sort by (created, date, event, white, black, id)
      - order: asc atau desc
      - page: nomor halaman
      - per_page: items per page (default 10)
    """
    qs = Game.objects.all()

    # 1) Search
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(white_player__icontains=q) |
            Q(black_player__icontains=q) |
            Q(event__icontains=q) |
            Q(opening__icontains=q)
        )

    # 2) Sorting
    allowed_sorts = {
        'id': 'id',
        'event': 'event',
        'white': 'white_player',
        'black': 'black_player',
        'date': 'game_date',
        'created': 'created_at',
    }
    sort = request.GET.get('sort', 'created')   # default: latest by created_at
    sort_field = allowed_sorts.get(sort, 'created_at')
    order = request.GET.get('order', 'desc')
    if order == 'asc':
        qs = qs.order_by(sort_field)
    else:
        qs = qs.order_by('-' + sort_field)

    # 3) Pagination
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

    # 4) offset untuk nomor urut global (pertama item index di halaman ini)
    try:
        current_page_number = int(games_page.number)
    except Exception:
        current_page_number = 1
    offset = (current_page_number - 1) * per_page

    context = {
        'games': games_page,          # paginated page object
        'q': q,
        'sort': sort,
        'order': order,
        'per_page': per_page,
        'paginator': paginator,
        'offset': offset,            # kirim offset ke template
    }
    return render(request, 'chess_db/game_list.html', context)

# --- Fungsi cerdas barumu, kita pertahankan! ---


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
            "fen": board.fen()
        })

        # 2. Loop semua langkah di PGN
        for move in g.mainline_moves():
            # Tentukan nomor langkah (misal: "1." atau "1...")
            move_number_str = ""
            if board.turn == chess.WHITE:
                move_number_str = f"{board.fullmove_number}."
            else:
                move_number_str = f"{board.fullmove_number}..."

            # Dapatkan notasi (misal: "e4" atau "Nf3")
            notation_str = board.san(move)

            # Lakukan langkah di papan virtual
            board.push(move)

            # Simpan semua data
            move_data_list.append({
                "move_number": move_number_str,
                "notation": notation_str,
                "fen": board.fen()
            })

    except Exception as e:
        print(f"Error parsing FEN/Move list for game {game_id}: {e}")
        move_data_list = [] # Kosongkan jika ada error

    context = {
        'game': game,
        'notes_form': notes_form,
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
