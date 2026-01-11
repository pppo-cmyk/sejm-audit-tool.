python
import requests
import io
import re
import logging
import zipfile
import os
import time
import numpy as np
import concurrent.futures
import pandas as pd
from datetime import datetime
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError
from pdf2image import convert_from_bytes
from unidecode import unidecode
from thefuzz import fuzz
from paddleocr import PaddleOCR
from docx import Document
import openpyxl
import xlrd

# ==============================================================================
# ⚙️ KONFIGURACJA TOTALNA (PROJECT TOTAL RECALL)
# ==============================================================================
TERMS = [9, 10]
API_URL = "https://api.sejm.gov.pl/sejm"
OUTPUT_DIR = "sejm_audit_output"
SAVE_INTERVAL_SECONDS = 300  # Zapis co 5 minut

# SŁOWNIK RYZYKA
SEMANTIC_TRIGGERS = {
    "FINANSE": ["uposazenie", "dodatek", "gratyfikacja", "naleznosc", "kwota bazowa", 
                "skutki finansowe", "mld zl", "srodki majatkowe", "budzet", "zwiekszenie", "wynagrodzenie"],
    "WOJSKO_SLUZBY": ["wojsko", "obrona narodowa", "zolnierz", "weteran", "amw", 
                      "uzbrojenie", "modernizacja", "fundusz wsparcia", "sluzb specjalnych", 
                      "cba", "abw", "skw", "sww", "wywiad", "kontrwywiad", "funkcjonariusz"]
}

if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)

# ==============================================================================
# 🚀 GPU INIT
# ==============================================================================
print("⚡ [HPC INIT] Start silnika PaddleOCR (RTX 5090)...")
try:
    GLOBAL_OCR_ENGINE = PaddleOCR(use_angle_cls=True, lang='pl', use_gpu=True, show_log=False)
    print("✅ [HPC INIT] Gotowy. Tryb: FORENSIC DIFF + ZIP + EXCEL + DEEP RIDER.")
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

def save_batch_to_disk(rows, batch_idx):
    if not rows: return
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{OUTPUT_DIR}/audit_part_{batch_idx}_{timestamp}.csv"
    df = pd.DataFrame(rows)
    cols = ["TREE_ID", "STATUS_SKANU", "DRZEWO STRUKTURY", "Nazwa Pliku", "Link", 
            "RYZYKO", "Alerty", "Autor", "Data Pliku", "Słowa"]
    for c in cols:
        if c not in df.columns: df[c] = ""
    df[cols].to_csv(filename, index=False, sep=';', encoding='utf-8-sig')
    print(f"💾 [AUTO-SAVE] Zapisano partię {batch_idx}: {filename} ({len(rows)} rekordów)")

def robust_request(url, retries=3):
    """Pobieranie z obsługą Rate Limit (429) - exponential backoff."""
    delay = 2
    for i in range(retries):
        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code == 429: # Za szybko!
                wait = delay * (i + 1) * 3
                print(f"🛑 Rate Limit (429). Czekam {wait}s...")
                time.sleep(wait)
                continue
            return resp
        except Exception as e:
            time.sleep(delay)
    return None

# ==============================================================================
# 🧠 FORENSIC SCANNER
# ==============================================================================

class ForensicScanner:
    def __init__(self, file_bytes, filename):
        self.file_bytes = file_bytes
        self.filename = filename
        self.ext = filename.split('.')[-1].lower()
        self.risk = 0
        self.vectors = []
        self.alerts = []
        
        self.visual_text = ""  # OCR z obrazka (GPU)
        self.logic_text = ""   # Tekst z kodu pliku

    def _ocr_gpu(self, images):
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
            # 1. WARSTWA LOGICZNA
            reader = PdfReader(io.BytesIO(self.file_bytes))
            if reader.is_encrypted:
                try: reader.decrypt('') 
                except:
                    self.alerts.append("🔒 ZABLOKOWANE HASŁEM")
                    self.risk += 10
                    return

            for page in reader.pages:
                self.logic_text += (page.extract_text() or "") + " "

            # 2. WARSTWA WIZUALNA (GPU RENDER 100% STRON)
            images = convert_from_bytes(self.file_bytes, dpi=200, fmt='jpeg', thread_count=8, use_pdftocairo=True)
            self.visual_text = self._ocr_gpu(images)

        except FileNotDecryptedError:
            self.alerts.append("🔒 ZABLOKOWANE HASŁEM")
            self.risk += 10
        except Exception as e:
            self.alerts.append(f"PDF Error: {str(e)}")

    def scan_docx(self):
        try:
            doc = Document(io.BytesIO(self.file_bytes))
            self.logic_text += " ".join([p.text for p in doc.paragraphs])
            for t in doc.tables:
                for r in t.rows:
                    for c in r.cells: self.logic_text += c.text + " "
            
            # Obrazki w Wordzie
            with zipfile.ZipFile(io.BytesIO(self.file_bytes)) as z:
                media = [f for f in z.namelist() if f.startswith('word/media/')]
                if media:
                    from PIL import Image
                    pil_imgs = []
                    for m in media:
                        with z.open(m) as f:
                            try: pil_imgs.append(Image.open(f).convert('RGB'))
                            except: pass
                    if pil_imgs:
                        self.visual_text += self._ocr_gpu(pil_imgs)
                        self.alerts.append("[SKAN W WORDZIE]")
        except: pass

    def scan_excel(self):
        try:
            # Excel traktujemy jako logiczny
            df_dict = pd.read_excel(io.BytesIO(self.file_bytes), sheet_name=None)
            for sheet_name, df in df_dict.items():
                self.logic_text += f" [Arkusz: {sheet_name}] {df.to_string()} "
        except Exception as e:
            self.alerts.append(f"Excel Error: {e}")

    def analyze_results(self):
        clean_visual = unidecode(self.visual_text).lower()
        clean_logic = unidecode(self.logic_text).lower()
        
        # Łączymy do szukania triggerów
        combined_text = clean_visual + " " + clean_logic
        clean_combined = re.sub(r'[^a-z0-9\s]', '', combined_text)

        found_cats = set()
        
        # 1. SZUKANIE SŁÓW
        for cat, terms in SEMANTIC_TRIGGERS.items():
            for term in terms:
                term_clean = unidecode(term).lower()
                # Fuzzy match
                if term_clean in clean_combined or fuzz.partial_ratio(term_clean, clean_combined) > 90:
                    self.vectors.append(term)
                    found_cats.add(cat)
                    self.risk += 2

        # 2. FORENSIC DIFF (PORÓWNANIE WARSTW - TYLKO DLA PDF)
        # Dla Excela/Worda nie robimy pełnego diffa, bo nie renderujemy całych stron wizualnie
        if self.ext == 'pdf':
            for vec in self.vectors:
                in_logic = vec in clean_logic
                in_visual = vec in clean_visual
                
                # A. INJECTION (Biały tekst)
                if in_logic and not in_visual:
                    self.alerts.append(f"⚠️ INJECTION (Tylko w kodzie): '{vec}'")
                    self.risk += 5
                
                # B. DEEP RIDER (Tylko na obrazie)
                if in_visual and not in_logic:
                    self.alerts.append(f"👁️ DEEP RIDER (Tylko na obrazie): '{vec}'")
                    self.risk += 5

        if "WOJSKO_SLUZBY" in found_cats and "FINANSE" in found_cats:
            self.risk += 10
            self.alerts.append("🚨 KORELACJA (SŁUŻBY+KASA)")

        return min(self.risk, 10)

    def run(self):
        if self.ext == 'pdf': self.scan_pdf()
        elif self.ext in ['docx', 'doc']: self.scan_docx()
        elif self.ext in ['xlsx', 'xls']: self.scan_excel()
        else:
            try: self.logic_text = self.file_bytes.decode('utf-8', errors='ignore')
            except: pass
            
        return self.analyze_results()

# ==============================================================================
# 🌳 WORKER (REKURENCJA ZIP)
# ==============================================================================

def process_file_content(content, filename, file_id, visual_tree, url):
    rows = []
    ext = filename.split('.')[-1].lower()
    
    # OBSŁUGA ARCHIWÓW (ZIP)
    if ext == 'zip':
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                rows.append({
                    "TREE_ID": file_id, "STATUS_SKANU": "OK (ZIP)",
                    "DRZEWO STRUKTURY": f"{visual_tree} 📦 {filename}",
                    "Nazwa Pliku": filename, "Link": url, "RYZYKO": 0, "Alerty": "Rozpakowano w locie", "Słowa": ""
                })
                
                for i, zip_file_name in enumerate(z.namelist()):
                    if zip_file_name.endswith('/'): continue
                    sub_content = z.read(zip_file_name)
                    sub_id = f"{file_id}.{i+1}"
                    sub_tree = visual_tree.replace("└──", "    └──")
                    
                    rows.extend(process_file_content(
                        sub_content, zip_file_name, sub_id, f"{sub_tree} ↪️", "wewn_zip"
                    ))
            return rows
        except: pass 

    # PLIK POJEDYNCZY
    row = {
        "TREE_ID": file_id, "STATUS_SKANU": "OK",
        "DRZEWO STRUKTURY": f"{visual_tree} 📄 {filename}",
        "Nazwa Pliku": filename, "Link": url,
        "RYZYKO": 0, "Alerty": "", "Autor": "?", "Data Pliku": "?", "Słowa": ""
    }

    try:
        m = extract_metadata(content, ext)
        row["Autor"] = m["Autor"]
        row["Data Pliku"] = m["Data"]
        
        scanner = ForensicScanner(content, filename)
        risk = scanner.run()
        
        row["RYZYKO"] = risk
        row["Słowa"] = ", ".join(list(set(scanner.vectors)))
        row["Alerty"] = " | ".join(scanner.alerts)
        
    except Exception as e:
        row["STATUS_SKANU"] = f"SCAN ERROR: {str(e)}"

    return [row]

def worker_process(proc, term, proc_idx):
    rows = []
    process_status = "OK"
    roman_id = get_roman(proc_idx)
    
    # NAGŁÓWEK PROCESU
    rows.append({
        "TREE_ID": f"{roman_id}", "STATUS_SKANU": "...",
        "DRZEWO STRUKTURY": f"📂 [{proc.get('num', '?')}] {proc['title'][:150]}...",
        "Nazwa Pliku": "", "Link": f"https://sejm.gov.pl/Sejm{term}.nsf/przebieg.xsp?id={proc['num']}",
        "RYZYKO": "", "Alerty": "", "Autor": "", "Data Pliku": "", "Słowa": ""
    })

    prints = proc.get('prints', [])
    for p_i, print_nr in enumerate(prints, 1):
        print_id = f"{roman_id}.{p_i}"
        rows.append({
            "TREE_ID": print_id, "STATUS_SKANU": "",
            "DRZEWO STRUKTURY": f"    ├── 📁 Druk {print_nr}",
            "Nazwa Pliku": "", "Link": "", "RYZYKO": "", "Alerty": "", "Autor": "", "Data Pliku": "", "Słowa": ""
        })

        try:
            meta_resp = robust_request(f"{API_URL}/term{term}/prints/{print_nr}")
            if not meta_resp or meta_resp.status_code != 200:
                rows[-1]["STATUS_SKANU"] = "API ERROR"
                continue
                
            attachments = meta_resp.json().get('attachments', [])
            for f_i, att in enumerate(attachments):
                file_id = f"{print_id}.{index_to_char(f_i)}"
                url = f"{API_URL}/term{term}/prints/{print_nr}/{att}"
                visual_tree = "        └──"
                
                file_resp = robust_request(url)
                if file_resp and file_resp.status_code == 200:
                    file_rows = process_file_content(file_resp.content, att, file_id, visual_tree, url)
                    rows.extend(file_rows)
                else:
                    rows.append({
                        "TREE_ID": file_id, "STATUS_SKANU": "DOWNLOAD ERROR",
                        "DRZEWO STRUKTURY": f"{visual_tree} ❌ {att}", "Nazwa Pliku": att, "Link": url
                    })

        except Exception as e:
            process_status = f"ERROR: {str(e)}"

    rows[0]["STATUS_SKANU"] = process_status
    return rows

def get_all_processes(term):
    try: return requests.get(f"{API_URL}/term{term}/processes", timeout=60).json()
    except: return []

# ==============================================================================
# 🏁 MAIN LOOP
# ==============================================================================

def main():
    print("=== SEJM TOTAL AUDIT (FULL FORENSIC V7.2) ===")
    
    tasks = []
    global_idx = 1
    for term in TERMS:
        procs = get_all_processes(term)
        print(f"Kadencja {term}: Znaleziono {len(procs)} procesów.")
        for p in procs:
            tasks.append((p, term, global_idx))
            global_idx += 1
            
    print(f"Start pracy. Wyniki co 5 minut w folderze '{OUTPUT_DIR}'.")
    
    buffer_rows = []
    last_save_time = time.time()
    batch_counter = 1
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_proc = {executor.submit(worker_process, t[0], t[1], t[2]): t[0]['num'] for t in tasks}
        
        completed = 0
        total = len(tasks)
        
        for future in concurrent.futures.as_completed(future_to_proc):
            completed += 1
            proc_num = future_to_proc[future]
            try:
                res = future.result()
                if res:
                    buffer_rows.extend(res)
                    if completed % 10 == 0:
                        print(f"[{completed}/{total}] Przetworzono proces {proc_num}")
            except Exception as e:
                print(f"Błąd procesu {proc_num}: {e}")

            if time.time() - last_save_time >= SAVE_INTERVAL_SECONDS:
                save_batch_to_disk(buffer_rows, batch_counter)
                buffer_rows = []
                batch_counter += 1
                last_save_time = time.time()

    if buffer_rows: save_batch_to_disk(buffer_rows, "FINAL")
    print("✅ KONIEC PRACY.")

if __name__ == "__main__":
    main()
