import json
import os

# Folder tempat file JSON berada
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Daftar file yang akan dibaca
ECO_FILES = ['ecoA.json', 'ecoB.json', 'ecoC.json', 'ecoD.json', 'ecoE.json']

# Dictionary utama
ECO_DICT = {}

def load_eco_database():
    """
    Membaca 5 file ECO (A-E) dan menggabungkannya ke dalam satu kamus.
    Mendukung format LIST ([...]) maupun DICTIONARY ({...}).
    """
    global ECO_DICT
    ECO_DICT = {} # Reset

    total_loaded = 0
    
    print("📂 Memulai proses muat Database ECO (A-E)...")

    for filename in ECO_FILES:
        file_path = os.path.join(BASE_DIR, filename)
        
        if not os.path.exists(file_path):
            print(f"   ⚠️ File tidak ditemukan: {filename} (Dilewati)")
            continue

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                count_file = 0

                # --- SKENARIO 1: FORMAT DICTIONARY ---
                # Struktur: { "FEN_STRING": { "eco": "A00", "name": "..." }, ... }
                if isinstance(data, dict):
                    for fen_key, info in data.items():
                        # Ambil FEN dari Key
                        board_fen = fen_key.split(' ')[0]
                        
                        code = info.get('eco', '')
                        name = info.get('name', 'Unknown')
                        
                        ECO_DICT[board_fen] = (code, name)
                        count_file += 1

                # --- SKENARIO 2: FORMAT LIST ---
                # Struktur: [ { "fen": "...", "eco": "A00", "name": "..." }, ... ]
                elif isinstance(data, list):
                    for item in data:
                        fen_raw = item.get('fen', '')
                        if fen_raw:
                            board_fen = fen_raw.split(' ')[0]
                            code = item.get('eco', '')
                            name = item.get('name', 'Unknown')
                            
                            ECO_DICT[board_fen] = (code, name)
                            count_file += 1
                
                total_loaded += count_file
                print(f"   ✅ {filename}: {count_file} data dimuat.")
                
        except Exception as e:
            print(f"   ❌ Error membaca {filename}: {e}")

    print(f"🏁 SELESAI. Total {total_loaded} variasi opening siap digunakan.")

# Load otomatis saat server jalan
load_eco_database()

def get_opening_name(fen):
    """
    Mencari nama opening berdasarkan FEN.
    """
    # Potong FEN, ambil posisi bidak saja
    board_fen = fen.split(' ')[0]
    
    if board_fen in ECO_DICT:
        return ECO_DICT[board_fen]
        
    return "-", "Unknown Variation"