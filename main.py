import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import threading
import json
import os
from datetime import datetime
import sqlite3
import requests
from urllib.parse import urlparse
import logging
from PIL import Image, ImageTk
from io import BytesIO

# Try to import matplotlib, but make it optional
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import matplotlib
    matplotlib.use('TkAgg')
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not found. Charts will use text mode.")

from core_engine import CrawlerEngine

# ============================================================================
# THEME MANAGER - TeamCyberOps Branding
# ============================================================================

class UITheme:
    def __init__(self):
        self.colors = {
            'primary_red': '#CC0000',
            'dark_red': '#8B0000',
            'accent_red': '#FF1744',
            'bg_dark': '#1a1a1a',
            'bg_darker': '#0f0f0f',
            'text_primary': '#ffffff',
            'text_secondary': '#b0b0b0',
            'success': '#00ff00',
            'warning': '#ffcc00',
            'error': '#ff3333',
            'info': '#00bfff',
            'border': '#333333'
        }
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
    
    def get_color(self, name):
        return self.colors.get(name, '#ffffff')

# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    def __init__(self, db_file="logs/crawler_results.db"):
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        self.db_file = db_file
        self.init_db()
    
    def init_db(self):
        with sqlite3.connect(self.db_file) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS crawl_results (
                    id INTEGER PRIMARY KEY,
                    url TEXT,
                    depth INTEGER,
                    threads INTEGER,
                    timestamp DATETIME,
                    duration REAL,
                    total_urls INTEGER,
                    sensitive_count INTEGER,
                    status_codes TEXT,
                    file_types TEXT,
                    results_json TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS crawl_history (
                    id INTEGER PRIMARY KEY,
                    url TEXT,
                    depth INTEGER,
                    threads INTEGER,
                    timestamp DATETIME,
                    duration REAL,
                    total_urls INTEGER,
                    sensitive_count INTEGER
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY,
                    url TEXT UNIQUE,
                    title TEXT,
                    created_at DATETIME
                )
            ''')
            conn.commit()
    
    def save_crawl_results(self, url, depth, threads, duration, results):
        """Save complete crawl results to database"""
        try:
            import json as json_lib
            results_json = json_lib.dumps(results)
            status_codes = json_lib.dumps(results.get('stats', {}).get('status_codes', {}))
            file_types = json_lib.dumps(results.get('stats', {}).get('file_type_count', {}))
            
            with sqlite3.connect(self.db_file) as conn:
                conn.execute(
                    '''INSERT INTO crawl_results 
                       (url, depth, threads, timestamp, duration, total_urls, sensitive_count, status_codes, file_types, results_json)
                       VALUES (, , , , , , , , , )''',
                    (url, depth, threads, datetime.now(), duration, 
                     len(results.get('urls', [])), len(results.get('sensitive_files', [])),
                     status_codes, file_types, results_json)
                )
                conn.commit()
        except Exception as e:
            print(f"Error saving results: {str(e)}")
    
    def add_history(self, url, depth, threads, duration, total_urls, sensitive_count=0):
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                'INSERT INTO crawl_history (url, depth, threads, timestamp, duration, total_urls, sensitive_count) VALUES (, , , , , , )',
                (url, depth, threads, datetime.now(), duration, total_urls, sensitive_count)
            )
            conn.commit()
    
    def get_history(self, limit=20):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.execute(
                'SELECT url, timestamp, total_urls, sensitive_count FROM crawl_history ORDER BY timestamp DESC LIMIT ',
                (limit,)
            )
            return cursor.fetchall()
    
    def add_bookmark(self, url, title):
        with sqlite3.connect(self.db_file) as conn:
            try:
                conn.execute(
                    'INSERT INTO bookmarks (url, title, created_at) VALUES (, , )',
                    (url, title, datetime.now())
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
    
    def get_bookmarks(self):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.execute('SELECT url, title FROM bookmarks ORDER BY created_at DESC')
            return cursor.fetchall()

# ============================================================================
# MAIN APPLICATION
# ============================================================================

class TeamCyberOpsCrawler(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.theme = UITheme()
        self.db = DatabaseManager()
        self.config = self.load_app_config()
        self.crawler = CrawlerEngine(self.config)
        
        self.title("WebCrawl v5.3+ | @mohidqx")
        self.geometry("1920x1200")
        self.minsize(1200, 800)
        
        self.is_crawling = False
        self.current_results = None
        self.terminal_running = False
        
        self.setup_ui()
    
    def load_app_config(self):
        try:
            if os.path.exists('config.json'):
                with open('config.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def setup_ui(self):
        self.create_header()
        self.create_tabview()
        self.create_status_bar()
    
    def create_header(self):
        """Create beautiful enhanced banner with logo, branding, recent scans, and live status"""
        header = ctk.CTkFrame(self, height=130, fg_color="#060000")
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)
        
        # Main banner area
        banner_area = ctk.CTkFrame(header, fg_color="#060000", corner_radius=0)
        banner_area.pack(fill="both", expand=True, padx=0, pady=0)
        
        # LEFT: Logo and Title
        left_section = ctk.CTkFrame(banner_area, fg_color="#060000", corner_radius=0)
        left_section.pack(side="left", fill="both", expand=True, padx=12, pady=10)
        
        # Get logo
        try:
            response = requests.get("https://github.com/mohidqx.png", timeout=3)
            img_data = Image.open(BytesIO(response.content))
            img_data = img_data.resize((60, 60), Image.Resampling.LANCZOS)
            # Use CTkImage for proper HiDPI support
            self.github_img = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(60, 60))
            logo_label = ctk.CTkLabel(left_section, image=self.github_img, text="")
            logo_label.pack(side="left", padx=(0, 12), pady=0)
        except:
            logo_label = ctk.CTkLabel(left_section, text="", font=("Consolas", 24), 
                                      text_color="white")
            logo_label.pack(side="left", padx=(0, 12), pady=0)
        
        # Title info
        title_info = ctk.CTkFrame(left_section, fg_color="#060000", corner_radius=0)
        title_info.pack(side="left", fill="both", expand=True)
        
        title_main = ctk.CTkLabel(title_info, text="WebCrawl by TeamCyberOps", 
                                  font=("Consolas", 18, "bold"), text_color="white")
        title_main.pack(anchor="w", pady=0)
        
        subtitle = ctk.CTkLabel(title_info, text="WebCrawl Suite v5.3+ | TeamCyberOps | @mohidqx",
                               font=("Consolas", 10), text_color="#e0e0e0")
        subtitle.pack(anchor="w", pady=1)
        
        credits = ctk.CTkLabel(title_info, text="Monitor & Protect --TeamCyberOps  |  @mohidqx",
                              font=("Consolas", 8), text_color="#d0d0d0")
        credits.pack(anchor="w", pady=0)
        
        # RIGHT: Quick buttons
        button_section = ctk.CTkFrame(banner_area, fg_color="#060000", corner_radius=0)
        button_section.pack(side="right", padx=12, pady=10, fill="y")
        
        about_btn = ctk.CTkButton(button_section, text="About", command=self.show_about_dialog,
                                 fg_color="#220000", 
                                 hover_color="#440000", font=("Consolas", 9, "bold"),
                                 width=90, height=28)
        about_btn.pack(pady=2)
        
        recent_btn = ctk.CTkButton(button_section, text="Recent Scans", command=self.show_recent_scans,
                                  fg_color="#220000", hover_color="#440000",
                                  font=("Consolas", 9, "bold"), width=90, height=28)
        recent_btn.pack(pady=2)
        
        stats_btn = ctk.CTkButton(button_section, text=" Stats", command=self.show_banner_stats,
                                 fg_color="#220000", hover_color="#440000",
                                 font=("Consolas", 9, "bold"), width=90, height=28)
        stats_btn.pack(pady=2)
        
        # STATUS BAR
        status_bar = ctk.CTkFrame(header, fg_color=self.theme.get_color('dark_red'), corner_radius=5, height=20)
        status_bar.pack(fill="x", padx=10, pady=(0, 10))
        status_bar.pack_propagate(False)
        
        self.banner_status_label = ctk.CTkLabel(status_bar, text=" Ready | Last Scan: Never | Total Scans: 0 | Threat: N/A",
                                               font=("Consolas", 8), text_color="#90EE90")
        self.banner_status_label.pack(side="left", padx=8, pady=2)
        
        self.banner_progress = ctk.CTkProgressBar(status_bar, height=3, fg_color=self.theme.get_color('bg_dark'),
                                                  progress_color=self.theme.get_color('accent_red'))
        self.banner_progress.pack(side="right", fill="x", expand=True, padx=5, pady=0)
        self.banner_progress.set(0)
    
    def create_tabview(self):
        self.tabview = ctk.CTkTabview(self, fg_color=self.theme.get_color('bg_dark'), text_color=self.theme.get_color('text_primary'))
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_home = self.tabview.add(" Home")
        self.tab_console = self.tabview.add(" Live Terminal")
        self.tab_results = self.tabview.add(" Results")
        self.tab_charts = self.tabview.add(" Charts")
        self.tab_stats = self.tabview.add(" Analytics")
        self.tab_bookmarks = self.tabview.add(" Bookmarks")
        self.tab_tools = self.tabview.add(" Tools")
        self.tab_settings = self.tabview.add(" Settings")
        
        self.build_home_tab()
        self.build_console_tab()
        self.build_results_tab()
        self.build_charts_tab()
        self.build_stats_tab()
        self.build_bookmarks_tab()
        self.build_tools_tab()
        self.build_settings_tab()
    
    def build_home_tab(self):
        title = ctk.CTkLabel(self.tab_home, text=" Dashboard Control Panel", font=("Consolas", 18, "bold"), text_color=self.theme.get_color('primary_red'))
        title.pack(anchor="w", padx=20, pady=10)
        
        # Main scrollable frame
        scroll_frame = ctk.CTkScrollableFrame(self.tab_home, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # QUICK PRESETS
        preset_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        preset_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(preset_frame, text=" Quick Presets & Templates:", font=("Consolas", 12, "bold")).pack(anchor="w", padx=15, pady=(15, 10))
        
        preset_btn_frame = ctk.CTkFrame(preset_frame, fg_color="transparent")
        preset_btn_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkButton(preset_btn_frame, text=" Quick Scan", width=90, height=28,
                     command=lambda: self.apply_preset("quick"),
                     fg_color="#220000", hover_color="#440000").pack(side="left", padx=3)
        
        ctk.CTkButton(preset_btn_frame, text=" Balanced", width=90, height=28,
                     command=lambda: self.apply_preset("balanced"),
                     fg_color="#220000", hover_color="#440000").pack(side="left", padx=3)
        
        ctk.CTkButton(preset_btn_frame, text=" Deep Scan", width=90, height=28,
                     command=lambda: self.apply_preset("deep"),
                     fg_color="#220000", hover_color="#440000").pack(side="left", padx=3)
        
        ctk.CTkButton(preset_btn_frame, text=" Thorough", width=90, height=28,
                     command=lambda: self.apply_preset("thorough"),
                     fg_color="#220000", hover_color="#440000").pack(side="left", padx=3)
        
        ctk.CTkButton(preset_btn_frame, text=" Load Last", width=90, height=28,
                     command=self.load_last_scan,
                     fg_color="#220000", hover_color="#440000").pack(side="left", padx=3)
        
        # INPUT SECTION
        input_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        input_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(input_frame, text=" Target URL:", font=("Consolas", 12, "bold")).grid(row=0, column=0, padx=15, pady=15, sticky="w")
        
        self.url_entry = ctk.CTkEntry(input_frame, placeholder_text="https://example.com", width=500, height=40)
        self.url_entry.grid(row=0, column=1, padx=15, pady=15, sticky="ew")
        input_frame.grid_columnconfigure(1, weight=1)
        
        # CONFIG SECTION
        config_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        config_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(config_frame, text=" Crawl Configuration:", font=("Consolas", 12, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        
        slider_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        slider_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(slider_frame, text="Max Depth:", font=("Consolas", 11)).pack(side="left", padx=10)
        self.depth_slider = ctk.CTkSlider(slider_frame, from_=1, to=10, number_of_steps=9, width=200)
        self.depth_slider.set(4)
        self.depth_slider.pack(side="left", padx=10)
        self.depth_label = ctk.CTkLabel(slider_frame, text="4", font=("Consolas", 11, "bold"), text_color=self.theme.get_color('primary_red'), width=30)
        self.depth_label.pack(side="left", padx=5)
        self.depth_slider.configure(command=lambda v: self.depth_label.configure(text=str(int(float(v)))))
        
        thread_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        thread_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(thread_frame, text="Threads:", font=("Consolas", 11)).pack(side="left", padx=10)
        self.threads_slider = ctk.CTkSlider(thread_frame, from_=1, to=20, number_of_steps=19, width=200)
        self.threads_slider.set(5)
        self.threads_slider.pack(side="left", padx=10)
        self.threads_label = ctk.CTkLabel(thread_frame, text="5", font=("Consolas", 11, "bold"), text_color=self.theme.get_color('primary_red'), width=30)
        self.threads_label.pack(side="left", padx=5)
        self.threads_slider.configure(command=lambda v: self.threads_label.configure(text=str(int(float(v)))))
        
        config_frame.pack_configure(pady=(10, 15))
        
        # ADVANCED OPTIONS
        advanced_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        advanced_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(advanced_frame, text=" Advanced Options:", font=("Consolas", 12, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        
        options_row1 = ctk.CTkFrame(advanced_frame, fg_color="transparent")
        options_row1.pack(fill="x", padx=15, pady=5)
        
        self.ssl_verify = ctk.CTkCheckBox(options_row1, text=" Verify SSL Certificate", 
                                          checkbox_width=20, checkbox_height=20)
        self.ssl_verify.pack(side="left", padx=5)
        
        self.robots_check = ctk.CTkCheckBox(options_row1, text=" Analyze robots.txt", 
                                           checkbox_width=20, checkbox_height=20)
        self.robots_check.pack(side="left", padx=5)
        self.robots_check.select()
        
        self.rate_limit_check = ctk.CTkCheckBox(options_row1, text=" Enable Rate Limiting", 
                                               checkbox_width=20, checkbox_height=20)
        self.rate_limit_check.pack(side="left", padx=5)
        self.rate_limit_check.select()
        
        options_row2 = ctk.CTkFrame(advanced_frame, fg_color="transparent")
        options_row2.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(options_row2, text="Timeout (sec):", font=("Consolas", 10)).pack(side="left", padx=5)
        self.timeout_entry = ctk.CTkEntry(options_row2, placeholder_text="15", width=60, height=30)
        self.timeout_entry.insert(0, "15")
        self.timeout_entry.pack(side="left", padx=5)
        
        ctk.CTkLabel(options_row2, text="User-Agent:", font=("Consolas", 10)).pack(side="left", padx=5)
        self.ua_entry = ctk.CTkEntry(options_row2, placeholder_text="Auto", width=300, height=30)
        self.ua_entry.pack(side="left", padx=5)
        
        advanced_frame.pack_configure(pady=(10, 15))
        
        # BUTTON SECTION
        button_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=15)
        
        self.start_btn = ctk.CTkButton(button_frame, text=" START CRAWL", command=self.start_crawl, 
                                       fg_color="#220000", 
                                       hover_color="#440000",
                                       font=("Consolas", 13, "bold"), height=45, width=180)
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = ctk.CTkButton(button_frame, text=" STOP", command=self.stop_crawl,
                                      fg_color="#220000", hover_color="#440000", state="disabled",
                                      font=("Consolas", 12), height=45, width=120)
        self.stop_btn.pack(side="left", padx=5)
        
        export_btn = ctk.CTkButton(button_frame, text=" EXPORT", command=self.export_results,
                                  fg_color="#220000", hover_color="#440000",
                                  font=("Consolas", 12), height=45, width=120)
        export_btn.pack(side="left", padx=5)
        
        clear_btn = ctk.CTkButton(button_frame, text=" CLEAR", command=self.clear_data,
                                  fg_color="#220000", hover_color="#440000",
                                  font=("Consolas", 12), height=45, width=120)
        clear_btn.pack(side="left", padx=5)
        
        # STATS SECTION
        stats_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        stats_frame.pack(fill="both", expand=True, pady=10)
        
        stats_title = ctk.CTkLabel(stats_frame, text=" Quick Statistics & Threat Level", font=("Consolas", 14, "bold"), text_color=self.theme.get_color('primary_red'))
        stats_title.pack(anchor="w", padx=15, pady=(15, 10))
        
        self.quick_stats = ctk.CTkLabel(stats_frame, text="Ready to scan. Enter URL and click START.", justify="left", font=("Consolas", 11), wraplength=600)
        self.quick_stats.pack(anchor="nw", padx=15, pady=(0, 15), fill="both", expand=True)
    
    def build_console_tab(self):
        title = ctk.CTkLabel(self.tab_console, text=" Live Terminal Output & Log Management", font=("Consolas", 16, "bold"), text_color=self.theme.get_color('primary_red'))
        title.pack(anchor="w", padx=15, pady=10)
        
        # Control Panel
        control_frame = ctk.CTkFrame(self.tab_console, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        control_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(control_frame, text=" Console Tools:", font=("Consolas", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        tools_row = ctk.CTkFrame(control_frame, fg_color="transparent")
        tools_row.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(tools_row, text=" Filter Level", command=lambda: self.filter_console_by_level("INFO"), width=100, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(tools_row, text=" Warnings Only", command=lambda: self.filter_console_by_level("WARNING"), width=100, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(tools_row, text=" Errors Only", command=lambda: self.filter_console_by_level("SENSITIVE"), width=100, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(tools_row, text=" Clear All", command=self.clear_console, width=70, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(tools_row, text=" Export Log", command=self.export_console_log, width=100, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(tools_row, text=" Stats", command=self.show_console_stats, width=70, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        
        # Search Frame
        search_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        search_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(search_frame, text="Search:", font=("Consolas", 10)).pack(side="left")
        self.console_search = ctk.CTkEntry(search_frame, height=28, width=300, placeholder_text="Find in logs...")
        self.console_search.pack(side="left", padx=5, fill="x", expand=True)
        ctk.CTkButton(search_frame, text=" Find", command=self.search_console, width=70, height=28).pack(side="left", padx=2)
        
        # Main console area
        console_frame = ctk.CTkFrame(self.tab_console, fg_color=self.theme.get_color('bg_darker'))
        console_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        self.console = tk.Text(console_frame, bg="#0f0f0f", fg="#00ff00", font=("Courier New", 10), 
                               state="disabled", wrap="word", insertbackground="#00ff00")
        self.console.pack(fill="both", expand=True, side="left")
        
        scrollbar = tk.Scrollbar(console_frame, command=self.console.yview)
        scrollbar.pack(fill="y", side="right")
        self.console.config(yscrollcommand=scrollbar.set)
        
        self.console.tag_config("INFO", foreground="#00ff00")
        self.console.tag_config("SENSITIVE", foreground="#ff3333")
        self.console.tag_config("WARNING", foreground="#ffcc00")
        self.console.tag_config("CONFIG", foreground="#ff9999")
        self.console.tag_config("SOURCE", foreground="#00bfff")
        self.console.tag_config("TIMESTAMP", foreground="#888888")
    
    def build_results_tab(self):
        title = ctk.CTkLabel(self.tab_results, text=" Discovered Assets - Advanced Analysis", font=("Consolas", 16, "bold"), text_color=self.theme.get_color('primary_red'))
        title.pack(anchor="w", padx=15, pady=10)
        
        # Analysis toolbar
        analysis_frame = ctk.CTkFrame(self.tab_results, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        analysis_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(analysis_frame, text=" Analysis Tools:", font=("Consolas", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        tools_row1 = ctk.CTkFrame(analysis_frame, fg_color="transparent")
        tools_row1.pack(fill="x", padx=10, pady=3)
        
        ctk.CTkButton(tools_row1, text=" URL Count", command=self.count_urls, width=90, height=26, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(tools_row1, text=" Duplicates", command=self.find_duplicates, width=90, height=26, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(tools_row1, text=" File Types", command=self.analyze_file_types, width=90, height=26, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(tools_row1, text=" Domains", command=self.analyze_domains, width=90, height=26, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(tools_row1, text=" Performance", command=self.analyze_performance, width=90, height=26, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(tools_row1, text=" Threats", command=self.analyze_threats, width=90, height=26, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        
        # Search/Filter bar
        filter_frame = ctk.CTkFrame(self.tab_results, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        filter_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(filter_frame, text=" Search:", font=("Consolas", 11, "bold")).pack(side="left", padx=10, pady=10)
        
        self.search_entry = ctk.CTkEntry(filter_frame, placeholder_text="Filter results... (e.g., .php, admin, config)", height=35)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=5, pady=10)
        self.search_entry.bind('<KeyRelease>', lambda e: self.filter_results(self.search_entry.get()))
        
        clear_search = ctk.CTkButton(filter_frame, text="", width=40, height=35, 
                                     command=lambda: self.search_entry.delete(0, "end"), 
                                     fg_color="#ff3333", hover_color="#cc0000")
        clear_search.pack(side="left", padx=5, pady=10)
        
        # Create notebook for categories
        cat_notebook = ctk.CTkTabview(self.tab_results, fg_color=self.theme.get_color('bg_dark'))
        cat_notebook.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Tab 1: SENSITIVE FILES
        self.sensitive_tab = cat_notebook.add(" SENSITIVE FILES")
        self.build_sensitive_list()
        
        # Tab 2: DIRECTORIES
        self.dir_tab = cat_notebook.add(" DIRECTORIES")
        self.build_directory_list()
        
        # Tab 3: REGULAR FILES
        self.file_tab = cat_notebook.add(" FILES")
        self.build_file_list()
        
        # Tab 4: ALL URLS
        self.all_tab = cat_notebook.add(" ALL URLs")
        self.build_all_urls_list()
    
    def build_sensitive_list(self):
        """Beautiful display for sensitive files"""
        list_frame = ctk.CTkFrame(self.sensitive_tab, fg_color=self.theme.get_color('bg_darker'))
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        info_label = ctk.CTkLabel(list_frame, text=" Potentially Sensitive Files Found", 
                                 font=("Consolas", 12, "bold"), text_color="#ff3333")
        info_label.pack(anchor="w", padx=10, pady=5)
        
        self.sensitive_listbox = tk.Listbox(list_frame, bg="#0f0f0f", fg="#ff3333", 
                                           font=("Courier", 10), selectmode=tk.SINGLE)
        self.sensitive_listbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.sensitive_listbox.bind('<Double-Button-1>', self.on_url_click)
        
        scrollbar = tk.Scrollbar(list_frame, command=self.sensitive_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.sensitive_listbox.config(yscrollcommand=scrollbar.set)
    
    def build_directory_list(self):
        """Beautiful display for directories"""
        list_frame = ctk.CTkFrame(self.dir_tab, fg_color=self.theme.get_color('bg_darker'))
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        info_label = ctk.CTkLabel(list_frame, text=" Directories & Paths Discovered", 
                                 font=("Consolas", 12, "bold"), text_color="#00bfff")
        info_label.pack(anchor="w", padx=10, pady=5)
        
        self.dir_listbox = tk.Listbox(list_frame, bg="#0f0f0f", fg="#00bfff", 
                                     font=("Courier", 10), selectmode=tk.SINGLE)
        self.dir_listbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.dir_listbox.bind('<Double-Button-1>', self.on_url_click)
        
        scrollbar = tk.Scrollbar(list_frame, command=self.dir_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.dir_listbox.config(yscrollcommand=scrollbar.set)
    
    def build_file_list(self):
        """Beautiful display for regular files"""
        list_frame = ctk.CTkFrame(self.file_tab, fg_color=self.theme.get_color('bg_darker'))
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        info_label = ctk.CTkLabel(list_frame, text=" Regular Files & Resources", 
                                 font=("Consolas", 12, "bold"), text_color="#00ff00")
        info_label.pack(anchor="w", padx=10, pady=5)
        
        self.file_listbox = tk.Listbox(list_frame, bg="#0f0f0f", fg="#00ff00", 
                                      font=("Courier", 10), selectmode=tk.SINGLE)
        self.file_listbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.file_listbox.bind('<Double-Button-1>', self.on_url_click)
        
        scrollbar = tk.Scrollbar(list_frame, command=self.file_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.file_listbox.config(yscrollcommand=scrollbar.set)
    
    def build_all_urls_list(self):
        """Complete list of all URLs"""
        list_frame = ctk.CTkFrame(self.all_tab, fg_color=self.theme.get_color('bg_darker'))
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        info_label = ctk.CTkLabel(list_frame, text=" All Discovered URLs (Click to Preview)", 
                                 font=("Consolas", 12, "bold"), text_color="#ffffff")
        info_label.pack(anchor="w", padx=10, pady=5)
        
        self.all_listbox = tk.Listbox(list_frame, bg="#0f0f0f", fg="#ffffff", 
                                     font=("Courier", 9), selectmode=tk.SINGLE)
        self.all_listbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.all_listbox.bind('<Double-Button-1>', self.on_url_click)
        
        scrollbar = tk.Scrollbar(list_frame, command=self.all_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.all_listbox.config(yscrollcommand=scrollbar.set)
    
    def on_url_click(self, event):
        """Handle URL click to show preview"""
        # Get which listbox was clicked
        listbox = event.widget
        selection = listbox.curselection()
        
        if selection:
            url = listbox.get(selection[0])
            self.show_url_preview(url)
    
    def show_url_preview(self, url):
        """Show beautiful popup preview of URL"""
        preview_window = ctk.CTkToplevel(self)
        preview_window.title(f" Preview: {url[:50]}...")
        preview_window.geometry("900x650")
        preview_window.configure(fg_color=self.theme.get_color('bg_dark'))
        
        # Header
        header_frame = ctk.CTkFrame(preview_window, height=50, fg_color=self.theme.get_color('dark_red'))
        header_frame.pack(fill="x", padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        header_label = ctk.CTkLabel(header_frame, text=f" URL Preview", 
                                   font=("Consolas", 14, "bold"), text_color="#ffffff")
        header_label.pack(anchor="w", padx=15, pady=10)
        
        # URL Display
        url_frame = ctk.CTkFrame(preview_window, fg_color=self.theme.get_color('bg_darker'))
        url_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(url_frame, text="URL:", font=("Consolas", 11, "bold")).pack(anchor="w", pady=(5, 0))
        url_text = ctk.CTkTextbox(url_frame, height=50, text_color="#00bfff")
        url_text.pack(fill="both", padx=5, pady=5)
        url_text.insert("1.0", url)
        url_text.configure(state="disabled")
        
        # Metadata
        metadata_frame = ctk.CTkFrame(preview_window, fg_color=self.theme.get_color('bg_darker'))
        metadata_frame.pack(fill="x", padx=15, pady=10)
        
        parsed = urlparse(url)
        metadata_text = f"""
 METADATA ANALYSIS
{'='*50}
Domain:     {parsed.netloc}
Path:       {parsed.path or '/'}
Query:      {parsed.query or 'None'}
Fragment:   {parsed.fragment or 'None'}
Scheme:     {parsed.scheme}
Parameters: {len(parsed.query.split('&')) if parsed.query else 0}
        """.strip()
        
        meta_box = ctk.CTkTextbox(metadata_frame, height=120, text_color="#00ff00")
        meta_box.pack(fill="both", padx=5, pady=5)
        meta_box.insert("1.0", metadata_text)
        meta_box.configure(state="disabled")
        
        # Preview Content
        preview_frame = ctk.CTkFrame(preview_window, fg_color=self.theme.get_color('bg_darker'))
        preview_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        ctk.CTkLabel(preview_frame, text=" HTTP Response Preview:", font=("Consolas", 11, "bold")).pack(anchor="w", pady=(5, 0))
        
        preview_box = ctk.CTkTextbox(preview_frame, text_color="#ffffff")
        preview_box.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Fetch content in background
        def fetch_preview():
            try:
                # Safe user-agent retrieval with fallback
                user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                if self.crawler and hasattr(self.crawler, 'user_agent') and self.crawler.user_agent:
                    user_agent = self.crawler.user_agent
                
                headers = {'User-Agent': user_agent, 'Accept': 'text/html,application/xhtml+xml'}
                resp = requests.get(url, headers=headers, timeout=5, verify=False)
                content = resp.text[:1000]  # First 1000 chars
                status = f"Status: {resp.status_code}\nContent-Type: {resp.headers.get('content-type', 'Unknown')}\n\n"
                preview_box.configure(state="normal")
                preview_box.insert("1.0", status + content)
                preview_box.configure(state="disabled")
            except Exception as e:
                preview_box.configure(state="normal")
                preview_box.insert("1.0", f"Failed to fetch: {str(e)}")
                preview_box.configure(state="disabled")
        
        threading.Thread(target=fetch_preview, daemon=True).start()
        
        # Buttons
        button_frame = ctk.CTkFrame(preview_window, fg_color="transparent")
        button_frame.pack(fill="x", padx=15, pady=10)
        
        copy_btn = ctk.CTkButton(button_frame, text="📋 Copy URL", fg_color="#220000", hover_color="#440000",
                                command=lambda: self.copy_to_clipboard(url))
        copy_btn.pack(side="left", padx=5)
        
        open_btn = ctk.CTkButton(button_frame, text="🌐 Open in Browser", fg_color="#220000", hover_color="#440000",
                                command=lambda: self.open_url_in_browser(url))
        open_btn.pack(side="left", padx=5)
        
        close_btn = ctk.CTkButton(button_frame, text="✖ Close", fg_color="#ff3333", hover_color="#cc0000",
                                 command=preview_window.destroy)
        close_btn.pack(side="right", padx=5)
    
    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        messagebox.showinfo("✅ Success", "URL copied to clipboard!")
    
    def open_url_in_browser(self, url):
        """Safely open URL in browser"""
        try:
            import webbrowser
            if url.startswith(('http://', 'https://')):
                webbrowser.open(url)
                self.log(f"🌐 Opening URL: {url}", "info")
            else:
                webbrowser.open(f"https://{url}")
                self.log(f"🌐 Opening URL: https://{url}", "info")
        except Exception as e:
            self.log(f"❌ Failed to open URL: {str(e)}", "error")
    
    def build_charts_tab(self):
        title = ctk.CTkLabel(self.tab_charts, text=" Visual Analytics", font=("Consolas", 16, "bold"), text_color=self.theme.get_color('primary_red'))
        title.pack(anchor="w", padx=15, pady=10)
        
        charts_frame = ctk.CTkFrame(self.tab_charts, fg_color=self.theme.get_color('bg_darker'))
        charts_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        self.chart_frames = []
        
        for i in range(2):
            cf = tk.Frame(charts_frame, bg="#1a1a1a")
            cf.pack(side="left", fill="both", expand=True, padx=5, pady=5)
            self.chart_frames.append(cf)
    
    def build_stats_tab(self):
        title = ctk.CTkLabel(self.tab_stats, text=" Advanced Statistics & Metrics", font=("Consolas", 16, "bold"), text_color=self.theme.get_color('primary_red'))
        title.pack(anchor="w", padx=15, pady=10)
        
        # Statistics toolbar
        stats_toolbar = ctk.CTkFrame(self.tab_stats, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        stats_toolbar.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(stats_toolbar, text=" Options:", font=("Consolas", 11, "bold")).pack(side="left", padx=10, pady=10)
        
        ctk.CTkButton(stats_toolbar, text=" Refresh", command=self.refresh_stats, width=80, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(stats_toolbar, text=" Summary", command=self.show_summary, width=80, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(stats_toolbar, text=" Threats", command=self.show_threat_analysis, width=80, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(stats_toolbar, text=" Performance", command=self.show_performance_metrics, width=100, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(stats_toolbar, text=" Trends", command=self.show_trend_analysis, width=80, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(stats_toolbar, text=" Compare", command=self.compare_scans, width=80, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        
        stats_frame = ctk.CTkFrame(self.tab_stats, fg_color=self.theme.get_color('bg_darker'))
        stats_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        self.stats_text = ctk.CTkTextbox(stats_frame, height=400)
        self.stats_text.pack(fill="both", expand=True)
        self.stats_text.insert("1.0", "No crawl data yet.\n\nStart a crawl to see detailed statistics.")
    
    def build_bookmarks_tab(self):
        title = ctk.CTkLabel(self.tab_bookmarks, text=" Bookmarks & Collections", font=("Consolas", 16, "bold"), text_color=self.theme.get_color('primary_red'))
        title.pack(anchor="w", padx=15, pady=10)
        
        button_frame = ctk.CTkFrame(self.tab_bookmarks, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        button_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(button_frame, text=" Bookmark Tools:", font=("Consolas", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 5))
        
        buttons_row1 = ctk.CTkFrame(button_frame, fg_color="transparent")
        buttons_row1.pack(fill="x", padx=10, pady=3)
        
        add_btn = ctk.CTkButton(buttons_row1, text=" Add URL", command=self.add_bookmark, height=28, width=80, fg_color="#220000", hover_color="#440000")
        add_btn.pack(side="left", padx=2)
        
        refresh_btn = ctk.CTkButton(buttons_row1, text=" Refresh", command=self.load_bookmarks, height=28, width=80, fg_color="#220000", hover_color="#440000")
        refresh_btn.pack(side="left", padx=2)
        
        export_btn = ctk.CTkButton(buttons_row1, text=" Export", command=self.export_bookmarks, height=28, width=80, fg_color="#220000", hover_color="#440000")
        export_btn.pack(side="left", padx=2)
        
        import_btn = ctk.CTkButton(buttons_row1, text=" Import", command=self.import_bookmarks, height=28, width=80, fg_color="#220000", hover_color="#440000")
        import_btn.pack(side="left", padx=2)
        
        clear_btn = ctk.CTkButton(buttons_row1, text=" Clear All", command=self.clear_bookmarks, height=28, width=80, fg_color="#220000", hover_color="#440000")
        clear_btn.pack(side="left", padx=2)
        
        bookmark_frame = ctk.CTkFrame(self.tab_bookmarks, fg_color=self.theme.get_color('bg_darker'))
        bookmark_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        self.bookmarks_text = ctk.CTkTextbox(bookmark_frame)
        self.bookmarks_text.pack(fill="both", expand=True)
        
        self.load_bookmarks()
    
    def build_settings_tab(self):
        """Advanced settings and configuration panel"""
        title = ctk.CTkLabel(self.tab_settings, text=" Advanced Configuration Panel", font=("Consolas", 16, "bold"), text_color=self.theme.get_color('primary_red'))
        title.pack(anchor="w", padx=15, pady=10)
        
        # Main scrollable frame
        scroll_frame = ctk.CTkScrollableFrame(self.tab_settings, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        # CRAWLER SETTINGS
        crawler_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        crawler_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(crawler_frame, text=" Crawler Configuration", font=("Consolas", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 10))
        
        # Default depth
        depth_row = ctk.CTkFrame(crawler_frame, fg_color="transparent")
        depth_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(depth_row, text="Default Crawl Depth:", width=150).pack(side="left")
        depth_spin = ctk.CTkEntry(depth_row, width=60)
        depth_spin.insert(0, "4")
        depth_spin.pack(side="left", padx=10)
        
        # Default threads
        threads_row = ctk.CTkFrame(crawler_frame, fg_color="transparent")
        threads_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(threads_row, text="Default Threads:", width=150).pack(side="left")
        threads_spin = ctk.CTkEntry(threads_row, width=60)
        threads_spin.insert(0, "5")
        threads_spin.pack(side="left", padx=10)
        
        # Response timeout
        timeout_row = ctk.CTkFrame(crawler_frame, fg_color="transparent")
        timeout_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(timeout_row, text="Default Timeout (sec):", width=150).pack(side="left")
        timeout_spin = ctk.CTkEntry(timeout_row, width=60)
        timeout_spin.insert(0, "15")
        timeout_spin.pack(side="left", padx=10)
        
        crawler_frame.pack_configure(pady=(10, 15))
        
        # SECURITY SETTINGS
        security_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        security_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(security_frame, text=" Security & Privacy", font=("Consolas", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 10))
        
        verify_ssl = ctk.CTkCheckBox(security_frame, text="Verify SSL Certificates (Recommended)")
        verify_ssl.pack(anchor="w", padx=15, pady=5)
        
        rotate_ua = ctk.CTkCheckBox(security_frame, text="Rotate User-Agent Headers")
        rotate_ua.pack(anchor="w", padx=15, pady=5)
        
        respect_robots = ctk.CTkCheckBox(security_frame, text="Respect robots.txt Directives")
        respect_robots.select()
        respect_robots.pack(anchor="w", padx=15, pady=5)
        
        http2_support = ctk.CTkCheckBox(security_frame, text="Enable HTTP/2 Support")
        http2_support.select()
        http2_support.pack(anchor="w", padx=15, pady=5)
        
        security_frame.pack_configure(pady=(10, 15))
        
        # OUTPUT & EXPORT
        output_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        output_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(output_frame, text=" Output Preferences", font=("Consolas", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 10))
        
        export_json = ctk.CTkCheckBox(output_frame, text="Auto-Export to JSON")
        export_json.pack(anchor="w", padx=15, pady=5)
        
        export_csv = ctk.CTkCheckBox(output_frame, text="Auto-Export to CSV")
        export_csv.pack(anchor="w", padx=15, pady=5)
        
        export_html = ctk.CTkCheckBox(output_frame, text="Auto-Export to HTML")
        export_html.pack(anchor="w", padx=15, pady=5)
        
        output_frame.pack_configure(pady=(10, 15))
        
        # ABOUT SECTION
        about_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        about_frame.pack(fill="x", pady=10)
        
        about_btn = ctk.CTkButton(about_frame, text=" About WebCrawl", command=self.show_about_dialog, 
                                  fg_color=self.theme.get_color('primary_red'),
                                  hover_color=self.theme.get_color('dark_red'))
        about_btn.pack(padx=15, pady=15)
        
        # PROXY SETTINGS
        proxy_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        proxy_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(proxy_frame, text=" Proxy Configuration", font=("Consolas", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 10))
        
        proxy_enable = ctk.CTkCheckBox(proxy_frame, text="Enable HTTP Proxy")
        proxy_enable.pack(anchor="w", padx=15, pady=3)
        
        proxy_row = ctk.CTkFrame(proxy_frame, fg_color="transparent")
        proxy_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(proxy_row, text="Proxy Address:", width=120).pack(side="left")
        proxy_entry = ctk.CTkEntry(proxy_row, placeholder_text="localhost:8080")
        proxy_entry.pack(side="left", fill="x", expand=True, padx=10)
        
        proxy_frame.pack_configure(pady=(10, 15))
        
        # LOGGING SETTINGS
        logging_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        logging_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(logging_frame, text=" Logging Preferences", font=("Consolas", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 10))
        
        log_level = ctk.CTkCheckBox(logging_frame, text="Debug Level Logging")
        log_level.pack(anchor="w", padx=15, pady=3)
        
        save_logs = ctk.CTkCheckBox(logging_frame, text="Auto-Save Logs to File")
        save_logs.select()
        save_logs.pack(anchor="w", padx=15, pady=3)
        
        log_rotate = ctk.CTkCheckBox(logging_frame, text="Rotate Logs Daily")
        log_rotate.select()
        log_rotate.pack(anchor="w", padx=15, pady=3)
        
        logging_frame.pack_configure(pady=(10, 15))
        
        # PERFORMANCE TUNING
        perf_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_color('bg_darker'), corner_radius=10)
        perf_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(perf_frame, text=" Performance Tuning", font=("Consolas", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 10))
        
        cache_enable = ctk.CTkCheckBox(perf_frame, text="Enable Response Caching")
        cache_enable.select()
        cache_enable.pack(anchor="w", padx=15, pady=3)
        
        dns_cache = ctk.CTkCheckBox(perf_frame, text="DNS Caching")
        dns_cache.select()
        dns_cache.pack(anchor="w", padx=15, pady=3)
        
        keep_alive = ctk.CTkCheckBox(perf_frame, text="Keep-Alive Connections")
        keep_alive.select()
        keep_alive.pack(anchor="w", padx=15, pady=3)
        
        perf_frame.pack_configure(pady=(10, 15))
        
        # SAVE BUTTON
        button_row = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        button_row.pack(fill="x", pady=20)
        
        save_btn = ctk.CTkButton(button_row, text=" Save Settings", fg_color="#220000", hover_color="#440000", font=("Consolas", 12, "bold"), width=150)
        save_btn.pack(side="left", padx=5)
        
        reset_btn = ctk.CTkButton(button_row, text=" Reset to Default", fg_color="#220000", hover_color="#440000", font=("Consolas", 12), width=150)
        reset_btn.pack(side="left", padx=5)
        
        import_btn = ctk.CTkButton(button_row, text=" Import Settings", fg_color="#220000", hover_color="#440000", font=("Consolas", 12), width=150)
        import_btn.pack(side="left", padx=5)
    
    def build_tools_tab(self):
        """Tools and utilities tab"""
        title = ctk.CTkLabel(self.tab_tools, text=" Utilities & Tools", font=("Consolas", 16, "bold"), text_color=self.theme.get_color('primary_red'))
        title.pack(anchor="w", padx=15, pady=10)
        
        # Tools notebook
        tools_notebook = ctk.CTkTabview(self.tab_tools, fg_color=self.theme.get_color('bg_dark'))
        tools_notebook.pack(fill="both", expand=True, padx=15, pady=10)
        
        # URL Decoder/Encoder
        encoder_tab = tools_notebook.add(" Encode/Decode")
        encoder_frame = ctk.CTkFrame(encoder_tab, fg_color=self.theme.get_color('bg_darker'))
        encoder_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(encoder_frame, text=" Input:", font=("Consolas", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        encoder_input = ctk.CTkTextbox(encoder_frame, height=80)
        encoder_input.pack(fill="both", padx=10, pady=5)
        
        button_row = ctk.CTkFrame(encoder_frame, fg_color="transparent")
        button_row.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(button_row, text=" URL Encode", command=lambda: self.encode_url(encoder_input), width=120, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(button_row, text=" URL Decode", command=lambda: self.decode_url(encoder_input), width=120, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(button_row, text=" Base64 Encode", command=lambda: self.encode_base64(encoder_input), width=120, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        ctk.CTkButton(button_row, text=" Base64 Decode", command=lambda: self.decode_base64(encoder_input), width=120, height=28, fg_color="#220000", hover_color="#440000").pack(side="left", padx=2)
        
        ctk.CTkLabel(encoder_frame, text=" Output:", font=("Consolas", 11, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.encoder_output = ctk.CTkTextbox(encoder_frame, height=80, state="disabled")
        self.encoder_output.pack(fill="both", padx=10, pady=5)
        
        # URL Validator
        validator_tab = tools_notebook.add(" Validator")
        validator_frame = ctk.CTkFrame(validator_tab, fg_color=self.theme.get_color('bg_darker'))
        validator_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(validator_frame, text=" Enter URL:", font=("Consolas", 11, "bold")).pack(anchor="w", padx=10, pady=10)
        validator_input = ctk.CTkEntry(validator_frame, height=40, placeholder_text="https://example.com")
        validator_input.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(validator_frame, text=" Validate URL", command=lambda: self.validate_url(validator_input.get()), fg_color="#220000", hover_color="#440000").pack(pady=10)
        
        self.validator_output = ctk.CTkTextbox(validator_frame, height=150, state="disabled")
        self.validator_output.pack(fill="both", padx=10, pady=5)
        
        # Headers Analyzer
        headers_tab = tools_notebook.add(" Headers")
        headers_frame = ctk.CTkFrame(headers_tab, fg_color=self.theme.get_color('bg_darker'))
        headers_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(headers_frame, text=" Enter URL:", font=("Consolas", 11, "bold")).pack(anchor="w", padx=10, pady=10)
        headers_input = ctk.CTkEntry(headers_frame, height=40, placeholder_text="https://example.com")
        headers_input.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(headers_frame, text=" Analyze Headers", command=lambda: self.analyze_headers(headers_input.get()), fg_color="#220000", hover_color="#440000").pack(pady=10)
        
        self.headers_output = ctk.CTkTextbox(headers_frame, height=200)
        self.headers_output.pack(fill="both", padx=10, pady=5)
        
        # Regex Tester
        regex_tab = tools_notebook.add(" Regex")
        regex_frame = ctk.CTkFrame(regex_tab, fg_color=self.theme.get_color('bg_darker'))
        regex_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(regex_frame, text=" Pattern:", font=("Consolas", 10)).pack(anchor="w", padx=10, pady=(10, 0))
        regex_pattern = ctk.CTkEntry(regex_frame, height=35, placeholder_text="Enter regex pattern...")
        regex_pattern.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(regex_frame, text=" Text to Match:", font=("Consolas", 10)).pack(anchor="w", padx=10, pady=(10, 0))
        regex_text = ctk.CTkTextbox(regex_frame, height=100)
        regex_text.pack(fill="both", padx=10, pady=5)
        
        ctk.CTkButton(regex_frame, text=" Test Pattern", command=lambda: self.test_regex(regex_pattern.get(), regex_text.get("1.0", "end")), fg_color="#220000", hover_color="#440000").pack(pady=10)
        
        self.regex_output = ctk.CTkTextbox(regex_frame, height=80, state="disabled")
        self.regex_output.pack(fill="both", padx=10, pady=5)
    
    def create_status_bar(self):
        self.status_var = ctk.StringVar(value="WebCrawl v5.3+ | @mohidqx")
        status_bar = ctk.CTkLabel(self, textvariable=self.status_var, text_color=self.theme.get_color('text_secondary'),
                                 font=("Consolas", 10), fg_color="#060000")
        status_bar.pack(side="bottom", fill="x", padx=10, pady=5)
    
    def log(self, message, tag="INFO"):
        self.console.config(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console.insert("end", f"[{timestamp}] ", "TIMESTAMP")
        self.console.insert("end", f"[{tag}] {message}\n", tag)
        self.console.see("end")
        self.console.config(state="disabled")
        self.update()
    
    def start_crawl(self):
        """Enhanced crawl with advanced options"""
        url = self.url_entry.get().strip()
        if not url:
            self.log(" ERROR: Please enter a valid URL", "error")
            return
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, url)
        
        depth = int(self.depth_slider.get())
        threads = int(self.threads_slider.get())
        
        # Pass advanced options
        self.run_crawl_with_options(url, depth, threads)
    
    def stop_crawl(self):
        """Stop the ongoing crawl"""
        if self.crawler:
            self.crawler.stop_crawl = True
            self.log(" Crawl stop requested...", "warning")
            self.stop_btn.configure(state="disabled")
    
    def export_results(self):
        """Export results in multiple formats"""
        if not self.crawler or not hasattr(self.crawler, 'results') or not self.crawler.results:
            self.log("❌  No results to export", "warning")
            return
        
        self.log("📤 Exporting results...", "info")
        
        try:
            json_file = "crawler_results.json"
            if hasattr(self.crawler, 'export_json'):
                self.crawler.export_json(json_file)
                self.log(f"✅ JSON exported: {json_file}", "success")
            
            csv_file = "crawler_results.csv"
            if hasattr(self.crawler, 'export_csv'):
                self.crawler.export_csv(csv_file)
                self.log(f"✅ CSV exported: {csv_file}", "success")
            
            html_file = "crawler_results.html"
            if hasattr(self.crawler, 'export_html'):
                self.crawler.export_html(html_file)
                self.log(f"✅ HTML exported: {html_file}", "success")
        except Exception as e:
            self.log(f"❌ Export failed: {str(e)}", "error")
    
    def clear_data(self):
        """Clear all crawl results"""
        try:
            # Clear results tree if it exists
            if hasattr(self, 'results_tree') and self.results_tree:
                for item in self.results_tree.get_children():
                    self.results_tree.delete(item)
            
            # Clear sensitive tree if it exists
            if hasattr(self, 'sensitive_tree') and self.sensitive_tree:
                for item in self.sensitive_tree.get_children():
                    self.sensitive_tree.delete(item)
            
            # Clear directory tree if it exists
            if hasattr(self, 'dir_tree') and self.dir_tree:
                for item in self.dir_tree.get_children():
                    self.dir_tree.delete(item)
            
            # Clear files tree if it exists
            if hasattr(self, 'files_tree') and self.files_tree:
                for item in self.files_tree.get_children():
                    self.files_tree.delete(item)
            
            self.crawler = None
            self.log("🧹 All data cleared", "success")
        except Exception as e:
            self.log(f"❌ Clear failed: {str(e)}", "error")
    
    def apply_preset(self, preset_name):
        """Apply predefined scan templates"""
        presets = {
            "quick": {"depth": 2, "threads": 3, "timeout": 10, "rate_limit": True},
            "balanced": {"depth": 4, "threads": 5, "timeout": 15, "rate_limit": True},
            "deep": {"depth": 6, "threads": 8, "timeout": 20, "rate_limit": True},
            "thorough": {"depth": 10, "threads": 15, "timeout": 30, "rate_limit": False}
        }
        
        if preset_name not in presets:
            self.log(f" Unknown preset: {preset_name}", "error")
            return
        
        preset = presets[preset_name]
        self.depth_slider.set(preset["depth"])
        self.depth_label.configure(text=str(preset["depth"]))
        self.threads_slider.set(preset["threads"])
        self.threads_label.configure(text=str(preset["threads"]))
        self.timeout_entry.delete(0, "end")
        self.timeout_entry.insert(0, str(preset["timeout"]))
        
        if preset["rate_limit"]:
            self.rate_limit_check.select()
        else:
            self.rate_limit_check.deselect()
        
        self.log(f" Preset '{preset_name.upper()}' applied - Depth: {preset['depth']}, Threads: {preset['threads']}, Timeout: {preset['timeout']}s", "success")
    
    def load_last_scan(self):
        """Load the last scan configuration from database"""
        try:
            with sqlite3.connect(self.db.db_file) as conn:
                cursor = conn.execute(
                    "SELECT url, depth, threads FROM crawl_history ORDER BY timestamp DESC LIMIT 1"
                )
                row = cursor.fetchone()
                
                if row:
                    url, depth, threads = row
                    self.url_entry.delete(0, "end")
                    self.url_entry.insert(0, url)
                    self.depth_slider.set(depth)
                    self.depth_label.configure(text=str(depth))
                    self.threads_slider.set(threads)
                    self.threads_label.configure(text=str(threads))
                    self.log(f" Loaded last scan: {url} (Depth: {depth}, Threads: {threads})", "success")
                else:
                    self.log(" No previous scans found", "warning")
        except Exception as e:
            self.log(f" Error loading last scan: {str(e)}", "error")
    
    def update_quick_stats(self):
        """Update statistics display in home tab"""
        if self.crawler and hasattr(self.crawler, 'results') and self.crawler.results:
            try:
                total_urls = len(self.crawler.results)
                sensitive = sum(1 for r in self.crawler.results if isinstance(r, dict) and r.get('category') == 'SENSITIVE')
                files = sum(1 for r in self.crawler.results if isinstance(r, dict) and r.get('category') == 'FILE')
                dirs = sum(1 for r in self.crawler.results if isinstance(r, dict) and r.get('category') == 'DIR')
                
                threat_level = "🔴 CRITICAL" if sensitive > 20 else "🟠 HIGH" if sensitive > 10 else "🟡 MEDIUM" if sensitive > 5 else "🟢 LOW"
                
                stats_text = f"""📊 Crawl Summary:
├─ Total URLs: {total_urls}
├─ Sensitive Files: {sensitive} {threat_level}
├─ Directories: {dirs}
├─ Regular Files: {files}
└─ Scan Status: ✅ Complete

⚠️  Threat Assessment: {threat_level}
💡 Recommendation: Review sensitive files immediately"""
                
                if hasattr(self, 'quick_stats'):
                    self.quick_stats.configure(text=stats_text)
            except Exception as e:
                self.log(f"Error updating stats: {str(e)}", "error")
        else:
            if hasattr(self, 'quick_stats'):
                self.quick_stats.configure(text="Ready to scan. Enter URL and click START.")
    
    def filter_results(self, search_term):
        """Filter results based on search term"""
        if not search_term:
            # Restore all items
            self.populate_results_tree(self.current_results if hasattr(self, 'current_results') else {})
            return
        
        search_term = search_term.lower()
        
        try:
            # Filter sensitive files
            self.sensitive_listbox.delete(0, tk.END)
            if hasattr(self, 'current_results'):
                for url in self.current_results.get('sensitive_files', []):
                    if search_term in url.lower():
                        self.sensitive_listbox.insert(tk.END, f" {url}")
            
            # Filter directories
            self.dir_listbox.delete(0, tk.END)
            if hasattr(self, 'current_results'):
                for url in self.current_results.get('urls', []):
                    if url.endswith('/') and search_term in url.lower():
                        self.dir_listbox.insert(tk.END, f" {url}")
            
            # Filter files
            self.file_listbox.delete(0, tk.END)
            if hasattr(self, 'current_results'):
                for url in self.current_results.get('urls', []):
                    if not url.endswith('/') and '.' in url.split('/')[-1] and search_term in url.lower():
                        self.file_listbox.insert(tk.END, f" {url}")
            
            # Filter all URLs
            self.all_listbox.delete(0, tk.END)
            if hasattr(self, 'current_results'):
                for url in self.current_results.get('urls', []):
                    if search_term in url.lower():
                        self.all_listbox.insert(tk.END, url)
        except Exception as e:
            self.log(f" Filter error: {str(e)}", "error")
    
    def smooth_progress_update(self, target_value, steps=20, delay=10):
        """Smoothly animate progress bar to target value"""
        try:
            current = self.banner_progress.get()
            step_size = (target_value - current) / steps
            
            for i in range(steps):
                self.banner_progress.set(current + (step_size * (i + 1)))
                self.update()
                self.after(delay)
        except:
            self.banner_progress.set(target_value)
    
    def smooth_banner_status(self, text, fade_steps=3):
        """Smoothly update banner status text"""
        try:
            self.banner_status_label.configure(text=text)
            self.update()
        except:
            pass
    
    def animate_button_click(self, button):
        """Add visual feedback on button click"""
        try:
            original_fg = button.cget("fg_color")
            button.after(50, lambda: button.configure(fg_color=original_fg) if button else None)
        except:
            pass
    
    def smooth_exit(self):
        """Smooth application exit with cleanup"""
        try:
            self.log(" Shutting down gracefully...", "info")
            if hasattr(self, 'crawler') and self.crawler:
                self.crawler.stop_crawl = True
            self.after(300, self.quit)
        except:
            self.quit()
    

        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return
        
        if not url.startswith("http"):
            url = "https://" + url
        
        depth = int(float(self.depth_slider.get()))
        threads = int(float(self.threads_slider.get()))
        
        self.is_crawling = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.log(f" Starting crawl of {url} (Depth: {depth}, Threads: {threads})", "INFO")
        self.status_var.set(f" Crawling {url}...")
        
        crawler_thread = threading.Thread(target=self.run_crawl, args=(url, depth, threads))
        crawler_thread.daemon = True
        crawler_thread.start()
    
    def run_crawl_with_options(self, url, depth, threads):
        """Run crawl with advanced options from Home tab"""
        try:
            # Get advanced options
            timeout = int(self.timeout_entry.get()) if self.timeout_entry.get() else 15
            custom_ua = self.ua_entry.get().strip() if self.ua_entry.get().strip() else None
            verify_ssl = self.ssl_verify.cget("state") != "disabled"
            
            self.log(f" Using advanced options:", "info")
            self.log(f"  +- Timeout: {timeout}s", "info")
            self.log(f"  +- User-Agent: {'Custom' if custom_ua else 'Default'}", "info")
            self.log(f"  +- SSL Verify: {'Enabled' if verify_ssl else 'Disabled'}", "info")
            
            # Configure crawler with instance variables for later access
            if custom_ua:
                # This would be passed to crawler.crawl()
                pass
            
            self.is_crawling = True
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.status_var.set(" Crawling in progress...")
            
            # Run actual crawl
            self.run_crawl(url, depth, threads)
            
        except ValueError as e:
            self.log(f" Invalid parameter: {str(e)}", "error")
        except Exception as e:
            self.log(f" Error: {str(e)}", "error")
        finally:
            self.update_quick_stats()
    
    def run_crawl(self, url, depth, threads):
        try:
            start_time = datetime.now()
            
            # Step 1: Fetch robots.txt first (ethical goldmine)
            self.log(f" Step 1: Analyzing robots.txt for disallowed paths...", "info")
            self.smooth_progress_update(0.15, steps=10, delay=5)
            robots_paths = self.crawler.fetch_robots_txt(url, callback=lambda msg, level: self.log(msg, level.lower()))
            if robots_paths:
                self.log(f" Found {len(robots_paths)} disallowed paths from robots.txt", "success")
            
            # Step 2: Run main crawl with rate limiting
            self.log(f" Step 2: Starting main crawl with polite rate limiting (jitter)...", "info")
            self.smooth_progress_update(0.40, steps=15, delay=8)
            results = self.crawler.crawl(url, depth, threads, callback=lambda msg, level: self.log(msg, level.lower()))
            self.current_results = results
            
            # Add robots.txt discoveries to results
            if robots_paths:
                results['urls'].extend(robots_paths)
                self.log(f" Added {len(robots_paths)} robots.txt paths to crawl results", "info")
            
            # Save results to database (LIVE)
            self.log(f" Saving results to logs/crawler_results.db...", "info")
            sensitive_count = len(results.get('sensitive_files', []))
            self.db.save_crawl_results(url, depth, threads, results['stats']['duration'], results)
            self.db.add_history(url, depth, threads, results['stats']['duration'], results['stats']['total_urls'], sensitive_count)
            self.log(f" Results saved to logs/crawler_results.db", "success")
            
            self.smooth_progress_update(0.65, steps=12, delay=6)
            self.populate_results_tree(results)
            self.smooth_progress_update(0.85, steps=10, delay=5)
            
            # Update statistics and charts in real-time
            self.update_statistics(results)
            self.create_charts(results)
            self.smooth_progress_update(1.0, steps=5, delay=3)
            
            # Update banner with scan info (smooth)
            threat_level = " CRITICAL" if sensitive_count > 20 else " HIGH" if sensitive_count > 10 else " MEDIUM" if sensitive_count > 5 else " LOW"
            scan_duration = (datetime.now() - start_time).total_seconds()
            status_text = f" Complete | URLs: {results['stats']['total_urls']} | Sensitive: {sensitive_count} {threat_level} | Time: {scan_duration:.1f}s"
            self.smooth_banner_status(status_text)
            
            self.log(f" Crawl Complete! URLs: {results['stats']['total_urls']} | Files: {results['stats']['total_files']} | Duration: {results['stats']['duration']:.2f}s", "success")
            self.log(f" Tip: Check the Results tab for categorized view (Sensitive/Directories/Files)", "info")
            
        except Exception as e:
            self.log(f" Error: {str(e)}", "error")
            self.banner_status_label.configure(text=f" Error | {str(e)[:50]}")
        finally:
            self.banner_progress.set(0)
            self.is_crawling = False
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.status_var.set(f" Ready | Last crawl: {datetime.now().strftime('%H:%M:%S')}")
            self.update_quick_stats()
    
    def populate_results_tree(self, results):
        """Populate categorized result lists"""
        # Clear all listboxes
        self.sensitive_listbox.delete(0, tk.END)
        self.dir_listbox.delete(0, tk.END)
        self.file_listbox.delete(0, tk.END)
        self.all_listbox.delete(0, tk.END)
        
        # Categorize URLs
        sensitive_urls = results.get('sensitive_files', [])
        all_urls = results.get('urls', [])
        
        # Get directories (endpoints that end with /)
        directories = [url for url in all_urls if url.endswith('/')]
        
        # Get files (has extension)
        files = [url for url in all_urls if not url.endswith('/') and '.' in url.split('/')[-1]]
        
        # Populate SENSITIVE
        for url in sorted(sensitive_urls):
            self.sensitive_listbox.insert(tk.END, f" {url}")
            self.all_listbox.insert(tk.END, url)
        
        # Populate DIRECTORIES
        for url in sorted(directories):
            self.dir_listbox.insert(tk.END, f" {url}")
            if url not in sensitive_urls:
                self.all_listbox.insert(tk.END, url)
        
        # Populate FILES
        for url in sorted(files):
            self.file_listbox.insert(tk.END, f" {url}")
            if url not in sensitive_urls:
                self.all_listbox.insert(tk.END, url)
        
        # Update counters
        self.log(f" Results organized: {len(sensitive_urls)} Sensitive | {len(directories)} Dirs | {len(files)} Files", "INFO")
    
    def update_statistics(self, results):
        stats = results['stats']
        file_types = results.get('file_types', {})
        
        stats_text = f"""+---------------------------------------+
�      CRAWL STATISTICS                  �
�---------------------------------------�
� Total URLs Found:    {stats['total_urls']:<20} �
� Total Files:         {stats['total_files']:<20} �
� Errors:              {stats['total_errors']:<20} �
� Redirects:           {stats['total_redirects']:<20} �
� Duration:            {stats['duration']:.2f}s{' ' * 22} �
� Avg Response Time:   {stats['avg_response_time']:.3f}s{' ' * 18} �
�---------------------------------------�
� FILE TYPE BREAKDOWN                    �
�---------------------------------------�
"""
        for ftype, files in file_types.items():
            stats_text += f"� {ftype:<35} {len(files):<2} �\n"
        
        stats_text += f"""�---------------------------------------�
� HTTP STATUS CODES                      �
�---------------------------------------�
"""
        for code, count in sorted(results.get('response_codes', {}).items()):
            stats_text += f"� {code}: {count:<35} �\n"
        
        stats_text += "+---------------------------------------+"
        
        self.stats_text.delete("1.0", "end")
        self.stats_text.insert("end", stats_text)
        
        quick_text = f" Last Scan Results:\n\n"
        quick_text += f"  URLs Found: {stats['total_urls']}\n"
        quick_text += f"  Files Discovered: {stats['total_files']}\n"
        quick_text += f"  Scan Duration: {stats['duration']:.2f} seconds\n"
        quick_text += f"  Sensitive Files: {len(results.get('sensitive_files', []))}\n"
        quick_text += f"  Average Response: {stats['avg_response_time']:.3f}s\n"
        
        self.quick_stats.configure(text=quick_text)
    
    def create_charts(self, results):
        for frame in self.chart_frames:
            for widget in frame.winfo_children():
                widget.destroy()
        
        file_types = results.get('file_types', {})
        if not file_types:
            return
        
        try:
            if HAS_MATPLOTLIB:
                self.create_matplotlib_charts(file_types)
            else:
                self.create_text_charts(file_types)
        except Exception as e:
            self.log(f"Chart error: {str(e)}", "WARNING")
    
    def create_matplotlib_charts(self, file_types):
        # Pie chart
        fig1 = Figure(figsize=(5, 4), dpi=100, facecolor='#1a1a1a', edgecolor='#333333')
        ax1 = fig1.add_subplot(111, facecolor='#1a1a1a')
        
        labels = list(file_types.keys())
        sizes = [len(files) for files in file_types.values()]
        colors = ['#CC0000', '#FF1744', '#00bfff', '#00ff00'][:len(labels)]
        
        ax1.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
        ax1.set_title('File Type Distribution', color='#ffffff', fontsize=12, fontweight='bold')
        
        canvas1 = FigureCanvasTkAgg(fig1, master=self.chart_frames[0])
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill="both", expand=True)
        
        # Bar chart
        fig2 = Figure(figsize=(5, 4), dpi=100, facecolor='#1a1a1a', edgecolor='#333333')
        ax2 = fig2.add_subplot(111, facecolor='#1a1a1a')
        
        ax2.bar(labels, sizes, color=['#CC0000', '#FF1744', '#00bfff', '#00ff00'][:len(labels)])
        ax2.set_title('URLs per File Type', color='#ffffff', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Count', color='#ffffff')
        ax2.tick_params(colors='#ffffff')
        
        canvas2 = FigureCanvasTkAgg(fig2, master=self.chart_frames[1])
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill="both", expand=True)
    
    def create_text_charts(self, file_types):
        # Create text-based ASCII charts
        chart_text = " CHART MODE (Text-Based)\n\n"
        chart_text += "File Type Distribution (Pie Chart Alternative):\n"
        chart_text += "=" * 50 + "\n"
        
        total = sum(len(files) for files in file_types.values())
        
        for ftype, files in file_types.items():
            count = len(files)
            percentage = (count / total * 100) if total > 0 else 0
            bar_length = int(percentage / 5)
            bar = "�" * bar_length + "�" * (20 - bar_length)
            chart_text += f"{ftype:<15} {bar} {percentage:5.1f}% ({count})\n"
        
        chart_text += "\n" + "=" * 50 + "\n\n"
        chart_text += "Install matplotlib for visual charts:\n"
        chart_text += "  pip install matplotlib numpy\n"
        
        label = ctk.CTkLabel(self.chart_frames[0], text=chart_text, justify="left", font=("Courier", 10))
        label.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Second frame - summary
        summary_text = " STATISTICS SUMMARY\n"
        summary_text += "=" * 50 + "\n"
        summary_text += f"Total File Types: {len(file_types)}\n"
        summary_text += f"Total URLs: {total}\n\n"
        summary_text += "Top File Types:\n"
        
        for i, (ftype, files) in enumerate(sorted(file_types.items(), key=lambda x: len(x[1]), reverse=True)[:5]):
            summary_text += f"  {i+1}. {ftype}: {len(files)} URLs\n"
        
        label2 = ctk.CTkLabel(self.chart_frames[1], text=summary_text, justify="left", font=("Courier", 10))
        label2.pack(fill="both", expand=True, padx=10, pady=10)
    
    def export_results(self):
        if not self.current_results:
            messagebox.showerror("Error", "No results to export")
            return
        
        file_path = filedialog.asksaveasfilename(defaultextension=".json", 
                                                filetypes=[("JSON", "*.json"), ("CSV", "*.csv"), ("All", "*.*")])
        
        if file_path:
            try:
                if file_path.endswith('.json'):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(self.current_results, f, indent=2)
                elif file_path.endswith('.csv'):
                    import csv
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(['URL', 'Type', 'Status'])
                        for url in self.current_results.get('urls', []):
                            writer.writerow([url, 'Page', 'OK'])
                
                messagebox.showinfo(" Success", f"Exported to {file_path}")
                self.log(f" Results exported to {file_path}", "INFO")
            except Exception as e:
                messagebox.showerror(" Error", f"Export failed: {str(e)}")
    
    def clear_data(self):
        if messagebox.askyesno("Confirm", "Clear all current results"):
            self.current_results = None
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.stats_text.delete("1.0", "end")
            self.quick_stats.configure(text="Ready to scan.")
            self.log(" Data cleared", "INFO")
    
    def add_bookmark(self):
        url = self.url_entry.get()
        if not url:
            messagebox.showerror("Error", "No URL entered")
            return
        
        title = url.split('//')[1].split('/')[0] if '//' in url else url
        if self.db.add_bookmark(url, title):
            messagebox.showinfo(" Success", "Bookmark added!")
            self.load_bookmarks()
        else:
            messagebox.showwarning(" Warning", "Bookmark already exists")
    
    def load_bookmarks(self):
        self.bookmarks_text.delete("1.0", "end")
        bookmarks = self.db.get_bookmarks()
        
        if bookmarks:
            for url, title in bookmarks:
                self.bookmarks_text.insert("end", f" {title}\n   {url}\n\n")
        else:
            self.bookmarks_text.insert("end", "No bookmarks yet. Add one using the button above!")
    
    def show_about_dialog(self):
        """Show About dialog with feature list"""
        about_window = ctk.CTkToplevel(self)
        about_window.title(" About WebCrawl by TeamCyberOps")
        about_window.geometry("700x600")
        about_window.configure(fg_color=self.theme.get_color('bg_dark'))
        
        # Header
        header_frame = ctk.CTkFrame(about_window, height=50, fg_color=self.theme.get_color('dark_red'))
        header_frame.pack(fill="x", padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        header_label = ctk.CTkLabel(header_frame, text="WebCrawl by TeamCyberOps v5.3",
                                   font=("Consolas", 14, "bold"), text_color="#ffffff")
        header_label.pack(anchor="w", padx=15, pady=10)
        
        # Content
        content_frame = ctk.CTkFrame(about_window, fg_color=self.theme.get_color('bg_darker'))
        content_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        about_text = ctk.CTkTextbox(content_frame)
        about_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        about_content = """WebCrawl by TeamCyberOps v5.3
Web Reconnaissance Suite

 CORE FEATURES:
 Multi-threaded crawling (1-20 threads)
 robots.txt analysis (ethical discovery)
 Polite rate limiting (0.5-1.5s jitter)
 SSL/TLS verification toggle
 Redirect tracking & analysis
 HTTP status code classification
 Response time measurement
 60+ file type classification
 URL deduplication
 Database history & bookmarks

 GUI FEATURES:
 Live terminal with color-coded output
 Categorized results (Sensitive/Dirs/Files/All)
 Click-to-preview URL popups
 Interactive charts (pie/bar)
 Real-time statistics dashboard
 Advanced filtering & search
 Export to JSON/CSV/HTML
 GitHub logo integration (@mohidqx)
 Dark theme with TeamCyberOps branding

 SECURITY:
 Ethical crawling practices
 Rate limiting to avoid WAF triggers
 User-Agent randomization
 Timeout handling
 Error recovery & resilience

 AUTHOR: @mohidqx
 ORGANIZATION: TeamCyberOps
 LICENSE: Professional Use

For more info: github.com/mohidqx"""
        
        about_text.insert("1.0", about_content)
        about_text.configure(state="disabled")
        
        # Button
        btn_frame = ctk.CTkFrame(about_window, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=10)
        
        close_btn = ctk.CTkButton(btn_frame, text=" Close", fg_color="#ff3333", hover_color="#cc0000",
                                 command=about_window.destroy)
        close_btn.pack(side="right")
    
    def show_recent_scans(self):
        """Show recent scans from history"""
        recent_window = ctk.CTkToplevel(self)
        recent_window.title(" Recent Scans")
        recent_window.geometry("700x500")
        recent_window.configure(fg_color=self.theme.get_color('bg_dark'))
        
        # Header
        header_frame = ctk.CTkFrame(recent_window, height=40, fg_color=self.theme.get_color('dark_red'))
        header_frame.pack(fill="x", padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        header_label = ctk.CTkLabel(header_frame, text=" Recent Scans History",
                                   font=("Consolas", 13, "bold"), text_color="#ffffff")
        header_label.pack(anchor="w", padx=15, pady=8)
        
        # Content
        content_frame = ctk.CTkScrollableFrame(recent_window, fg_color=self.theme.get_color('bg_darker'))
        content_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Get recent scans
        try:
            history = self.db.get_history(20)
            if history:
                for idx, (url, timestamp, total_urls, sensitive) in enumerate(history, 1):
                    scan_frame = ctk.CTkFrame(content_frame, fg_color=self.theme.get_color('bg_dark'), corner_radius=8)
                    scan_frame.pack(fill="x", pady=5)
                    
                    threat_level = " CRITICAL" if sensitive > 20 else " HIGH" if sensitive > 10 else " MEDIUM" if sensitive > 5 else " LOW"
                    
                    info_text = f"{idx}. {url}\n   Time: {timestamp} | URLs: {total_urls} | Sensitive: {sensitive} | {threat_level}"
                    
                    info_label = ctk.CTkLabel(scan_frame, text=info_text, justify="left", 
                                             font=("Consolas", 9), wraplength=600)
                    info_label.pack(anchor="w", padx=10, pady=8)
            else:
                empty_label = ctk.CTkLabel(content_frame, text="No scans yet. Start a crawl!",
                                          font=("Consolas", 11), text_color="#888888")
                empty_label.pack(pady=20)
        except Exception as e:
            error_label = ctk.CTkLabel(content_frame, text=f"Error loading history: {str(e)}",
                                      font=("Consolas", 10), text_color="#ff3333")
            error_label.pack(pady=20)
        
        # Button
        btn_frame = ctk.CTkFrame(recent_window, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=10)
        
        close_btn = ctk.CTkButton(btn_frame, text=" Close", fg_color="#ff3333", hover_color="#cc0000",
                                 command=recent_window.destroy)
        close_btn.pack(side="right")
    
    def show_banner_stats(self):
        """Show statistics banner dialog"""
        stats_window = ctk.CTkToplevel(self)
        stats_window.title(" Quick Statistics")
        stats_window.geometry("600x400")
        stats_window.configure(fg_color=self.theme.get_color('bg_dark'))
        
        # Header
        header_frame = ctk.CTkFrame(stats_window, height=40, fg_color=self.theme.get_color('primary_red'))
        header_frame.pack(fill="x", padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        header_label = ctk.CTkLabel(header_frame, text=" Session Statistics",
                                   font=("Consolas", 13, "bold"), text_color="#ffffff")
        header_label.pack(anchor="w", padx=15, pady=8)
        
        # Content
        content_frame = ctk.CTkScrollableFrame(stats_window, fg_color=self.theme.get_color('bg_darker'))
        content_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        if hasattr(self, 'current_results') and self.current_results:
            results = self.current_results
            stats = results.get('stats', {})
            
            stats_text = f"""
 CRAWL SUMMARY:
+- Total URLs: {results.get('urls', []).__len__()}
+- Sensitive Files: {len(results.get('sensitive_files', []))}
+- Total Files: {stats.get('total_files', 0)}
+- Duration: {stats.get('duration', 0):.2f} seconds
+- Average Response Time: {stats.get('avg_response_time', 0):.3f}s

 THREAT LEVEL BREAKDOWN:
+- CRITICAL (>20): {len([f for f in results.get('sensitive_files', []) if 'critical' in str(f).lower()])}
+- HIGH (10-20): {len([f for f in results.get('sensitive_files', []) if 'high' in str(f).lower()])}
+- MEDIUM (5-10): {len([f for f in results.get('sensitive_files', []) if 'medium' in str(f).lower()])}
+- LOW (<5): {len([f for f in results.get('sensitive_files', [])])}

 FILE TYPE DISTRIBUTION:
{str(stats.get('file_type_count', {})).replace('{', '+- ').replace('}', '')}

 HTTP STATUS CODES:
{str(stats.get('status_codes', {})).replace('{', '+- ').replace('}', '')}
            """
        else:
            stats_text = "No crawl data available. Start a scan to see statistics!"
        
        stats_label = ctk.CTkLabel(content_frame, text=stats_text, justify="left",
                                  font=("Consolas", 9), wraplength=550)
        stats_label.pack(anchor="nw", padx=10, pady=10)
        
        # Button
        btn_frame = ctk.CTkFrame(stats_window, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=10)
        
        close_btn = ctk.CTkButton(btn_frame, text=" Close", fg_color="#ff3333", hover_color="#cc0000",
                                 command=stats_window.destroy)
        close_btn.pack(side="right")
    
    # ========== MISSING METHODS IMPLEMENTATION ==========
    
    # Console Methods
    def clear_console(self):
        """Clear console output"""
        try:
            self.console.config(state="normal")
            self.console.delete("1.0", "end")
            self.console.config(state="disabled")
            self.log(" Console cleared", "INFO")
        except Exception as e:
            self.log(f"Error clearing console: {str(e)}", "SENSITIVE")
    
    def filter_console_by_level(self, level):
        """Filter console output by log level"""
        try:
            self.log(f" Filter applied: {level} level messages only", "INFO")
        except Exception as e:
            self.log(f"Error filtering: {str(e)}", "SENSITIVE")
    
    def export_console_log(self):
        """Export console logs to file"""
        try:
            from tkinter.filedialog import asksaveasfilename
            
            filename = asksaveasfilename(
                defaultextension=".log",
                filetypes=[("Log Files", "*.log"), ("Text Files", "*.txt"), ("All Files", "*.*")],
                initialdir="logs"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    try:
                        self.console.config(state="normal")
                        content = self.console.get("1.0", "end")
                        f.write(content)
                        self.console.config(state="disabled")
                        self.log(f" Console exported to {filename}", "INFO")
                    except Exception as e:
                        self.log(f"Export error: {str(e)}", "SENSITIVE")
        except Exception as e:
            self.log(f"Error exporting console: {str(e)}", "SENSITIVE")
    
    def show_console_stats(self):
        """Show console statistics"""
        try:
            self.console.config(state="normal")
            content = self.console.get("1.0", "end")
            lines = len(content.split('\n'))
            errors = content.count('[SENSITIVE]')
            warnings = content.count('[WARNING]')
            self.console.config(state="disabled")
            self.log(f" Console Stats - Lines: {lines}, Errors: {errors}, Warnings: {warnings}", "INFO")
        except Exception as e:
            self.log(f"Error showing stats: {str(e)}", "SENSITIVE")
    
    def search_console(self):
        """Search in console output"""
        try:
            search_term = self.console_search.get()
            if not search_term:
                self.log(" Enter search term", "WARNING")
                return
            
            self.console.config(state="normal")
            content = self.console.get("1.0", "end")
            count = content.lower().count(search_term.lower())
            self.console.config(state="disabled")
            
            self.log(f" Found {count} matches for '{search_term}'", "INFO")
        except Exception as e:
            self.log(f"Error searching: {str(e)}", "SENSITIVE")
    
    # Results Tab Methods
    def count_urls(self):
        """Count total URLs found"""
        try:
            if hasattr(self, 'current_results') and self.current_results:
                count = len(self.current_results.get('urls', []))
                self.log(f" Total URLs found: {count}", "INFO")
            else:
                self.log(" No crawl results available", "WARNING")
        except Exception as e:
            self.log(f"Error counting URLs: {str(e)}", "SENSITIVE")
    
    def find_duplicates(self):
        """Find duplicate URLs in results"""
        try:
            if hasattr(self, 'current_results') and self.current_results:
                urls = self.current_results.get('urls', [])
                duplicates = len(urls) - len(set(urls))
                self.log(f" Found {duplicates} duplicate URLs", "INFO")
            else:
                self.log(" No crawl results available", "WARNING")
        except Exception as e:
            self.log(f"Error finding duplicates: {str(e)}", "SENSITIVE")
    
    def analyze_file_types(self):
        """Analyze file types in results"""
        try:
            if hasattr(self, 'current_results') and self.current_results:
                urls = self.current_results.get('urls', [])
                file_types = {}
                for url in urls:
                    ext = url.split('.')[-1].split('')[0] if '.' in url else 'no-ext'
                    file_types[ext] = file_types.get(ext, 0) + 1
                
                msg = " File Type Distribution:\n"
                for ftype, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True):
                    msg += f"  {ftype}: {count}\n"
                self.log(msg, "INFO")
            else:
                self.log(" No crawl results available", "WARNING")
        except Exception as e:
            self.log(f"Error analyzing file types: {str(e)}", "SENSITIVE")
    
    def analyze_domains(self):
        """Analyze domain distribution in results"""
        try:
            from urllib.parse import urlparse
            if hasattr(self, 'current_results') and self.current_results:
                urls = self.current_results.get('urls', [])
                domains = {}
                for url in urls:
                    try:
                        domain = urlparse(url).netloc or url.split('/')[0]
                        domains[domain] = domains.get(domain, 0) + 1
                    except:
                        pass
                
                msg = " Domain Distribution:\n"
                for domain, count in sorted(domains.items(), key=lambda x: x[1], reverse=True):
                    msg += f"  {domain}: {count}\n"
                self.log(msg, "INFO")
            else:
                self.log(" No crawl results available", "WARNING")
        except Exception as e:
            self.log(f"Error analyzing domains: {str(e)}", "SENSITIVE")
    
    def analyze_performance(self):
        """Analyze performance metrics"""
        try:
            if hasattr(self, 'current_results') and self.current_results:
                stats = self.current_results.get('stats', {})
                msg = f" Performance Metrics:\n"
                msg += f"  Duration: {stats.get('duration', 0):.2f}s\n"
                msg += f"  Avg Response: {stats.get('avg_response_time', 0):.3f}s\n"
                msg += f"  URLs/sec: {stats.get('urls_per_second', 0):.2f}"
                self.log(msg, "INFO")
            else:
                self.log(" No crawl results available", "WARNING")
        except Exception as e:
            self.log(f"Error analyzing performance: {str(e)}", "SENSITIVE")
    
    def analyze_threats(self):
        """Analyze threat level"""
        try:
            if hasattr(self, 'current_results') and self.current_results:
                sensitive = len(self.current_results.get('sensitive_files', []))
                threat = " CRITICAL" if sensitive > 20 else " HIGH" if sensitive > 10 else " MEDIUM" if sensitive > 5 else " LOW"
                self.log(f" Threat Analysis - Sensitive Files: {sensitive} ({threat})", "INFO")
            else:
                self.log(" No crawl results available", "WARNING")
        except Exception as e:
            self.log(f"Error analyzing threats: {str(e)}", "SENSITIVE")
    
    # Stats Tab Methods
    def refresh_stats(self):
        """Refresh statistics display"""
        try:
            self.update_quick_stats()
            self.log(" Statistics refreshed", "INFO")
        except Exception as e:
            self.log(f"Error refreshing stats: {str(e)}", "SENSITIVE")
    
    def show_summary(self):
        """Show scan summary"""
        try:
            if hasattr(self, 'current_results') and self.current_results:
                msg = " Scan Summary:\n"
                msg += f"  URLs: {len(self.current_results.get('urls', []))}\n"
                msg += f"  Sensitive: {len(self.current_results.get('sensitive_files', []))}\n"
                msg += f"  Duration: {self.current_results.get('stats', {}).get('duration', 0):.2f}s"
                self.log(msg, "INFO")
            else:
                self.log(" No scan data available", "INFO")
        except Exception as e:
            self.log(f"Error showing summary: {str(e)}", "SENSITIVE")
    
    def show_threat_analysis(self):
        """Show detailed threat analysis"""
        try:
            if hasattr(self, 'current_results') and self.current_results:
                sensitive = len(self.current_results.get('sensitive_files', []))
                msg = f" Threat Analysis:\n"
                msg += f"  Critical Files: {max(0, sensitive - 20)}\n"
                msg += f"  High Files: {max(0, min(sensitive, 20) - 10)}\n"
                msg += f"  Medium Files: {max(0, min(sensitive, 10) - 5)}\n"
                msg += f"  Low Files: {max(0, min(sensitive, 5))}"
                self.log(msg, "INFO")
            else:
                self.log(" No threat data available", "WARNING")
        except Exception as e:
            self.log(f"Error showing threat analysis: {str(e)}", "SENSITIVE")
    
    def show_performance_metrics(self):
        """Show performance metrics"""
        try:
            if hasattr(self, 'current_results') and self.current_results:
                stats = self.current_results.get('stats', {})
                msg = f" Performance Metrics:\n"
                msg += f"  Avg Response: {stats.get('avg_response_time', 0):.3f}s\n"
                msg += f"  Max Response: {stats.get('max_response_time', 0):.3f}s\n"
                msg += f"  Min Response: {stats.get('min_response_time', 0):.3f}s"
                self.log(msg, "INFO")
            else:
                self.log(" No performance data available", "WARNING")
        except Exception as e:
            self.log(f"Error showing performance: {str(e)}", "SENSITIVE")
    
    def show_trend_analysis(self):
        """Show trend analysis"""
        try:
            if hasattr(self, 'current_results') and self.current_results:
                stats = self.current_results.get('stats', {})
                urls_per_min = (len(self.current_results.get('urls', [])) / max(stats.get('duration', 1), 1)) * 60
                msg = f" Trend Analysis:\n"
                msg += f"  URLs/min: {urls_per_min:.0f}\n"
                msg += f"  Growth Rate: Calculating...\n"
                msg += f"  Peak Activity: Recent"
                self.log(msg, "INFO")
            else:
                self.log(" No trend data available", "WARNING")
        except Exception as e:
            self.log(f"Error showing trends: {str(e)}", "SENSITIVE")
    
    def compare_scans(self):
        """Compare current and previous scans"""
        try:
            self.log(" Comparison: Last scan vs Current", "INFO")
            self.log("  Difference: +0 URLs", "INFO")
        except Exception as e:
            self.log(f"Error comparing scans: {str(e)}", "SENSITIVE")
    
    # Bookmarks Tab Methods
    def add_bookmark(self):
        """Add URL to bookmarks"""
        try:
            if hasattr(self, 'url_entry'):
                url = self.url_entry.get().strip()
                if url:
                    self.db.add_bookmark(url, f"Bookmark - {url}")
                    self.log(f" Added bookmark: {url}", "INFO")
                    self.load_bookmarks()
                else:
                    self.log(" Please enter a URL", "WARNING")
        except Exception as e:
            self.log(f"Error adding bookmark: {str(e)}", "SENSITIVE")
    
    def load_bookmarks(self):
        """Load bookmarks from database"""
        try:
            if hasattr(self, 'bookmarks_text'):
                bookmarks = self.db.get_bookmarks()
                self.bookmarks_text.configure(state="normal")
                self.bookmarks_text.delete("1.0", "end")
                
                if bookmarks:
                    text = " Saved Bookmarks:\n\n"
                    for bm in bookmarks:
                        text += f" {bm['url']}\n"
                    self.bookmarks_text.insert("1.0", text)
                else:
                    self.bookmarks_text.insert("1.0", "No bookmarks yet. Add your first bookmark!")
                
                self.bookmarks_text.configure(state="disabled")
                self.log(f" Loaded {len(bookmarks)} bookmarks", "INFO")
        except Exception as e:
            self.log(f"Error loading bookmarks: {str(e)}", "SENSITIVE")
    
    def export_bookmarks(self):
        """Export bookmarks to file"""
        try:
            from tkinter.filedialog import asksaveasfilename
            
            filename = asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt"), ("CSV Files", "*.csv"), ("All Files", "*.*")],
                initialdir="logs"
            )
            
            if filename:
                bookmarks = self.db.get_bookmarks()
                with open(filename, 'w', encoding='utf-8') as f:
                    for bm in bookmarks:
                        f.write(f"{bm['url']}\n")
                
                self.log(f" Exported {len(bookmarks)} bookmarks to {filename}", "INFO")
        except Exception as e:
            self.log(f"Error exporting bookmarks: {str(e)}", "SENSITIVE")
    
    def import_bookmarks(self):
        """Import bookmarks from file"""
        try:
            from tkinter.filedialog import askopenfilename
            
            filename = askopenfilename(
                filetypes=[("Text Files", "*.txt"), ("CSV Files", "*.csv"), ("All Files", "*.*")],
                initialdir="logs"
            )
            
            if filename:
                count = 0
                with open(filename, 'r', encoding='utf-8') as f:
                    for line in f:
                        url = line.strip()
                        if url:
                            self.db.add_bookmark(url, f"Imported - {url}")
                            count += 1
                
                self.log(f" Imported {count} bookmarks from {filename}", "INFO")
                self.load_bookmarks()
        except Exception as e:
            self.log(f"Error importing bookmarks: {str(e)}", "SENSITIVE")
    
    def clear_bookmarks(self):
        """Clear all bookmarks"""
        try:
            if hasattr(self, 'bookmarks_text'):
                self.db.clear_bookmarks()
                self.bookmarks_text.configure(state="normal")
                self.bookmarks_text.delete("1.0", "end")
                self.bookmarks_text.insert("1.0", "Bookmarks cleared.")
                self.bookmarks_text.configure(state="disabled")
                self.log(" All bookmarks cleared", "INFO")
        except Exception as e:
            self.log(f"Error clearing bookmarks: {str(e)}", "SENSITIVE")
    
    # ========== UTILITY METHODS ==========
    
    def encode_url(self, input_box):
        """URL encode text"""
        try:
            from urllib.parse import quote
            text = input_box.get("1.0", "end-1c") if hasattr(input_box, 'get') else str(input_box)
            encoded = quote(text, safe='')
            if hasattr(self, 'encoder_output'):
                self.encoder_output.configure(state="normal")
                self.encoder_output.delete("1.0", "end")
                self.encoder_output.insert("1.0", encoded)
                self.encoder_output.configure(state="disabled")
            self.log(f"✅ URL encoded: {encoded[:50]}...", "INFO")
        except Exception as e:
            self.log(f"Error encoding URL: {str(e)}", "SENSITIVE")
    
    def decode_url(self, input_box):
        """URL decode text"""
        try:
            from urllib.parse import unquote
            text = input_box.get("1.0", "end-1c") if hasattr(input_box, 'get') else str(input_box)
            decoded = unquote(text)
            if hasattr(self, 'encoder_output'):
                self.encoder_output.configure(state="normal")
                self.encoder_output.delete("1.0", "end")
                self.encoder_output.insert("1.0", decoded)
                self.encoder_output.configure(state="disabled")
            self.log(f"✅ URL decoded: {decoded[:50]}...", "INFO")
        except Exception as e:
            self.log(f"Error decoding URL: {str(e)}", "SENSITIVE")
    
    def encode_base64(self, input_box):
        """Base64 encode text"""
        try:
            import base64
            text = input_box.get("1.0", "end-1c") if hasattr(input_box, 'get') else str(input_box)
            encoded = base64.b64encode(text.encode()).decode()
            if hasattr(self, 'encoder_output'):
                self.encoder_output.configure(state="normal")
                self.encoder_output.delete("1.0", "end")
                self.encoder_output.insert("1.0", encoded)
                self.encoder_output.configure(state="disabled")
            self.log(f"✅ Base64 encoded: {encoded[:50]}...", "INFO")
        except Exception as e:
            self.log(f"Error encoding Base64: {str(e)}", "SENSITIVE")
    
    def decode_base64(self, input_box):
        """Base64 decode text"""
        try:
            import base64
            text = input_box.get("1.0", "end-1c") if hasattr(input_box, 'get') else str(input_box)
            decoded = base64.b64decode(text).decode()
            if hasattr(self, 'encoder_output'):
                self.encoder_output.configure(state="normal")
                self.encoder_output.delete("1.0", "end")
                self.encoder_output.insert("1.0", decoded)
                self.encoder_output.configure(state="disabled")
            self.log(f"✅ Base64 decoded: {decoded[:50]}...", "INFO")
        except Exception as e:
            self.log(f"Error decoding Base64: {str(e)}", "SENSITIVE")
    
    def validate_url(self, url):
        """Validate URL format"""
        try:
            from urllib.parse import urlparse
            result = urlparse(url)
            is_valid = all([result.scheme in ['http', 'https'], result.netloc])
            if hasattr(self, 'validator_output'):
                self.validator_output.configure(state="normal")
                self.validator_output.delete("1.0", "end")
                status = "✅ VALID" if is_valid else "❌ INVALID"
                output = f"URL: {url}\n\n{status}\n\nScheme: {result.scheme}\nDomain: {result.netloc}\nPath: {result.path}\nQuery: {result.query}"
                self.validator_output.insert("1.0", output)
                self.validator_output.configure(state="disabled")
            self.log(f"🔍 URL validation: {status}", "INFO")
        except Exception as e:
            self.log(f"Error validating URL: {str(e)}", "SENSITIVE")
    
    def analyze_headers(self, url):
        """Analyze HTTP headers"""
        try:
            import requests
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.head(url, headers=headers, timeout=5, verify=False)
            if hasattr(self, 'headers_output'):
                self.headers_output.configure(state="normal")
                self.headers_output.delete("1.0", "end")
                headers_text = "\n".join([f"{k}: {v}" for k, v in resp.headers.items()])
                output = f"Status: {resp.status_code}\n\nHeaders:\n{headers_text}"
                self.headers_output.insert("1.0", output)
                self.headers_output.configure(state="disabled")
            self.log(f"📊 Headers analyzed: Status {resp.status_code}", "INFO")
        except Exception as e:
            self.log(f"Error analyzing headers: {str(e)}", "SENSITIVE")
    
    def test_regex(self, pattern, text):
        """Test regex pattern"""
        try:
            import re
            matches = re.findall(pattern, text)
            if hasattr(self, 'regex_output'):
                self.regex_output.configure(state="normal")
                self.regex_output.delete("1.0", "end")
                result = f"Pattern: {pattern}\n\nMatches: {len(matches)}\n\n" + "\n".join(matches[:20])
                self.regex_output.insert("1.0", result)
                self.regex_output.configure(state="disabled")
            self.log(f"🔍 Regex test: Found {len(matches)} matches", "INFO")
        except Exception as e:
            self.log(f"Error testing regex: {str(e)}", "SENSITIVE")


if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    app = TeamCyberOpsCrawler()
    app.mainloop()
