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
    pip install requests

Kompatybilność:
    - Windows
    - Linux/Mac
    - Jupyter Notebook (Vast.ai, Google Colab)

Autor: Sejm Audit Tool
"""

import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any


# ==============================================================================
# KONFIGURACJA
# ==============================================================================

API_URL = "https://api.sejm.gov.pl/sejm"
TERM = 10  # Kadencja X
PROCESS_NUMBER = 471  # Numer procesu
OUTPUT_DIR = "process_471_output"
DOWNLOAD_ATTACHMENTS = True  # Czy pobierać załączniki?


# ==============================================================================
# KLASA GŁÓWNA
# ==============================================================================

class SejmProcessDownloader:
    """Pobiera i analizuje proces legislacyjny z Sejmu."""
    
    def __init__(self, term: int, process_number: int, output_dir: str):
        self.term = term
        self.process_number = process_number
        self.output_dir = output_dir
        self.process_data: Dict[str, Any] = {}
        self.attachments: List[Dict[str, Any]] = []
        self.tree_structure: List[Dict[str, Any]] = []
        
        # Stwórz folder wyjściowy
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
    def _make_request(self, url: str, timeout: int = 60) -> Optional[requests.Response]:
        """Wykonuje żądanie HTTP z obsługą błędów."""
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp
            else:
                print(f"⚠️  HTTP {resp.status_code}: {url}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Błąd połączenia: {e}")
            return None
    
    def fetch_process_info(self) -> bool:
        """Pobiera informacje o procesie."""
        print(f"\n📥 Pobieram informacje o procesie nr {self.process_number}...")
        
        # Pobierz listę wszystkich procesów
        url = f"{API_URL}/term{self.term}/processes"
        resp = self._make_request(url)
        
        if not resp:
            print("❌ Nie udało się pobrać listy procesów")
            return False
            
        processes = resp.json()
        
        # Znajdź nasz proces po numerze
        for proc in processes:
            # Sprawdź różne warianty identyfikacji procesu
            proc_num = str(proc.get('number', ''))
            proc_uе = str(proc.get('uE', ''))
            
            # Sprawdź czy któryś z druków pasuje do naszego numeru
            prints = proc.get('prints', [])
            if str(self.process_number) in [str(p) for p in prints]:
                self.process_data = proc
                print(f"✅ Znaleziono proces: {proc.get('title', 'Brak tytułu')[:100]}...")
                return True
                
        # Jeśli nie znaleziono bezpośrednio, szukaj procesu z drukiem 471
        print(f"🔍 Szukam procesu zawierającego druk nr {self.process_number}...")
        for proc in processes:
            prints = proc.get('prints', [])
            if self.process_number in prints or str(self.process_number) in [str(p) for p in prints]:
                self.process_data = proc
                print(f"✅ Znaleziono proces: {proc.get('title', 'Brak tytułu')[:100]}...")
                return True
        
        print(f"❌ Nie znaleziono procesu z drukiem nr {self.process_number}")
        return False
    
    def fetch_print_details(self, print_number: int) -> Optional[Dict[str, Any]]:
        """Pobiera szczegóły druku."""
        url = f"{API_URL}/term{self.term}/prints/{print_number}"
        resp = self._make_request(url)
        
        if resp:
            return resp.json()
        return None
    
    def download_attachment(self, print_number: int, filename: str) -> Optional[str]:
        """Pobiera załącznik i zapisuje na dysk."""
        url = f"{API_URL}/term{self.term}/prints/{print_number}/{filename}"
        resp = self._make_request(url)
        
        if resp:
            # Stwórz podfolder dla druku
            print_dir = os.path.join(self.output_dir, f"druk_{print_number}")
            if not os.path.exists(print_dir):
                os.makedirs(print_dir)
            
            filepath = os.path.join(print_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(resp.content)
            
            return filepath
        return None
    
    def build_tree(self) -> List[Dict[str, Any]]:
        """Buduje drzewo chronologiczne i powiązaniowe."""
        tree = []
        
        if not self.process_data:
            return tree
        
        # Główny węzeł procesu
        process_node = {
            "level": 0,
            "type": "PROCES",
            "id": self.process_data.get('number', self.process_number),
            "title": self.process_data.get('title', 'Brak tytułu'),
            "description": self.process_data.get('description', ''),
            "document_type": self.process_data.get('documentType', ''),
            "state": self.process_data.get('state', ''),
            "term": self.term,
            "children": []
        }
        
        # Pobierz druki i ich załączniki
        prints = self.process_data.get('prints', [])
        print(f"\n📋 Znaleziono {len(prints)} druków do przetworzenia")
        
        for idx, print_num in enumerate(prints):
            print(f"\n📄 [{idx+1}/{len(prints)}] Przetwarzam druk nr {print_num}...")
            
            print_details = self.fetch_print_details(print_num)
            
            if print_details:
                print_node = {
                    "level": 1,
                    "type": "DRUK",
                    "number": print_num,
                    "title": print_details.get('title', ''),
                    "document_date": print_details.get('documentDate', ''),
                    "delivery_date": print_details.get('deliveryDate', ''),
                    "change_date": print_details.get('changeDate', ''),
                    "attachments": []
                }
                
                # Pobierz załączniki
                attachments = print_details.get('attachments', [])
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
                        print(f"      ⬇️  [{att_idx+1}/{len(attachments)}] Pobieram: {att}")
                        local_path = self.download_attachment(print_num, att)
                        if local_path:
                            att_node["local_path"] = local_path
                            print(f"      ✅ Zapisano: {local_path}")
                        else:
                            print(f"      ❌ Błąd pobierania")
                    
                    print_node["attachments"].append(att_node)
                    self.attachments.append(att_node)
                
                process_node["children"].append(print_node)
            else:
                print(f"   ⚠️  Nie udało się pobrać szczegółów druku {print_num}")
        
        tree.append(process_node)
        self.tree_structure = tree
        return tree
    
    def print_tree_ascii(self) -> str:
        """Generuje tekstowe drzewo ASCII."""
        output_lines = []
        
        def add_node(node, prefix="", is_last=True):
            connector = "└── " if is_last else "├── "
            
            if node["type"] == "PROCES":
                output_lines.append(f"📂 PROCES: {node['title'][:80]}...")
                output_lines.append(f"   Stan: {node['state']}")
                output_lines.append(f"   Typ dokumentu: {node['document_type']}")
                output_lines.append("")
                
                children = node.get("children", [])
                for idx, child in enumerate(children):
                    is_last_child = (idx == len(children) - 1)
                    add_node(child, "", is_last_child)
                    
            elif node["type"] == "DRUK":
                output_lines.append(f"{prefix}{connector}📄 DRUK NR {node['number']}")
                output_lines.append(f"{prefix}{'    ' if is_last else '│   '}   Tytuł: {node['title'][:60]}...")
                output_lines.append(f"{prefix}{'    ' if is_last else '│   '}   Data dokumentu: {node['document_date']}")
                output_lines.append(f"{prefix}{'    ' if is_last else '│   '}   Data dostarczenia: {node['delivery_date']}")
                
                attachments = node.get("attachments", [])
                for att_idx, att in enumerate(attachments):
                    is_last_att = (att_idx == len(attachments) - 1)
                    att_prefix = prefix + ("    " if is_last else "│   ")
                    att_connector = "└── " if is_last_att else "├── "
                    
                    status = "✅" if att.get("local_path") else "🔗"
                    output_lines.append(f"{att_prefix}{att_connector}{status} {att['filename']}")
                
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
            f.write(f"Numer procesu: {self.process_number}\n")
            f.write(f"Kadencja: {self.term}\n")
            f.write(f"Tytuł: {self.process_data.get('title', 'N/A')}\n")
            f.write(f"Stan: {self.process_data.get('state', 'N/A')}\n")
            f.write(f"Typ dokumentu: {self.process_data.get('documentType', 'N/A')}\n\n")
            f.write(f"Liczba druków: {len(self.process_data.get('prints', []))}\n")
            f.write(f"Liczba załączników: {len(self.attachments)}\n\n")
            
            f.write("LINK DO STRONY SEJMU:\n")
            f.write(f"https://www.sejm.gov.pl/Sejm{self.term}.nsf/PrzebiegProc.xsp?nr={self.process_number}\n\n")
            
            f.write("POBRANE ZAŁĄCZNIKI:\n")
            f.write("-" * 40 + "\n")
            for att in self.attachments:
                status = "✅ Pobrano" if att.get("local_path") else "❌ Nie pobrano"
                f.write(f"  {status}: {att['filename']}\n")
                if att.get("local_path"):
                    f.write(f"     Lokalna ścieżka: {att['local_path']}\n")
        
        print(f"   ✅ Raport: {summary_path}")
    
    def run(self):
        """Uruchamia cały proces pobierania i analizy."""
        print("=" * 80)
        print("🏛️  SEJM PROCESS DOWNLOADER")
        print(f"   Pobieranie procesu nr {self.process_number} z kadencji {self.term}")
        print("=" * 80)
        
        # 1. Pobierz informacje o procesie
        if not self.fetch_process_info():
            print("\n❌ Nie udało się pobrać informacji o procesie.")
            print("   Sprawdź numer procesu i połączenie z internetem.")
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
        
        print("\n" + "=" * 80)
        print("✅ ZAKOŃCZONO POMYŚLNIE!")
        print(f"   Wyniki zapisane w: {os.path.abspath(self.output_dir)}")
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
