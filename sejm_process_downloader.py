#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sejm Process Downloader - Pobieranie i analiza procesu legislacyjnego nr 471
=============================================================================

Prosty program do pobierania danych z Sejmu wraz z załącznikami
i tworzenia drzewa chronologicznego i powiązaniowego.

Użycie:
    python sejm_process_downloader.py

Wymagania:
    pip install requests beautifulsoup4

Kompatybilność:
    - Windows
    - Linux/Mac
    - Jupyter Notebook (Vast.ai, Google Colab)

Autor: Sejm Audit Tool
"""

import os
import re
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse, unquote

# Opcjonalnie: BeautifulSoup do scrapowania strony Sejmu
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    print("⚠️  BeautifulSoup nie zainstalowany. Uruchom: pip install beautifulsoup4")


# ==============================================================================
# KONFIGURACJA
# ==============================================================================

API_URL = "https://api.sejm.gov.pl/sejm"
SEJM_WEB_URL = "https://www.sejm.gov.pl"
TERM = 10  # Kadencja X
PROCESS_NUMBER = 471  # Numer druku do pobrania
OUTPUT_DIR = f"druk_{PROCESS_NUMBER}_dokumentacja"
DOWNLOAD_ATTACHMENTS = True  # Czy pobierać załączniki?


# ==============================================================================
# KLASA GŁÓWNA
# ==============================================================================

class SejmProcessDownloader:
    """Pobiera i analizuje proces legislacyjny z Sejmu."""
    
    # Counter for unique filenames
    _filename_counter = 0
    
    def __init__(self, term: int, process_number: int, output_dir: str):
        self.term = term
        self.process_number = process_number
        self.output_dir = output_dir
        self.process_data: Dict[str, Any] = {}
        self.attachments: List[Dict[str, Any]] = []
        self.tree_structure: List[Dict[str, Any]] = []
        self.all_prints: List[int] = []  # Wszystkie znalezione druki
        
        # Stwórz folder wyjściowy
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def _make_request(self, url: str, timeout: int = 60) -> Optional[requests.Response]:
        """Wykonuje żądanie HTTP z obsługą błędów."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            resp = requests.get(url, timeout=timeout, headers=headers)
            if resp.status_code == 200:
                return resp
            else:
                print(f"⚠️  HTTP {resp.status_code}: {url}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Błąd połączenia: {e}")
            return None
    
    def fetch_print_from_api(self, print_number: int) -> Optional[Dict[str, Any]]:
        """Pobiera szczegóły druku bezpośrednio z API."""
        url = f"{API_URL}/term{self.term}/prints/{print_number}"
        resp = self._make_request(url)
        if resp:
            try:
                return resp.json()
            except json.JSONDecodeError:
                return None
        return None
    
    def scrape_process_page(self) -> bool:
        """Scrapuje stronę procesu z Sejmu i wyciąga linki do dokumentów."""
        if not HAS_BS4:
            print("❌ BeautifulSoup wymagany do scrapowania strony")
            return False
        
        page_url = f"{SEJM_WEB_URL}/Sejm{self.term}.nsf/PrzebiegProc.xsp?nr={self.process_number}"
        print(f"\n🌐 Pobieram stronę: {page_url}")
        
        resp = self._make_request(page_url)
        if not resp:
            return False
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Znajdź tytuł procesu
        title_elem = soup.find('h1') or soup.find('title')
        if title_elem:
            self.process_data['title'] = title_elem.get_text(strip=True)
        else:
            self.process_data['title'] = f"Druk nr {self.process_number}"
        
        print(f"✅ Tytuł: {self.process_data['title'][:100]}...")
        
        # Znajdź wszystkie linki do dokumentów (PDF, DOC, DOCX, etc.)
        doc_links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            link_text = link.get_text(strip=True)
            
            # Szukaj linków do plików
            if any(ext in href.lower() for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.rtf']):
                full_url = urljoin(page_url, href)
                doc_links.append({
                    'url': full_url,
                    'text': link_text,
                    'filename': self._extract_filename(href)
                })
            # Szukaj linków do API Sejmu
            elif 'api.sejm.gov.pl' in href:
                doc_links.append({
                    'url': href,
                    'text': link_text,
                    'filename': self._extract_filename(href)
                })
            # Szukaj linków do druków
            elif '/druk' in href.lower() or 'druk' in link_text.lower():
                # Spróbuj wyciągnąć numer druku
                match = re.search(r'(\d+)', link_text)
                if match:
                    druk_num = int(match.group(1))
                    if druk_num not in self.all_prints:
                        self.all_prints.append(druk_num)
        
        # Znajdź także linki w tabelach
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                for cell in row.find_all(['td', 'th']):
                    for link in cell.find_all('a', href=True):
                        href = link['href']
                        link_text = link.get_text(strip=True)
                        if any(ext in href.lower() for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.rtf']):
                            full_url = urljoin(page_url, href)
                            if full_url not in [d['url'] for d in doc_links]:
                                doc_links.append({
                                    'url': full_url,
                                    'text': link_text,
                                    'filename': self._extract_filename(href)
                                })
        
        self.process_data['scraped_documents'] = doc_links
        print(f"📎 Znaleziono {len(doc_links)} linków do dokumentów na stronie")
        
        # Dodaj główny druk do listy
        if self.process_number not in self.all_prints:
            self.all_prints.insert(0, self.process_number)
        
        return True
    
    def _extract_filename(self, url: str) -> str:
        """Wyciąga nazwę pliku z URL."""
        parsed = urlparse(url)
        path = unquote(parsed.path)
        filename = os.path.basename(path)
        if not filename or '.' not in filename:
            # Generuj unikalną nazwę pliku z licznikiem
            SejmProcessDownloader._filename_counter += 1
            filename = f"dokument_{SejmProcessDownloader._filename_counter:04d}.pdf"
        return filename
    
    def fetch_process_info(self) -> bool:
        """Pobiera informacje o procesie - najpierw z API, potem ze strony."""
        print(f"\n📥 Pobieram informacje o druku nr {self.process_number}...")
        
        # METODA 1: Bezpośrednio pobierz druk z API
        print(f"🔍 Próbuję API: {API_URL}/term{self.term}/prints/{self.process_number}")
        print_data = self.fetch_print_from_api(self.process_number)
        
        if print_data:
            self.process_data = {
                'title': print_data.get('title', f'Druk nr {self.process_number}'),
                'documentDate': print_data.get('documentDate', ''),
                'deliveryDate': print_data.get('deliveryDate', ''),
                'documentType': print_data.get('documentType', ''),
                'prints': [self.process_number],
                'attachments': print_data.get('attachments', []),
                'print_data': print_data
            }
            self.all_prints = [self.process_number]
            
            # Sprawdź czy są powiązane druki
            additional_prints = print_data.get('additionalPrints', [])
            if additional_prints:
                self.all_prints.extend(additional_prints)
            
            print(f"✅ Znaleziono druk: {self.process_data['title'][:80]}...")
            print(f"   📎 Załączniki z API: {len(self.process_data['attachments'])}")
            return True
        
        # METODA 2: Scrapuj stronę Sejmu
        print("⚠️  API nie zwróciło danych, próbuję scrapowania strony...")
        if HAS_BS4:
            if self.scrape_process_page():
                return True
        
        # METODA 3: Szukaj w liście procesów
        print("🔍 Szukam w liście procesów...")
        url = f"{API_URL}/term{self.term}/processes"
        resp = self._make_request(url)
        
        if resp:
            try:
                processes = resp.json()
                for proc in processes:
                    prints = proc.get('prints', [])
                    if self.process_number in prints or str(self.process_number) in [str(p) for p in prints]:
                        self.process_data = proc
                        self.all_prints = prints
                        print(f"✅ Znaleziono proces: {proc.get('title', 'Brak tytułu')[:80]}...")
                        return True
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        
        print(f"❌ Nie znaleziono druku nr {self.process_number}")
        return False
    
    def download_attachment(self, url: str, filename: str, subfolder: str = "") -> Optional[str]:
        """Pobiera załącznik z dowolnego URL i zapisuje na dysk."""
        resp = self._make_request(url)
        
        if resp:
            # Stwórz podfolder jeśli podany
            if subfolder:
                target_dir = os.path.join(self.output_dir, subfolder)
            else:
                target_dir = self.output_dir
            
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            
            # Sanitize filename - remove characters not allowed in Windows filenames
            safe_filename = re.sub(r'[<>:"/\\\\|?*]', '_', filename)
            filepath = os.path.join(target_dir, safe_filename)
            
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            
            return filepath
        return None
    
    def download_api_attachment(self, print_number: int, filename: str) -> Optional[str]:
        """Pobiera załącznik z API Sejmu."""
        url = f"{API_URL}/term{self.term}/prints/{print_number}/{filename}"
        return self.download_attachment(url, filename, f"druk_{print_number}")
    
    def build_tree(self) -> List[Dict[str, Any]]:
        """Buduje drzewo chronologiczne i powiązaniowe."""
        tree = []
        
        if not self.process_data:
            return tree
        
        # Główny węzeł procesu
        process_node = {
            "level": 0,
            "type": "PROCES",
            "id": self.process_number,
            "title": self.process_data.get('title', 'Brak tytułu'),
            "description": self.process_data.get('description', ''),
            "document_type": self.process_data.get('documentType', ''),
            "document_date": self.process_data.get('documentDate', ''),
            "term": self.term,
            "children": []
        }
        
        print(f"\n📋 Przetwarzam {len(self.all_prints)} druków...")
        
        # Pobierz każdy druk z API
        for idx, print_num in enumerate(self.all_prints):
            print(f"\n📄 [{idx+1}/{len(self.all_prints)}] Druk nr {print_num}...")
            
            print_data = self.fetch_print_from_api(print_num)
            
            if print_data:
                print_node = {
                    "level": 1,
                    "type": "DRUK",
                    "number": print_num,
                    "title": print_data.get('title', ''),
                    "document_date": print_data.get('documentDate', ''),
                    "delivery_date": print_data.get('deliveryDate', ''),
                    "attachments": []
                }
                
                # Pobierz załączniki z API
                attachments = print_data.get('attachments', [])
                print(f"   📎 Załączniki: {len(attachments)}")
                
                for att_idx, att in enumerate(attachments):
                    att_node = {
                        "level": 2,
                        "type": "ZAŁĄCZNIK",
                        "filename": att,
                        "download_url": f"{API_URL}/term{self.term}/prints/{print_num}/{att}",
                        "local_path": None
                    }
                    
                    if DOWNLOAD_ATTACHMENTS:
                        print(f"      ⬇️  [{att_idx+1}/{len(attachments)}] {att}")
                        local_path = self.download_api_attachment(print_num, att)
                        if local_path:
                            att_node["local_path"] = local_path
                            print(f"      ✅ Zapisano")
                        else:
                            print(f"      ❌ Błąd")
                    
                    print_node["attachments"].append(att_node)
                    self.attachments.append(att_node)
                
                process_node["children"].append(print_node)
            else:
                print(f"   ⚠️  Brak danych w API")
        
        # Jeśli są dokumenty ze scrapowania strony, pobierz je też
        scraped_docs = self.process_data.get('scraped_documents', [])
        if scraped_docs and DOWNLOAD_ATTACHMENTS:
            print(f"\n📥 Pobieranie {len(scraped_docs)} dokumentów ze strony Sejmu...")
            
            scraped_node = {
                "level": 1,
                "type": "STRONA_WWW",
                "title": "Dokumenty ze strony Sejmu",
                "attachments": []
            }
            
            for doc_idx, doc in enumerate(scraped_docs):
                print(f"   ⬇️  [{doc_idx+1}/{len(scraped_docs)}] {doc['filename']}")
                
                att_node = {
                    "level": 2,
                    "type": "ZAŁĄCZNIK_WWW",
                    "filename": doc['filename'],
                    "text": doc['text'],
                    "download_url": doc['url'],
                    "local_path": None
                }
                
                local_path = self.download_attachment(doc['url'], doc['filename'], "strona_www")
                if local_path:
                    att_node["local_path"] = local_path
                    print(f"      ✅ Zapisano")
                else:
                    print(f"      ❌ Błąd")
                
                scraped_node["attachments"].append(att_node)
                self.attachments.append(att_node)
            
            if scraped_node["attachments"]:
                process_node["children"].append(scraped_node)
        
        tree.append(process_node)
        self.tree_structure = tree
        return tree
    
    def print_tree_ascii(self) -> str:
        """Generuje tekstowe drzewo ASCII."""
        output_lines = []
        
        def add_node(node, prefix="", is_last=True):
            connector = "└── " if is_last else "├── "
            node_type = node.get("type", "")
            
            if node_type == "PROCES":
                title = node.get('title', 'Brak tytułu')
                output_lines.append(f"📂 DRUK NR {self.process_number}: {title[:80]}...")
                doc_date = node.get('document_date', '')
                if doc_date:
                    output_lines.append(f"   Data dokumentu: {doc_date}")
                output_lines.append(f"   Typ dokumentu: {node.get('document_type', 'N/A')}")
                output_lines.append("")
                
                children = node.get("children", [])
                for idx, child in enumerate(children):
                    is_last_child = (idx == len(children) - 1)
                    add_node(child, "", is_last_child)
                    
            elif node_type == "DRUK":
                output_lines.append(f"{prefix}{connector}📄 DRUK NR {node.get('number', '?')}")
                title = node.get('title', '')
                if title:
                    output_lines.append(f"{prefix}{'    ' if is_last else '│   '}   Tytuł: {title[:60]}...")
                output_lines.append(f"{prefix}{'    ' if is_last else '│   '}   Data dokumentu: {node.get('document_date', 'N/A')}")
                output_lines.append(f"{prefix}{'    ' if is_last else '│   '}   Data dostarczenia: {node.get('delivery_date', 'N/A')}")
                
                attachments = node.get("attachments", [])
                for att_idx, att in enumerate(attachments):
                    is_last_att = (att_idx == len(attachments) - 1)
                    att_prefix = prefix + ("    " if is_last else "│   ")
                    att_connector = "└── " if is_last_att else "├── "
                    
                    status = "✅" if att.get("local_path") else "🔗"
                    output_lines.append(f"{att_prefix}{att_connector}{status} {att.get('filename', '?')}")
                
                output_lines.append("")
            
            elif node_type == "STRONA_WWW":
                output_lines.append(f"{prefix}{connector}🌐 DOKUMENTY ZE STRONY WWW")
                
                attachments = node.get("attachments", [])
                for att_idx, att in enumerate(attachments):
                    is_last_att = (att_idx == len(attachments) - 1)
                    att_prefix = prefix + ("    " if is_last else "│   ")
                    att_connector = "└── " if is_last_att else "├── "
                    
                    status = "✅" if att.get("local_path") else "🔗"
                    output_lines.append(f"{att_prefix}{att_connector}{status} {att.get('filename', '?')}")
                
                output_lines.append("")
        
        for node in self.tree_structure:
            add_node(node)
        
        return "\n".join(output_lines)
    
    def generate_chronological_tree(self) -> str:
        """Generuje drzewo chronologiczne (sortowane po datach)."""
        output_lines = []
        output_lines.append("=" * 80)
        output_lines.append("📅 DRZEWO CHRONOLOGICZNE")
        output_lines.append("=" * 80)
        output_lines.append("")
        
        # Zbierz wszystkie daty
        events = []
        
        for node in self.tree_structure:
            if node["type"] == "PROCES":
                for child in node.get("children", []):
                    if child["type"] == "DRUK":
                        doc_date = child.get("document_date", "")
                        delivery_date = child.get("delivery_date", "")
                        
                        if doc_date:
                            events.append({
                                "date": doc_date,
                                "type": "Dokument",
                                "description": f"Druk nr {child['number']}: {child['title'][:50]}...",
                                "attachments": len(child.get("attachments", []))
                            })
                        
                        if delivery_date and delivery_date != doc_date:
                            events.append({
                                "date": delivery_date,
                                "type": "Dostarczenie",
                                "description": f"Dostarczenie druku nr {child['number']}",
                                "attachments": 0
                            })
        
        # Sortuj po dacie
        events.sort(key=lambda x: x.get("date", ""))
        
        for event in events:
            output_lines.append(f"📆 {event['date']}")
            output_lines.append(f"   [{event['type']}] {event['description']}")
            if event['attachments'] > 0:
                output_lines.append(f"   📎 Załączniki: {event['attachments']}")
            output_lines.append("")
        
        return "\n".join(output_lines)
    
    def save_results(self):
        """Zapisuje wyniki do plików."""
        print("\n💾 Zapisywanie wyników...")
        
        # 1. Zapisz surowe dane JSON
        json_path = os.path.join(self.output_dir, "process_data.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "process": self.process_data,
                "tree": self.tree_structure,
                "attachments": self.attachments,
                "generated_at": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
        print(f"   ✅ Dane JSON: {json_path}")
        
        # 2. Zapisz drzewo ASCII
        tree_path = os.path.join(self.output_dir, "drzewo_struktury.txt")
        with open(tree_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("🌳 DRZEWO STRUKTURY PROCESU LEGISLACYJNEGO\n")
            f.write(f"   Numer procesu: {self.process_number}\n")
            f.write(f"   Kadencja: {self.term}\n")
            f.write(f"   Data wygenerowania: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            f.write(self.print_tree_ascii())
        print(f"   ✅ Drzewo struktury: {tree_path}")
        
        # 3. Zapisz drzewo chronologiczne
        chrono_path = os.path.join(self.output_dir, "drzewo_chronologiczne.txt")
        with open(chrono_path, 'w', encoding='utf-8') as f:
            f.write(self.generate_chronological_tree())
        print(f"   ✅ Drzewo chronologiczne: {chrono_path}")
        
        # 4. Zapisz raport podsumowujący
        summary_path = os.path.join(self.output_dir, "raport_podsumowujacy.txt")
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("📊 RAPORT PODSUMOWUJĄCY\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Numer druku: {self.process_number}\n")
            f.write(f"Kadencja: {self.term}\n")
            f.write(f"Tytuł: {self.process_data.get('title', 'N/A')}\n")
            f.write(f"Typ dokumentu: {self.process_data.get('documentType', 'N/A')}\n\n")
            f.write(f"Liczba powiązanych druków: {len(self.all_prints)}\n")
            f.write(f"Liczba pobranych załączników: {len(self.attachments)}\n\n")
            
            f.write("LINK DO STRONY SEJMU:\n")
            f.write(f"https://www.sejm.gov.pl/Sejm{self.term}.nsf/PrzebiegProc.xsp?nr={self.process_number}\n\n")
            
            f.write("POBRANE ZAŁĄCZNIKI:\n")
            f.write("-" * 40 + "\n")
            for att in self.attachments:
                status = "✅ Pobrano" if att.get("local_path") else "❌ Nie pobrano"
                f.write(f"  {status}: {att.get('filename', '?')}\n")
                if att.get("local_path"):
                    f.write(f"     Lokalna ścieżka: {att['local_path']}\n")
        
        print(f"   ✅ Raport: {summary_path}")
    
    def run(self):
        """Uruchamia cały proces pobierania i analizy."""
        print("=" * 80)
        print("🏛️  SEJM PROCESS DOWNLOADER")
        print(f"   Pobieranie druku nr {self.process_number} z kadencji {self.term}")
        print("=" * 80)
        
        # 1. Pobierz informacje o procesie
        if not self.fetch_process_info():
            print("\n❌ Nie udało się pobrać informacji o druku.")
            print("   Sprawdź numer druku i połączenie z internetem.")
            return False
        
        # 2. Zbuduj drzewo i pobierz załączniki
        self.build_tree()
        
        # 3. Wyświetl drzewo
        print("\n" + "=" * 80)
        print("🌳 DRZEWO STRUKTURY:")
        print("=" * 80)
        print(self.print_tree_ascii())
        
        # 4. Wyświetl drzewo chronologiczne
        print(self.generate_chronological_tree())
        
        # 5. Zapisz wyniki
        self.save_results()
        
        # 6. Podsumowanie
        downloaded_count = len([a for a in self.attachments if a.get('local_path')])
        
        print("\n" + "=" * 80)
        print("✅ ZAKOŃCZONO POMYŚLNIE!")
        print(f"   📂 Folder: {os.path.abspath(self.output_dir)}")
        print(f"   📄 Pobrano dokumentów: {downloaded_count}")
        print("=" * 80)
        
        return True


# ==============================================================================
# URUCHOMIENIE
# ==============================================================================

def main():
    """Funkcja główna."""
    downloader = SejmProcessDownloader(
        term=TERM,
        process_number=PROCESS_NUMBER,
        output_dir=OUTPUT_DIR
    )
    downloader.run()


if __name__ == "__main__":
    main()
