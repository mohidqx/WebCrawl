import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import requests
from urllib.parse import urljoin, urlparse
import re
import time
import urllib3

# Suppress InsecureRequestWarning for unverified HTTPS requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Setup TeamCyberOps Branding ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class CyberOpsCrawler(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Config
        self.title("Multi-Layer Recon Crawler v5.5 (Pro Dashboard) - TeamCyberOps | @mohidqx")
        self.geometry("1300x800") # Increased width for split-screen
        
        # Core Variables
        self.is_crawling = False
        self.visited_urls = set()
        
        # Expanded Sensitive Patterns for aggressive vulnerability identification
        self.sensitive_patterns = re.compile(
            r'\.(sql|zip|log|bak|env|php|txt|pdf|conf|json|db|old|swp|xml|git|pem|key|rsa|tar|gz)$|id_rsa', 
            re.IGNORECASE
        )
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        
        self.build_ui()

    def build_ui(self):
        # ---------------- TOP CONTROLS ----------------
        self.control_frame = ctk.CTkFrame(self, height=80)
        self.control_frame.pack(fill="x", padx=10, pady=10)

        self.url_entry = ctk.CTkEntry(self.control_frame, placeholder_text="Enter Target URL (e.g., https://target.com/)", width=450)
        self.url_entry.pack(side="left", padx=10, pady=20)

        self.depth_label = ctk.CTkLabel(self.control_frame, text="Max Depth:")
        self.depth_label.pack(side="left", padx=5)
        
        self.depth_entry = ctk.CTkEntry(self.control_frame, width=50)
        self.depth_entry.insert(0, "4")
        self.depth_entry.pack(side="left", padx=5)

        self.start_btn = ctk.CTkButton(self.control_frame, text="Start Attack", fg_color="green", hover_color="dark green", command=self.start_crawling)
        self.start_btn.pack(side="left", padx=10)

        self.stop_btn = ctk.CTkButton(self.control_frame, text="Stop", fg_color="red", hover_color="dark red", state="disabled", command=self.stop_crawling)
        self.stop_btn.pack(side="left", padx=10)
        
        self.export_btn = ctk.CTkButton(self.control_frame, text="Export Logs", command=self.export_data)
        self.export_btn.pack(side="right", padx=10)

        # ---------------- MAIN DASHBOARD (SPLIT VIEW) ----------------
        self.main_dashboard = ctk.CTkFrame(self, fg_color="transparent")
        self.main_dashboard.pack(fill="both", expand=True, padx=10, pady=5)

        # LEFT PANEL: Attack Surface (Treeview)
        self.left_panel = ctk.CTkFrame(self.main_dashboard, width=400)
        self.left_panel.pack(side="left", fill="y", padx=(0, 5))
        self.left_panel.pack_propagate(False) # Keep width fixed

        self.tree_label = ctk.CTkLabel(self.left_panel, text="🎯 Attack Surface (Site Map)", font=("Consolas", 14, "bold"), text_color="#00bfff")
        self.tree_label.pack(anchor="w", padx=10, pady=(5,0))

        # Styling the Treeview to match dark mode
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#0a0a0a", foreground="#00ff00", fieldbackground="#0a0a0a", borderwidth=0, font=("Consolas", 10))
        style.configure("Treeview.Heading", background="#1f538d", foreground="white", font=("Consolas", 10, "bold"))
        style.map('Treeview', background=[('selected', '#1f538d')])

        self.tree = ttk.Treeview(self.left_panel)
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)
        self.tree.heading("#0", text="Target Directory Structure", anchor="w")
        
        # Tags for Colors in Treeview
        self.tree.tag_configure('DOMAIN', foreground='#ffffff', font=("Consolas", 11, "bold"))
        self.tree.tag_configure('DIR', foreground='#00bfff')
        self.tree.tag_configure('INFO', foreground='#00ff00')
        self.tree.tag_configure('SENSITIVE', foreground='#ff3333', background="#330000")

        scrollbar = ttk.Scrollbar(self.tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # RIGHT PANEL: Live Console
        self.right_panel = ctk.CTkFrame(self.main_dashboard)
        self.right_panel.pack(side="right", fill="both", expand=True, padx=(5, 0))

        self.console_label = ctk.CTkLabel(self.right_panel, text="💻 Live Execution Logs", font=("Consolas", 14, "bold"), text_color="#00ff00")
        self.console_label.pack(anchor="w", padx=10, pady=(5,0))
        
        self.console = tk.Text(self.right_panel, bg="#050505", fg="#ffffff", font=("Consolas", 11), state="disabled")
        self.console.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Tags for Colors in Console
        self.console.tag_config("INFO", foreground="#00ff00")      
        self.console.tag_config("DIR", foreground="#00bfff")       
        self.console.tag_config("SENSITIVE", foreground="#ff3333", font=("Consolas", 11, "bold")) 
        self.console.tag_config("WARNING", foreground="#ffcc00")   

        # ---------------- STATUS BAR ----------------
        self.status_var = ctk.StringVar(value="Status: Ready | System: Idle | TeamCyberOps")
        self.status_bar = ctk.CTkLabel(self, textvariable=self.status_var, font=("Consolas", 12))
        self.status_bar.pack(side="bottom", anchor="w", padx=15, pady=5)

    # --- CORE FUNCTIONS ---

    def log(self, message, tag="INFO"):
        self.console.config(state="normal")
        timestamp = time.strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] [{tag}] {message}\n"
        self.console.insert("end", formatted_msg, tag)
        self.console.see("end")
        self.console.config(state="disabled")

    def update_tree(self, full_url, tag):
        """Thread-safe UI update for the File Manager Tree"""
        parsed = urlparse(full_url)
        domain = parsed.netloc
        path = parsed.path.strip('/')

        if not self.tree.exists(domain):
            self.tree.insert('', 'end', domain, text=f"🌐 {domain}", tags=('DOMAIN',), open=True)

        if not path:
            return

        parts = path.split('/')
        parent = domain
        
        for i, part in enumerate(parts):
            node_id = f"{domain}/{'/'.join(parts[:i+1])}"
            if not self.tree.exists(node_id):
                is_last = (i == len(parts) - 1)
                
                if is_last:
                    node_text = f"📄 {part}" if tag != "DIR" else f"📁 {part}"
                    node_tag = tag
                else:
                    node_text = f"📁 {part}"
                    node_tag = "DIR"

                self.tree.insert(parent, 'end', node_id, text=node_text, tags=(node_tag,))
            parent = node_id

    def start_crawling(self):
        target_url = self.url_entry.get().strip()
        if not target_url:
            messagebox.showerror("Error", "Please enter a valid URL.")
            return

        if not target_url.startswith("http"):
            target_url = "https://" + target_url

        try:
            max_depth = int(self.depth_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Depth must be an integer.")
            return

        self.is_crawling = True
        self.visited_urls.clear()
        
        # Reset UI Elements
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.console.config(state="normal")
        self.console.delete(1.0, "end")
        self.console.config(state="disabled")
        
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.log(f"Initiating Aggressive Recon on: {target_url}", "INFO")
        self.status_var.set(f"Status: Crawling {target_url}...")

        self.crawl_thread = threading.Thread(target=self.crawl, args=(target_url, 0, max_depth, urlparse(target_url).netloc))
        self.crawl_thread.daemon = True
        self.crawl_thread.start()

    def stop_crawling(self):
        self.is_crawling = False
        self.log("Crawl interrupted by user. Halting active threads...", "WARNING")
        self.finish_crawl()

    def finish_crawl(self):
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_var.set(f"Status: Idle | Total Assets Found: {len(self.visited_urls)} | TeamCyberOps")

    def crawl(self, url, current_depth, max_depth, base_domain):
        if not self.is_crawling:
            return
        
        if url in self.visited_urls or current_depth > max_depth:
            return
            
        self.visited_urls.add(url)
        
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }
        
        try:
            # allow_redirects=True ensures we trace the final destination
            response = requests.get(url, headers=headers, timeout=10, verify=False, allow_redirects=True) 
            
            if response.status_code != 200:
                self.log(f"Access Denied/Error [HTTP {response.status_code}] on: {url}", "WARNING")
                return

            html_content = response.text
            links = re.findall(r'(?:href|src)=["\']([^"\'#? \t]+)["\']', html_content, re.IGNORECASE)
            
            if current_depth == 0 and not links:
                self.log(f"No valid links found. Target might be heavily JS-rendered or WAF blocked.", "WARNING")

            for link in links:
                if not self.is_crawling:
                    break

                if link in ["../", "/", ""] or link.lower().startswith(("javascript:", "mailto:", "tel:", "data:")):
                    continue
                
                full_url = urljoin(response.url, link)
                
                if urlparse(full_url).netloc != base_domain:
                    continue

                if full_url not in self.visited_urls:
                    if self.sensitive_patterns.search(full_url):
                        self.visited_urls.add(full_url)
                        self.log(f"CRITICAL ASSET FOUND: {full_url}", "SENSITIVE")
                        self.after(0, self.update_tree, full_url, "SENSITIVE")
                    elif full_url.endswith('/') or not "." in full_url.split("/")[-1]:
                        self.log(f"DIR DISCOVERED: {full_url}", "DIR")
                        self.after(0, self.update_tree, full_url, "DIR")
                        self.crawl(full_url, current_depth + 1, max_depth, base_domain)
                    else:
                        self.visited_urls.add(full_url)
                        self.log(full_url, "INFO")
                        self.after(0, self.update_tree, full_url, "INFO")
                            
        except requests.exceptions.Timeout:
            self.log(f"Timeout on: {url} (Possible WAF drop or Rate Limit)", "WARNING")
        except requests.exceptions.RequestException as e:
            self.log(f"Connection Error: {url}", "WARNING")
            
        if current_depth == 0:
            self.log("Recon Phase Completed Successfully.", "INFO")
            self.after(0, self.finish_crawl)

    def export_data(self):
        if not self.visited_urls:
            messagebox.showinfo("Info", "No data to export.")
            return
            
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file_path:
            with open(file_path, "w") as f:
                for url in sorted(self.visited_urls):
                    f.write(url + "\n")
            messagebox.showinfo("Success", f"Data exported successfully to {file_path}")

if __name__ == "__main__":
    app = CyberOpsCrawler()
    app.mainloop()