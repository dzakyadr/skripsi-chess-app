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
from datetime import datetime

#Upload PGN
def upload_pgn(request):
    if request.method == 'POST':
        form = UploadPgnForm(request.POST, request.FILES)
        if form.is_valid():
            pgn_file = request.FILES['pgn_file']
            # CEK FORMAT
            filename = pgn_file.name.lower() #biar .PGN juga bisa 
            if not filename.endswith('.pgn'):
                messages.warning(
                    request, "File PGN tidak valid atau tidak berisi permainan.")
                return redirect('game_list')
            try:
                raw_text = pgn_file.read().decode('utf-8', errors='ignore').replace('\x00', '')
                #decode dengan 'ignore' untuk menghindari error karakter 
                #replace untuk jaga-jaga ada null byte biar db tidak error
            except Exception as e:
                messages.error(request, "File rusak atau tidak terbaca.")
                return redirect('game_list')

            pgn_io = io.StringIO(raw_text) #untuk dibaca python-chess 
            games_processed_count = 0

            while True:
                try:
                    game_obj = chess.pgn.read_game(pgn_io)
                except Exception as e:
                    messages.error(request, f"Error saat parsing PGN: {e}")
                    break  # berhenti jika ada error di file

                if game_obj is None:
                    break  # Berhenti jika sudah tidak ada game lagi

                headers = game_obj.headers

                white_elo = int(headers.get('WhiteElo', 0)) if headers.get(
                    'WhiteElo', '').isdigit() else None
                black_elo = int(headers.get('BlackElo', 0)) if headers.get(
                    'BlackElo', '').isdigit() else None

                game_date = None #none biar dicari di pgn dl
                date_str = headers.get('Date', '')
                try:
                    if date_str and '.' in date_str:
                        parts = date_str.split('.')
                        year = int(parts[0]) if parts[0].isdigit(
                        ) else 1970 
                        month = int(parts[1]) if len(
                            parts) > 1 and parts[1].isdigit() else 1
                        day = int(parts[2]) if len(
                            parts) > 2 and parts[2].isdigit() else 1
                        game_date = datetime(year, month, day).date()
                except Exception:
                    pass 

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
                    result=headers.get('Result', '*'),
                    pgn=str(game_obj),
                    eco_code=headers.get('ECO', ''),
                    opening=headers.get('Opening', ''),
                )
                games_processed_count += 1

            if games_processed_count > 0:
                messages.success(
                    request, f"Berhasil upload {games_processed_count} permainan.")
            else:
                messages.warning(
                    request, "File PGN tidak valid atau tidak berisi permainan.")

            return redirect('game_list')

    else:  
        form = UploadPgnForm()
    return render(request, 'chess_db/upload_pgn.html', {'form': form})

#game list
def game_list(request):
    qs = Game.objects.all()

    def get_aliases(name_query):
        names = {name_query}
        profiles = PlayerProfile.objects.filter(
            Q(name__icontains=name_query) | 
            Q(aliases__username__icontains=name_query)
            #icontains i hurus besar kecil sama contains yg mengandung
        ).distinct()
        
        for prof in profiles:
            names.add(prof.name)
            for alias in prof.aliases.all():
                names.add(alias.username)
        return names

    #filter posisi fen dari openings explorer
    fen_query = request.GET.get('fen', '').strip()
    if fen_query and fen_query != 'start':
        matching_ids = []
        target_board_fen = fen_query.split(' ')[0]
        board = chess.Board()
        games_to_scan = qs.order_by('-game_date')[:2000] 

        for game in games_to_scan:
            try:
                pgn_io = io.StringIO(game.pgn)
                game_obj = chess.pgn.read_game(pgn_io)
                if game_obj:
                    board.reset()
                    if board.fen().split(' ')[0] == target_board_fen:
                        matching_ids.append(game.id)
                        continue
                    for move in game_obj.mainline_moves():
                        board.push(move)
                        if board.fen().split(' ')[0] == target_board_fen:
                            matching_ids.append(game.id)
                            break 
            except:
                continue
        qs = qs.filter(id__in=matching_ids)

    #advanced search
    white_filter = request.GET.get('white', '').strip()
    black_filter = request.GET.get('black', '').strip()
    ignore_color = request.GET.get('ignore_color')

    if white_filter:
        aliases = get_aliases(white_filter)
        q_obj = Q()
        for name in aliases:
            if ignore_color:
                q_obj |= Q(white_player__icontains=name) | Q(black_player__icontains=name)
            else:
                q_obj |= Q(white_player__icontains=name)
        qs = qs.filter(q_obj)

    if black_filter and not ignore_color:
        aliases = get_aliases(black_filter)
        q_obj = Q()
        for name in aliases:
            q_obj |= Q(black_player__icontains=name)
        qs = qs.filter(q_obj)

    #filter metadata
    result = request.GET.get('result')
    if result: qs = qs.filter(result=result)
    
    elo_min = request.GET.get('elo_min')
    if elo_min: qs = qs.filter(Q(white_elo__gte=elo_min) | Q(black_elo__gte=elo_min))
    
    year_start = request.GET.get('year_start')
    if year_start: qs = qs.filter(game_date__year__gte=year_start)
    
    year_end = request.GET.get('year_end')
    if year_end: qs = qs.filter(game_date__year__lte=year_end)

    eco = request.GET.get('eco')
    if eco: qs = qs.filter(eco_code__icontains=eco)


    #fitur pencarian
    q = request.GET.get('q', '').strip()
    if q:
       
        aliases = get_aliases(q)
        search_query = Q()
        # 1. Cek Nama Pemain (White ATAU Black)
        for name in aliases:
            search_query |= Q(white_player__icontains=name) | Q(black_player__icontains=name)
        # 2. Cek Metadata (Event, Site, Opening, ECO)
        search_query |= Q(event__icontains=q) | Q(site__icontains=q) | Q(eco_code__icontains=q) | Q(opening__icontains=q)
        qs = qs.filter(search_query)

    #sorting
    sort_param = request.GET.get('sort', 'newest')
    sort_options = {
        'newest': '-game_date',
        'oldest': 'game_date',
        'white_az': 'white_player',
        'black_az': 'black_player',
        'white_za': '-white_player',
        'black_za': '-black_player',
        'event_az': 'event',
    }
    qs = qs.order_by(sort_options.get(sort_param, '-game_date'))

    paginator = Paginator(qs, 10)
    page = request.GET.get('page', 1)
    try:
        games_page = paginator.page(page)
    except PageNotAnInteger:
        games_page = paginator.page(1)
    except EmptyPage:
        games_page = paginator.page(paginator.num_pages)

    try: offset = (int(games_page.number) - 1) * 10
    except: offset = 0

    context = {
        'games': games_page,
        'paginator': paginator,
        'offset': offset,
        'fen_query': fen_query,
        'request': request 
    }
    
    return render(request, 'chess_db/game_list.html', context)

#analysis board
def analysis_board(request):

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


from datetime import datetime 



def save_analysis(request):
    if request.method == 'POST':
        # Ambil data dari form modal
        white_name = request.POST.get('white_player', 'Player (White)')
        black_name = request.POST.get('black_player', 'Analysis (Black)')
        event_name = request.POST.get('event', 'Manual Analysis')
        result_res = request.POST.get('result', '*')
        pgn_data = request.POST.get('pgn_data', '') # Ini PGN dari JavaScript

        # Buat Game Baru
        new_game = Game.objects.create(
            white_player=white_name,
            black_player=black_name,
            event=event_name,
            result=result_res,
            game_date=datetime.now().date(), # Tanggal hari ini
            pgn=pgn_data, # Simpan langkah yang sudah dibuat
            site="Local Analysis"
        )
        
        messages.success(request, "Analisis berhasil disimpan sebagai permainan baru!")
        return redirect('game_detail', game_id=new_game.id)
    
    # Jika bukan POST, kembalikan ke halaman analisis (sesuaikan nama url-nya jika beda)
    return redirect('game_list')

def game_detail(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    
    if request.method == 'POST':
        notes_form = GameNotesForm(request.POST, instance=game)
        if notes_form.is_valid():
            notes_form.save()
            messages.success(request, "Catatan berhasil disimpan!")
            return redirect('game_detail', game_id=game.id) # Refresh halaman
    else:
        # Jika cuma melihat, isi form dengan notes yang sudah ada di database
        notes_form = GameNotesForm(instance=game)

    move_data_list = []
    
    try:
        pgn_io = io.StringIO(game.pgn)
        g = chess.pgn.read_game(pgn_io)
        board = g.board()

        # 1. Tambahkan POSISI AWAL (index 0)
        move_data_list.append({
            "move_number": "Start",
            "notation": "Posisi Awal",
            "fen": board.fen(),
            "from": None, 
            "to": None   
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
#opening explorer
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
            
            
            if found_position:
                
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
    fen = request.GET.get('fen', 'start')
    opponent = request.GET.get('opponent', '').strip()
    user_color = request.GET.get('color', '')

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

    games = Game.objects.all()

    if opponent:
        #(ALIASING)
        profiles = PlayerProfile.objects.filter(
            Q(name__icontains=opponent) | 
            Q(aliases__username__icontains=opponent)
        ).distinct()

        target_names = set() 
        
        if profiles.exists():
            
            for prof in profiles:
                target_names.add(prof.name) 
                for alias in prof.aliases.all():
                    target_names.add(alias.username)
        else:
            target_names.add(opponent)
        
        
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
        
        games = games.filter(query_player)

    target_games = games.order_by('-game_date')[:1000]
    stats_data = {}
    
    for game in target_games:
        try:
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
    
    

    debug_names = list(target_names) if opponent else []
    
    current_board_fen = board.fen() 
    
    eco_code, opening_name = get_opening_name(current_board_fen)

    
    return JsonResponse({
        'stats': stats_list,
        'searched_aliases': list(target_names) if opponent else [], # (Kalau kamu pakai alias)
        'opening': {'code': eco_code, 'name': opening_name} #kirim data opening
    })
    
def advanced_search(request):
    return render(request, 'chess_db/advanced_search.html')

@require_POST # Hanya boleh diakses lewat tombol submit (POST)
def game_bulk_delete(request):
    game_ids = request.POST.getlist('selected_games')
    
    if game_ids:
        
        deleted_count, _ = Game.objects.filter(id__in=game_ids).delete()
        
        messages.success(request, f"Berhasil menghapus {deleted_count} game.")
    else:
        messages.warning(request, "Tidak ada game yang dipilih.")
        
    return redirect('game_list')


from .eco_data import get_opening_name
#api identify opening
def api_identify_opening(request):
    fen = request.GET.get('fen', '').strip()
    
    #posisi awal
    if not fen or fen == 'start':
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    #panggil fungsi dari eco_data.py
    eco_code, opening_name = get_opening_name(fen)
    
    #hasill default
    if not opening_name:
        eco_code = "-"
        opening_name = "Unknown Opening"
        
    return JsonResponse({
        'eco': eco_code,
        'name': opening_name
    })