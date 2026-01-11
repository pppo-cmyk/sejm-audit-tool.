import requests
import io
import re
import logging
import zipfile
import os
import csv
import numpy as np
import concurrent.futures
import pandas as pd
from datetime import datetime
from pypdf import PdfReader
from pdf2image import convert_from_bytes
from unidecode import unidecode
from thefuzz import fuzz
from paddleocr import PaddleOCR
from docx import Document

# ==============================================================================
# ⚙️ KONFIGURACJA TOTALNA (PROJECT TOTAL RECALL)
# ==============================================================================
TERMS = [9, 10]  # Kadencje IX i X
API_URL = "https://api.sejm.gov.pl/sejm"
OUTPUT_FILE = f"sejm_total_recall_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

# BATCH_SIZE: Co ile procesów zapisywać wyniki na dysk?
# To zabezpiecza przed utratą danych przy braku prądu/awarii przez 2 tygodnie pracy.
BATCH_SAVE_INTERVAL = 5 

# SŁOWNIK SZUKANY: Czego szukamy W ŚRODKU (niezależnie od tytułu ustawy)
# Szukamy pieniędzy i służb w ustawach o rybach, drogach i edukacji.
SEMANTIC_TRIGGERS = {
    "FINANSE": ["uposazenie", "dodatek", "gratyfikacja", "naleznosc", "kwota bazowa", 
                "skutki finansowe", "mld zl", "srodki majatkowe", "budzet", "zwiekszenie", "wynagrodzenie"],
    "WOJSKO_SLUZBY": ["wojsko", "obrona narodowa", "zolnierz", "weteran", "amw", 
                      "uzbrojenie", "modernizacja", "fundusz wsparcia", "sluzb specjalnych", 
                      "cba", "abw", "skw", "sww", "wywiad", "kontrwywiad", "funkcjonariusz"]
}

# ==============================================================================
# 🚀 GPU ENGINE INIT
# ==============================================================================
print("⚡ [HPC INIT] Start silnika PaddleOCR (RTX 5090)...")
try:
    # use_angle_cls=True -> Prostuje krzywe skany (ważne przy starych drukach)
    GLOBAL_OCR_ENGINE = PaddleOCR(use_angle_cls=True, lang='pl', use_gpu=True, show_log=False)
    print("✅ [HPC INIT] Gotowy. Tryb: 100% STRON RENDER | NO FILTERS.")
except Exception as e:
    raise RuntimeError(f"Błąd GPU: {e}")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# ==============================================================================
# 🛠️ NARZĘDZIA POMOCNICZE
# ==============================================================================

def get_roman(n):
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syb = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    roman_num = ''
    i = 0
    while n > 0:
        for _ in range(n // val[i]):
            roman_num += syb[i]
            n -= val[i]
        i += 1
    return roman_num

def index_to_char(n):
    return chr(65 + n) if n < 26 else f"Z{n}"

def extract_metadata(file_bytes, ext):
    meta = {"Autor": "?", "Data": "?"}
    try:
        if ext == 'pdf':
            info = PdfReader(io.BytesIO(file_bytes)).metadata
            if info:
                meta["Autor"] = info.author or "?"
                if info.creation_date: meta["Data"] = str(info.creation_date).replace("D:", "").split('+')[0]
        elif ext in ['docx', 'doc']:
            prop = Document(io.BytesIO(file_bytes)).core_properties
            meta["Autor"] = prop.author or "?"
            if prop.created: meta["Data"] = prop.created.strftime("%Y-%m-%d %H:%M:%S")
    except: pass
    return meta

def initialize_csv():
    """Tworzy plik i nagłówki, jeśli nie istnieje."""
    if not os.path.exists(OUTPUT_FILE):
        df = pd.DataFrame(columns=["TREE_ID", "DRZEWO STRUKTURY", "Nazwa Pliku", "Link", 
                                   "RYZYKO", "Alerty", "Autor", "Data Pliku", "Słowa"])
        df.to_csv(OUTPUT_FILE, index=False, sep=';', encoding='utf-8-sig')

def append_to_csv(rows):
    """Dopisuje wyniki do pliku na dysku (tryb bezpieczny)."""
    if not rows: return
    df = pd.DataFrame(rows)
    # Filtrujemy kolumny dla porządku
    cols = ["TREE_ID", "DRZEWO STRUKTURY", "Nazwa Pliku", "Link", 
            "RYZYKO", "Alerty", "Autor", "Data Pliku", "Słowa"]
    # Uzupełnienie brakujących kolumn pustymi
    for c in cols:
        if c not in df.columns: df[c] = ""
    
    df[cols].to_csv(OUTPUT_FILE, mode='a', header=False, index=False, sep=';', encoding='utf-8-sig')

# ==============================================================================
# 🧠 NUCLEAR SCANNER (100% STRON)
# ==============================================================================

class NuclearScanner:
    def __init__(self, file_bytes, filename):
        self.file_bytes = file_bytes
        self.filename = filename
        self.ext = filename.split('.')[-1].lower()
        self.risk = 0
        self.vectors = []
        self.alerts = []
        self.full_text_cache = ""

    def _ocr_images_gpu(self, images):
        text = ""
        for img in images:
            try:
                img_array = np.array(img)
                res = GLOBAL_OCR_ENGINE.ocr(img_array, cls=True)
                if res and res[0]:
                    text += " ".join([line[1][0] for line in res[0]]) + " "
            except: pass
        return text

    def scan_pdf(self):
        try:
            # 1. RENDEROWANIE WSZYSTKICH STRON (BEZ LIMITU)
            # Jeśli ustawa ma 500 stron, to renderujemy 500 stron.
            images = convert_from_bytes(self.file_bytes, dpi=200, fmt='jpeg', thread_count=8, use_pdftocairo=True)
            
            # 2. CZYTANIE PRZEZ GPU
            self.full_text_cache = self._ocr_images_gpu(images)
            
            # Dodatkowo wyciągamy tekst z warstwy logicznej (double check)
            try:
                reader = PdfReader(io.BytesIO(self.file_bytes))
                for page in reader.pages:
                    self.full_text_cache += (page.extract_text() or "") + " "
            except: pass

        except Exception as e:
            self.alerts.append(f"PDF Render Error: {str(e)}")

    def scan_docx(self):
        try:
            # 1. Tekst
            doc = Document(io.BytesIO(self.file_bytes))
            self.full_text_cache += " ".join([p.text for p in doc.paragraphs])
            # Tabele w Wordzie
            for t in doc.tables:
                for r in t.rows:
                    for c in r.cells:
                        self.full_text_cache += c.text + " "
            
            # 2. Obrazki w Wordzie
            with zipfile.ZipFile(io.BytesIO(self.file_bytes)) as z:
                media = [f for f in z.namelist() if f.startswith('word/media/')]
                if media:
                    from PIL import Image
                    pil_images = []
                    for m in media:
                        with z.open(m) as f:
                            try: pil_images.append(Image.open(f).convert('RGB'))
                            except: pass
                    if pil_images:
                        ocr = self._ocr_images_gpu(pil_images)
                        if ocr:
                            self.full_text_cache += " " + ocr
                            self.alerts.append("[SKAN W WORDZIE]")
        except Exception as e:
            self.alerts.append(f"DOCX Error: {str(e)}")

    def analyze_results(self):
        clean = unidecode(self.full_text_cache).lower()
        clean = re.sub(r'[^a-z0-9\s]', '', clean)
        
        found_cats = set()
        
        for cat, terms in SEMANTIC_TRIGGERS.items():
            for term in terms:
                term_clean = unidecode(term).lower()
                # Fuzzy match > 90%
                if term_clean in clean or fuzz.partial_ratio(term_clean, clean) > 90:
                    self.vectors.append(term)
                    found_cats.add(cat)
                    self.risk += 2
        
        # Logika "Wrzutki"
        if "WOJSKO_SLUZBY" in found_cats and "FINANSE" in found_cats:
            self.risk += 10
            self.alerts.append("🚨 KORELACJA (KASA DLA SŁUŻB)")

        return min(self.risk, 10)

    def run(self):
        if self.ext == 'pdf': self.scan_pdf()
        elif self.ext in ['docx', 'doc']: self.scan_docx()
        # Pliki tekstowe/inne też sprawdzamy
        else:
            try: self.full_text_cache = self.file_bytes.decode('utf-8', errors='ignore')
            except: pass
            
        return self.analyze_results()

# ==============================================================================
# 🌳 WORKER DRZEWA (BEZ FILTRÓW)
# ==============================================================================

def worker_process_full_tree(proc, term, proc_idx):
    rows = []
    roman_id = get_roman(proc_idx)
    
    # 1. KORZEŃ (PROCES)
    rows.append({
        "TREE_ID": f"{roman_id}",
        "DRZEWO STRUKTURY": f"📂 [{proc.get('num', '?')}] {proc['title'][:150]}...",
        "Nazwa Pliku": "", "Link": f"https://sejm.gov.pl/Sejm{term}.nsf/przebieg.xsp?id={proc['num']}",
        "RYZYKO": "", "Alerty": "", "Autor": "", "Data Pliku": "", "Słowa": ""
    })

    prints = proc.get('prints', [])
    # Jeśli proces nie ma druków (np. wczesna faza), to i tak jest odnotowany w korzeniu.
    
    for p_i, print_nr in enumerate(prints, 1):
        # 2. GAŁĄŹ (DRUK)
        print_id = f"{roman_id}.{p_i}"
        rows.append({
            "TREE_ID": print_id,
            "DRZEWO STRUKTURY": f"    ├── 📁 Druk nr {print_nr}",
            "Nazwa Pliku": "", "Link": "", "RYZYKO": "", "Alerty": "", "Autor": "", "Data Pliku": "", "Słowa": ""
        })

        try:
            meta = requests.get(f"{API_URL}/term{term}/prints/{print_nr}", timeout=10).json()
            attachments = meta.get('attachments', [])
            
            for f_i, att in enumerate(attachments):
                # 3. LIŚĆ (PLIK) - SKANUJEMY KAŻDY JEDEN
                file_char = index_to_char(f_i)
                file_id = f"{print_id}.{file_char}"
                url = f"{API_URL}/term{term}/prints/{print_nr}/{att}"
                
                row = {
                    "TREE_ID": file_id,
                    "DRZEWO STRUKTURY": f"        └── 📄 {att}",
                    "Nazwa Pliku": att,
                    "Link": url,
                    "RYZYKO": 0, "Alerty": "", "Autor": "?", "Data Pliku": "?", "Słowa": ""
                }
                
                try:
                    resp = requests.get(url, timeout=120) # Długi timeout na duże pliki
                    if resp.status_code == 200:
                        content = resp.content
                        m = extract_metadata(content, att.split('.')[-1].lower())
                        row["Autor"] = m["Autor"]
                        row["Data Pliku"] = m["Data"]
                        
                        # NUCLEAR SCAN
                        scanner = NuclearScanner(content, att)
                        risk = scanner.run()
                        
                        row["RYZYKO"] = risk
                        row["Słowa"] = ", ".join(list(set(scanner.vectors)))
                        row["Alerty"] = " | ".join(scanner.alerts)
                    else:
                        row["Alerty"] = "Błąd 404/500"
                except Exception as e:
                    row["Alerty"] = f"CRASH: {str(e)}"
                
                rows.append(row)
                
        except Exception as e:
            logging.error(f"Err Druk {print_nr}: {e}")

    return rows

def get_all_processes(term):
    """Pobiera WSZYSTKIE procesy. Bez wyjątków."""
    try:
        data = requests.get(f"{API_URL}/term{term}/processes", timeout=30).json()
        return data
    except Exception as e:
        print(f"Błąd API Sejmu dla kadencji {term}: {e}")
        return []

# ==============================================================================
# 🏁 MAIN LOOP (CIĄGŁA PRACA)
# ==============================================================================

def main():
    print("=== SEJM TOTAL RECALL AUDIT ===")
    print("System: RTX 5090 | Mode: 100% Coverage | Filters: OFF")
    
    initialize_csv()
    
    tasks = []
    global_idx = 1
    
    # 1. Zbieranie listy celów (Wszystkie kadencje, wszystkie ustawy)
    for term in TERMS:
        procs = get_all_processes(term)
        print(f"Kadencja {term}: Znaleziono {len(procs)} WSZYSTKICH procesów.")
        for p in procs:
            tasks.append((p, term, global_idx))
            global_idx += 1
            
    print(f"Łącznie do przetworzenia: {len(tasks)} procesów legislacyjnych.")
    print(f"Szacowany czas: DNI/TYGODNIE. Wyniki zapisywane na bieżąco do: {OUTPUT_FILE}")

    # 2. Uruchomienie maszyny
    # Batch processing to save memory and progress
    batch_rows = []
    
    # Używamy ThreadPoolExecutor, ale iterujemy ręcznie po wynikach, żeby zapisywać co chwilę
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        # Mapowanie futures na ID procesu (do logowania)
        future_to_proc = {executor.submit(worker_process_full_tree, t[0], t[1], t[2]): t[0]['num'] for t in tasks}
        
        for i, future in enumerate(concurrent.futures.as_completed(future_to_proc)):
            proc_num = future_to_proc[future]
            try:
                res = future.result()
                if res:
                    batch_rows.extend(res)
                    
                    # Logowanie postępu
                    if any(r['RYZYKO'] >= 6 for r in res if isinstance(r['RYZYKO'], int)):
                         print(f"🚨 [{i+1}/{len(tasks)}] ZNALEZIONO RYZYKO w procesie {proc_num}")
                    else:
                         if i % 10 == 0: print(f"Processing [{i+1}/{len(tasks)}] - Proces {proc_num} OK.")

                # Zapis partii co BATCH_SAVE_INTERVAL procesów
                if (i + 1) % BATCH_SAVE_INTERVAL == 0:
                    append_to_csv(batch_rows)
                    batch_rows = [] # Czyścimy bufor
                    
            except Exception as e:
                print(f"Błąd krytyczny w procesie {proc_num}: {e}")

    # Zapisz resztki na końcu
    if batch_rows:
        append_to_csv(batch_rows)
        
    print(f"\n✅ SKANOWANIE ZAKOŃCZONE. Pełny raport: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
