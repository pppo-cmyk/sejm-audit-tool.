# Sejm Audit Tool

Narzędzia do pobierania i analizy danych z Sejmu RP.

## 🆕 Sejm Process Downloader (Nowy!)

Prosty program do pobierania konkretnego procesu legislacyjnego wraz z załącznikami i tworzenia drzewa chronologicznego.

### Szybki start

**Windows / Linux / Mac:**
```bash
pip install requests
python sejm_process_downloader.py
```

**Jupyter Notebook (Vast.ai / Google Colab):**
1. Otwórz plik `sejm_process_downloader.ipynb`
2. Uruchom wszystkie komórki po kolei
3. Wyniki zostaną zapisane w folderze `process_471_output`

### Konfiguracja

Aby zmienić numer procesu, edytuj zmienne na początku pliku:

```python
TERM = 10  # Kadencja (np. 10 = X kadencja)
PROCESS_NUMBER = 471  # Numer procesu do pobrania
OUTPUT_DIR = "process_471_output"  # Folder wyjściowy
DOWNLOAD_ATTACHMENTS = True  # Czy pobierać pliki załączników?
```

### Wyniki

Program tworzy następujące pliki:
- `process_data.json` - Surowe dane w formacie JSON
- `drzewo_struktury.txt` - Drzewo struktury procesu (ASCII)
- `drzewo_chronologiczne.txt` - Oś czasu wydarzeń
- `raport_podsumowujacy.txt` - Raport podsumowujący
- `druk_XXX/` - Foldery z pobranymi załącznikami

### Link do strony Sejmu

https://www.sejm.gov.pl/Sejm10.nsf/PrzebiegProc.xsp?nr=471

---

## Główny skaner (Heavy Audit Mode)

Pełny skaner wszystkich procesów legislacyjnych z OCR i analizą ryzyka.

### Wymagania
```bash
pip install -r requirements.txt
sudo apt-get install poppler-utils libgl1  # Linux
```

### Uruchomienie
```bash
python main.py
```

---

## Pliki

| Plik | Opis |
|------|------|
| `sejm_process_downloader.py` | Prosty downloader dla pojedynczego procesu |
| `sejm_process_downloader.ipynb` | Wersja Jupyter Notebook |
| `main.py` | Główny skaner (Heavy Audit Mode) |
| `demo.py.` | Skrypt demonstracyjny |

## Licencja

MIT