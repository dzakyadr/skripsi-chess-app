# Di dalam chess_db/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import UploadPgnForm
from .models import Game
import chess.pgn
import io
from datetime import datetime
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q





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
                    break # Hentikan jika ada error di file

                if game_obj is None:
                    break  # Berhenti jika sudah tidak ada game lagi
                
                headers = game_obj.headers
                
                # --- Perbaikanmu yang bagus: Parsing ELO yang aman ---
                white_elo = int(headers.get('WhiteElo', 0)) if headers.get('WhiteElo', '').isdigit() else None
                black_elo = int(headers.get('BlackElo', 0)) if headers.get('BlackElo', '').isdigit() else None
                
                # --- Perbaikanmu yang bagus: Parsing Tanggal yang aman ---
                game_date = None
                date_str = headers.get('Date', '')
                try:
                    if date_str and '.' in date_str:
                        parts = date_str.split('.')
                        year = int(parts[0]) if parts[0].isdigit() else 1970 # Default jika '????'
                        month = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
                        day = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
                        game_date = datetime(year, month, day).date()
                except Exception:
                    pass # Biarkan game_date tetap None jika error

                # Simpan game ke database
                g = Game.objects.create(
                    event = headers.get('Event', ''),
                    site = headers.get('Site', ''),
                    game_date = game_date,
                    round = headers.get('Round', ''),
                    white_player = headers.get('White', 'Unknown'),
                    black_player = headers.get('Black', 'Unknown'),
                    white_elo = white_elo,
                    black_elo = black_elo,
                    result = headers.get('Result', '*'), # Cocokkan dengan model 'choices'
                    
                    # --- Ini kita perbaiki: simpan PGN per game, BUKAN file mentah ---
                    pgn = str(game_obj), 
                    
                    eco_code = headers.get('ECO',''),
                    opening = headers.get('Opening',''),
                )
                games_processed_count += 1
            
            if games_processed_count > 0:
                messages.success(request, f"Sukses! Berhasil mengimpor {games_processed_count} permainan.")
            else:
                messages.warning(request, "File PGN tidak valid atau tidak berisi permainan.")
            
            # --- Perbaikanmu yang bagus: redirect ke daftar game ---
            return redirect('game_list')
    
    else: # Ini adalah request GET (pertama kali buka halaman)
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

    fen_list = []
    try:
        pgn_io = io.StringIO(game.pgn)
        g = chess.pgn.read_game(pgn_io)
        board = g.board()
        fen_list.append(board.fen()) # Tambahkan posisi awal
        for m in g.mainline_moves():
            board.push(m)
            fen_list.append(board.fen())
    except Exception as e:
        print(f"Error parsing FEN list for game {game_id}: {e}") # Debug di server
        fen_list = []

    context = {
        'game': game,
        'fen_list': fen_list, # Kita kirim list FEN-nya
    }
    return render(request, 'chess_db/game_detail.html', context)