from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import UploadPgnForm, GameEditForm, GameNotesForm
import chess.pgn
from collections import Counter
import io
from datetime import datetime
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.views.decorators.http import require_POST
from collections import defaultdict
import chess
from django.http import JsonResponse
from .models import Game, PlayerProfile, PlayerAlias
from .eco_data import get_opening_name 

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

def game_list(request):
    qs = Game.objects.all()

    # --- 1. SEARCH BY FEN (LOGIKA BARU) ---
    # Ini untuk menangkap request dari Opening Explorer / Analysis Board
    fen_query = request.GET.get('fen', '').strip()
    
    if fen_query and fen_query != 'start':
        # Kita harus mencari game yang pernah melewati posisi ini.
        # Karena database kita menyimpan PGN (bukan FEN per langkah), kita harus scan manual.
        # (Catatan: Ini mungkin agak lambat jika databasenya ribuan, tapi ini solusi terbaik tanpa ubah model)
        
        matching_ids = []
        # Ambil bagian posisi bidak saja (sebelum spasi pertama) agar pencarian fleksibel
        target_board_fen = fen_query.split(' ')[0] 
        
        board = chess.Board()

        # Optimasi: Batasi pencarian ke 1000 game terbaru dulu supaya tidak loading lama
        # Kalau mau cari semua, hapus [:1000]
        games_to_scan = qs.order_by('-game_date')[:1000] 

        for game in games_to_scan:
            try:
                pgn_io = io.StringIO(game.pgn)
                game_obj = chess.pgn.read_game(pgn_io)
                
                if game_obj:
                    board.reset()
                    # Cek posisi awal
                    if board.fen().split(' ')[0] == target_board_fen:
                        matching_ids.append(game.id)
                        continue

                    # Cek setiap langkah dalam game
                    for move in game_obj.mainline_moves():
                        board.push(move)
                        if board.fen().split(' ')[0] == target_board_fen:
                            matching_ids.append(game.id)
                            break # Ketemu! Lanjut ke game berikutnya
            except:
                continue
        
        # Filter QuerySet agar HANYA menampilkan game yang cocok
        qs = qs.filter(id__in=matching_ids)

    # --- 2. SEARCH BIASA (Nama, Event, dll) ---
    q = request.GET.get('q', '').strip()
    if q:
        # A. Cek apakah 'q' cocok dengan Profil/Alias di database?
        profiles = PlayerProfile.objects.filter(
            Q(name__icontains=q) | 
            Q(aliases__username__icontains=q)
        ).distinct()

        # B. Kumpulkan semua nama target
        target_names = set()
        
        if profiles.exists():
            # Kalau ketemu profil resmi, ambil SEMUA nama panggilannya
            for prof in profiles:
                target_names.add(prof.name)
                for alias in prof.aliases.all():
                    target_names.add(alias.username)
        else:
            # Kalau tidak ada profil, cari teks apa adanya
            target_names.add(q)
        
        # C. Susun Query Database
        # Kita mencari game yang:
        # 1. Pemainnya ada di daftar 'target_names' (Smart Search)
        # 2. ATAU Event/Opening mengandung teks 'q' (Search Biasa)
        
        search_query = Q()
        
        # Filter Pemain (Cerdas)
        for name in target_names:
            search_query |= Q(white_player__icontains=name) | Q(black_player__icontains=name)
            
        # Filter Metadata lain (Event/Opening) - Tetap pakai teks asli user 'q'
        search_query |= Q(event__icontains=q) | Q(opening__icontains=q)
        
        # Terapkan filter
        qs = qs.filter(search_query)

    # --- 3. SORTING ---
    sort_param = request.GET.get('sort', 'newest')
    sort_options = {
        'newest': '-game_date',
        'oldest': 'game_date',
        'white_az': 'white_player',
        'white_za': '-white_player',
        'black_az': 'black_player',
        'black_za': '-black_player',
        'event_az': 'event',
        'id': '-id',
    }
    order_by_field = sort_options.get(sort_param, '-game_date')
    qs = qs.order_by(order_by_field)

    # --- 4. PAGINATION ---
    try:
        per_page = int(request.GET.get('per_page', 10))
        if per_page <= 0 or per_page > 200: per_page = 10
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

    # Hitung offset untuk penomoran tabel
    try:
        current_page_number = int(games_page.number)
    except:
        current_page_number = 1
    offset = (current_page_number - 1) * per_page

    context = {
        'games': games_page,
        'q': q,
        'sort': sort_param,
        'per_page': per_page,
        'paginator': paginator,
        'offset': offset,
        'fen_query': fen_query, # Kirim data FEN ke template (untuk info alert)
    }
    
    return render(request, 'chess_db/game_list.html', context)


def analysis_board(request):
    # 1. Cek parameter di URL
    game_id = request.GET.get('game_id')
    fen_input = request.GET.get('fen')
    
    initial_pgn = None
    initial_fen = None

    # 2. Logika Pengambilan Data
    if game_id:
        # Hanya ambil PGN jika ada ID valid
        game_obj = get_object_or_404(Game, pk=game_id)
        initial_pgn = game_obj.pgn
    elif fen_input:
        # Hanya ambil FEN jika ada parameter fen
        initial_fen = fen_input
    
    # Jika tidak ada game_id dan tidak ada fen,
    # maka initial_pgn dan initial_fen AKAN TETAP None (Kosong).
    
    context = {
        'initial_pgn': initial_pgn,
        'initial_fen': initial_fen
    }
    return render(request, 'chess_db/analysis_board.html', context)

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
    # 1. Parameter Filter
    opponent_name = request.GET.get('opponent', '').strip()
    user_color = request.GET.get('color', '') 
    current_fen = request.GET.get('fen', 'start')
    
    # 2. Setup Board
    board = chess.Board()
    if current_fen != 'start':
        try:
            board.set_fen(current_fen)
        except ValueError:
            board.reset()

    # Info Giliran
    turn_color = 'white' if board.turn == chess.WHITE else 'black'
    move_number = board.fullmove_number

    # 3. Filter Database (Sama seperti sebelumnya)
    hero_name = "You"
    villain_name = opponent_name if opponent_name else "Global Stats"
    scenario_text = ""
    is_opponent_turn = False

    if opponent_name:
        if user_color == 'white':
            games = Game.objects.filter(black_player__icontains=opponent_name)
            scenario_text = f"Giliranmu (Putih) vs {opponent_name}." if turn_color == 'white' else f"Giliran {opponent_name} (Hitam)."
            is_opponent_turn = (turn_color == 'black')
        elif user_color == 'black':
            games = Game.objects.filter(white_player__icontains=opponent_name)
            scenario_text = f"Giliran {opponent_name} (Putih)." if turn_color == 'white' else f"Giliranmu (Hitam) vs {opponent_name}."
            is_opponent_turn = (turn_color == 'white')
        else:
            games = Game.objects.filter(Q(white_player__icontains=opponent_name) | Q(black_player__icontains=opponent_name))
            scenario_text = f"Statistik umum {opponent_name}."
            is_opponent_turn = True 
    else:
        games = Game.objects.all()
        scenario_text = f"Statistik Global Database."
        is_opponent_turn = False

    # 4. Hitung Statistik & CARI GAME TERKAIT (Update di sini)
    target_games = games.order_by('-game_date')[:500] # Batasi 500 game terbaru biar cepat
    
    stats_data = {} 
    matching_games = [] # <-- LIST BARU UNTUK MENYIMPAN GAME
    
    root_fen_base = board.fen().split(' ')[0]

    for game in target_games:
        try:
            pgn_io = io.StringIO(game.pgn)
            chess_game = chess.pgn.read_game(pgn_io)
            if not chess_game: continue
            
            game_board = chess_game.board()
            found_position = False # Penanda apakah game ini melewati posisi tersebut
            next_move = None
            
            if current_fen == 'start':
                found_position = True
                moves = list(chess_game.mainline_moves())
                if moves: next_move = moves[0]
            else:
                # Replay
                for move in chess_game.mainline_moves():
                    if game_board.fen().split(' ')[0] == root_fen_base:
                        found_position = True
                        next_move = move
                        break
                    game_board.push(move)
            
            # JIKA POSISI COCOK:
            if found_position:
                # A. Masukkan ke daftar 'Matching Games' (Batasi 10 saja biar UI gak penuh)
                #if len(matching_games) < 10:
                 #   matching_games.append(game)

                # B. Hitung Statistik Langkah Selanjutnya
                if next_move:
                    move_san = game_board.san(next_move)
                    result = game.result
                    
                    if move_san not in stats_data:
                        stats_data[move_san] = {'move': move_san, 'total': 0, 'wins': 0, 'draws': 0, 'losses': 0}
                    
                    stats_data[move_san]['total'] += 1
                    if result == '1-0': stats_data[move_san]['wins'] += 1
                    elif result == '0-1': stats_data[move_san]['losses'] += 1
                    else: stats_data[move_san]['draws'] += 1
                    
        except Exception:
            continue
            
    stats_list = sorted(stats_data.values(), key=lambda x: x['total'], reverse=True)

    context = {
        'stats_list': stats_list,
        'scenario_text': scenario_text,
        'opponent_name': opponent_name,
        'is_opponent_turn': is_opponent_turn,
        'move_number': move_number,
        'turn_color': turn_color.capitalize()
    }
    return render(request, 'chess_db/opening_explorer.html', context)

def api_opening_stats(request):
    """
    API Opening Explorer dengan Fitur SMART ALIASING.
    """
    fen = request.GET.get('fen', 'start')
    opponent = request.GET.get('opponent', '').strip()
    user_color = request.GET.get('color', '')

    # 1. Setup Papan
    board = chess.Board()
    if fen != 'start':
        try:
            board.set_fen(fen)
        except ValueError:
            return JsonResponse({'error': 'Invalid FEN'}, status=400)
    
    root_fen_base = board.fen().split(' ')[0]
    
    eco_code, opening_name = get_opening_name(board.fen())
    
    if not opening_name:
        opening_name = "Unknown Opening"
        eco_code = "-"

    # 2. FILTER GAME (BAGIAN INI KITA UPDATE JADI PINTAR)
    games = Game.objects.all()

    if opponent:
        # --- LOGIKA PENYATUAN AKUN (ALIASING) ---
        # Langkah A: Cari apakah nama yang diketik user ada di tabel Profil/Alias?
        # Kita cari Profil yang namanya mirip ATAU punya alias yang mirip input user
        profiles = PlayerProfile.objects.filter(
            Q(name__icontains=opponent) | 
            Q(aliases__username__icontains=opponent)
        ).distinct()

        # Langkah B: Kumpulkan semua nama panggilan (Username) yang mungkin
        target_names = set() # Pakai set biar tidak ada nama dobel
        
        if profiles.exists():
            # Kalau ketemu Profil resmi, ambil semua alias-nya
            for prof in profiles:
                target_names.add(prof.name) # Masukkan nama asli (misal "Dzaky Adrian")
                for alias in prof.aliases.all():
                    target_names.add(alias.username) # Masukkan semua alias (vestnik713, dzakuy)
        else:
            # Kalau tidak ketemu di database alias, ya cari nama itu aja apa adanya
            target_names.add(opponent)
        
        # Langkah C: Bikin Query Database Game
        # Kita akan cari game dimana nama pemainnya COCOK dengan SALAH SATU dari target_names
        # Contoh Query: (White="vestnik713") OR (White="dzakuy") ...
        
        query_player = Q()
        for name in target_names:
            if user_color == 'white':
                # Kita Putih, Cari Lawan (Hitam) yang namanya ada di daftar
                query_player |= Q(black_player__icontains=name)
            elif user_color == 'black':
                # Kita Hitam, Cari Lawan (Putih) yang namanya ada di daftar
                query_player |= Q(white_player__icontains=name)
            else:
                # Cari di kedua sisi
                query_player |= Q(white_player__icontains=name) | Q(black_player__icontains=name)
        
        # Terapkan filter pintar ini
        games = games.filter(query_player)

    # 3. Hitung Statistik (Sama seperti sebelumnya, tidak berubah)
    target_games = games.order_by('-game_date')[:1000]
    stats_data = {}
    
    for game in target_games:
        try:
            # Optimasi: Cek string PGN dulu
            #if root_fen_base not in game.pgn and fen != 'start': 
             #   continue 

            pgn_io = io.StringIO(game.pgn)
            chess_game = chess.pgn.read_game(pgn_io)
            if not chess_game: continue

            game_board = chess_game.board()
            next_move = None
            
            if fen == 'start':
                moves = list(chess_game.mainline_moves())
                if moves: next_move = moves[0]
            else:
                match = False
                for move in chess_game.mainline_moves():
                    if game_board.fen().split(' ')[0] == root_fen_base:
                        match = True
                        next_move = move
                        break
                    game_board.push(move)
                if not match: continue

            if next_move:
                move_san = game_board.san(next_move)
                result = game.result
                
                if move_san not in stats_data:
                    stats_data[move_san] = {'move': move_san, 'total': 0, 'wins': 0, 'draws': 0, 'losses': 0}
                
                stats_data[move_san]['total'] += 1
                if result == '1-0': stats_data[move_san]['wins'] += 1
                elif result == '0-1': stats_data[move_san]['losses'] += 1
                else: stats_data[move_san]['draws'] += 1

        except Exception:
            continue

    stats_list = sorted(stats_data.values(), key=lambda x: x['total'], reverse=True)
    
    
    # Kirim juga info nama siapa saja yang dicari (untuk debug/info)
    debug_names = list(target_names) if opponent else []
    
    current_board_fen = board.fen() 
    
    # Panggil fungsi debug tadi
    eco_code, opening_name = get_opening_name(current_board_fen)
    # ...
    
    return JsonResponse({
        'stats': stats_list,
        'searched_aliases': list(target_names) if opponent else [], # (Kalau kamu pakai logika alias)
        'opening': {'code': eco_code, 'name': opening_name} # <-- KIRIM DATA INI
    })