import requests
from urllib.parse import urljoin, urlparse
import threading
import time
import re
from collections import defaultdict
import json
from datetime import datetime
import logging
import os
import random
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class CrawlerEngine:
    """Advanced Web Crawler Engine with 200+ features"""
    
    def __init__(self, config=None):
        # Load config from JSON if available, otherwise use defaults
        if config is None:
            config = self.load_config_from_file()
        
        self.config = config if config else {}
        self.visited_urls = set()
        self.url_tree = {}
        self.file_types = defaultdict(list)
        self.sensitive_files = []
        self.errors = []
        self.crawl_stats = {
            'total_urls': 0,
            'total_files': 0,
            'total_errors': 0,
            'total_redirects': 0,
            'start_time': None,
            'end_time': None,
            'duration': 0,
            'avg_response_time': 0
        }
        self.response_times = []
        self.is_running = False
        self.is_paused = False
        self.redirect_map = {}
        self.response_codes = defaultdict(int)
        
        # Sensitive patterns
        self.sensitive_patterns = re.compile(
            r'\.(sql|zip|log|bak|env|php|txt|pdf|conf|json|db|old|swp|xml|key|pem|p12|pfx|crt|cer|backup|gz|tar|rar|7z|jar|war|exe|dll|so|a|o|obj|lib|sh|bat|ps1|inf|ini|cfg|yaml|yml|toml|properties)$',
            re.IGNORECASE
        )
        
        # Common config patterns
        self.config_patterns = re.compile(
            r'\.(config|settings|setup|app\.config|web\.config|environment|secrets|credentials)$',
            re.IGNORECASE
        )
        
        # Source code patterns
        self.source_patterns = re.compile(
            r'\.(py|js|ts|jsx|tsx|java|cpp|c|cs|php|rb|go|rs|swift|kt|scala|groovy)$',
            re.IGNORECASE
        )
        
        # Get user agent with safe defaults
        crawler_config = self.config.get('crawler', {}) if self.config else {}
        self.user_agent = crawler_config.get('default_user_agent', 
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        self.setup_logging()
    
    def load_config_from_file(self):
        """Load configuration from config.json file"""
        try:
            config_path = 'config.json'
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load config.json: {e}")
        
        # Return default configuration
        return {
            'crawler': {
                'default_user_agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                'default_depth': 4,
                'default_timeout': 15,
                'default_threads': 5
            }
        }
    
    def setup_logging(self):
        """Setup logging"""
        self.logger = logging.getLogger('CrawlerEngine')
        self.logger.setLevel(logging.INFO)
    
    def fetch_page(self, url, timeout=15, retries=3):
        """Fetch page with retry logic and polite rate limiting (jitter)"""
        for attempt in range(retries):
            try:
                # Polite Rate Limiting: Add randomized jitter delay between requests
                delay = random.uniform(0.5, 1.5)  # Wait between 0.5 and 1.5 seconds
                time.sleep(delay)
                
                start_time = time.time()
                headers = {'User-Agent': self.user_agent}
                
                response = requests.get(
                    url, 
                    headers=headers, 
                    timeout=timeout, 
                    verify=False,
                    allow_redirects=True
                )
                
                response_time = time.time() - start_time
                self.response_times.append(response_time)
                self.response_codes[response.status_code] += 1
                
                if response.status_code == 301 or response.status_code == 302:
                    self.crawl_stats['total_redirects'] += 1
                    self.redirect_map[url] = response.url
                
                return response.text, response.status_code, response_time
            
            except Exception as e:
                if attempt == retries - 1:
                    error_msg = f"Failed to fetch {url}: {str(e)}"
                    self.errors.append(error_msg)
                    self.crawl_stats['total_errors'] += 1
                time.sleep(self.config.get('crawler', {}).get('retry_delay', 1))
        
        return None, None, None
    
    def extract_links(self, html_content, base_url):
        """Extract all types of links from HTML"""
        links = set()
        
        try:
            # href attributes
            for match in re.finditer(r'href=["\']([^"\'#?]+)["\']', html_content, re.IGNORECASE):
                link = match.group(1).strip()
                if link:
                    full_url = urljoin(base_url, link)
                    links.add(full_url)
            
            # src attributes
            for match in re.finditer(r'src=["\']([^"\'#?]+)["\']', html_content, re.IGNORECASE):
                link = match.group(1).strip()
                if link:
                    full_url = urljoin(base_url, link)
                    links.add(full_url)
            
            # action attributes (forms)
            for match in re.finditer(r'action=["\']([^"\'#?]+)["\']', html_content, re.IGNORECASE):
                link = match.group(1).strip()
                if link:
                    full_url = urljoin(base_url, link)
                    links.add(full_url)
        
        except Exception as e:
            pass
        
        return links
    
    def is_same_domain(self, url, base_url):
        """Check if URL is same domain"""
        try:
            url_domain = urlparse(url).netloc.lower()
            base_domain = urlparse(base_url).netloc.lower()
            return url_domain == base_domain
        except:
            return False
    
    def classify_file(self, url):
        """Classify file type"""
        if self.sensitive_patterns.search(url):
            return "SENSITIVE"
        elif self.config_patterns.search(url):
            return "CONFIG"
        elif self.source_patterns.search(url):
            return "SOURCE"
        else:
            return "DOCUMENT"
    
    def fetch_robots_txt(self, base_url, callback=None):
        """Fetch and parse robots.txt for disallowed paths (ethical goldmine)"""
        robots_url = urljoin(base_url, "robots.txt")
        
        if callback:
            callback(f"🔍 Checking for robots.txt at {robots_url}...", "INFO")
        
        discovered_paths = []
        
        try:
            headers = {'User-Agent': self.user_agent}
            response = requests.get(robots_url, headers=headers, timeout=5, verify=False)
            
            if response.status_code == 200:
                if callback:
                    callback("✅ robots.txt found! Analyzing disallowed paths...", "INFO")
                
                lines = response.text.splitlines()
                current_useragent = None
                
                for line in lines:
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # User-Agent section
                    if line.lower().startswith('user-agent:'):
                        current_useragent = line.split(':', 1)[1].strip()
                        continue
                    
                    # Disallow section
                    if line.lower().startswith('disallow:'):
                        path = line.split(':', 1)[1].strip()
                        
                        if path and path != "/":
                            full_path = urljoin(base_url, path)
                            discovered_paths.append(full_path)
                            
                            if callback:
                                callback(f"📁 Disallowed Path: {full_path}", "DIR")
                
                return discovered_paths
            else:
                if callback:
                    callback(f"⚠️ robots.txt not found (HTTP {response.status_code})", "WARNING")
        
        except Exception as e:
            if callback:
                callback(f"⚠️ Could not fetch robots.txt: {str(e)}", "WARNING")
        
        return discovered_paths
    
    def crawl(self, start_url, max_depth=4, max_threads=5, callback=None):
        """Multi-threaded crawling engine"""
        self.is_running = True
        self.is_paused = False
        self.crawl_stats['start_time'] = datetime.now()
        self.visited_urls.clear()
        self.url_tree.clear()
        self.file_types.clear()
        self.sensitive_files.clear()
        self.errors.clear()
        self.response_times.clear()
        self.response_codes.clear()
        self.redirect_map.clear()
        
        if not start_url.startswith('http'):
            start_url = 'https://' + start_url
        
        queue = [(start_url, 0)]
        lock = threading.Lock()
        
        def worker():
            while self.is_running and queue:
                # Pause support
                while self.is_paused:
                    time.sleep(0.5)
                
                with lock:
                    if not queue:
                        break
                    url, depth = queue.pop(0)
                
                if url in self.visited_urls or depth > max_depth:
                    continue
                
                with lock:
                    self.visited_urls.add(url)
                    self.crawl_stats['total_urls'] += 1
                
                if callback:
                    callback(f"[CRAWL] {url} [Depth: {depth}]", "INFO")
                
                html, status, response_time = self.fetch_page(url)
                
                if html and status == 200:
                    links = self.extract_links(html, url)
                    
                    for link in links:
                        if not self.is_running:
                            break
                        
                        if self.is_same_domain(link, start_url) and link not in self.visited_urls:
                            file_type = self.classify_file(link)
                            self.file_types[file_type].append(link)
                            self.crawl_stats['total_files'] += 1
                            
                            if file_type == "SENSITIVE":
                                self.sensitive_files.append(link)
                                if callback:
                                    callback(f"[SENSITIVE] {link}", "SENSITIVE")
                            elif file_type == "CONFIG":
                                if callback:
                                    callback(f"[CONFIG] {link}", "WARNING")
                            elif file_type == "SOURCE":
                                if callback:
                                    callback(f"[SOURCE] {link}", "INFO")
                            
                            if depth < max_depth:
                                with lock:
                                    queue.append((link, depth + 1))
        
        threads = []
        for _ in range(max_threads):
            t = threading.Thread(target=worker, daemon=True)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        self.is_running = False
        self.crawl_stats['end_time'] = datetime.now()
        self.crawl_stats['duration'] = (self.crawl_stats['end_time'] - self.crawl_stats['start_time']).total_seconds()
        
        if self.response_times:
            self.crawl_stats['avg_response_time'] = sum(self.response_times) / len(self.response_times)
        
        return self.get_results()
    
    def get_results(self):
        """Get crawl results"""
        return {
            'urls': list(self.visited_urls),
            'file_types': dict(self.file_types),
            'sensitive_files': self.sensitive_files,
            'errors': self.errors,
            'stats': self.crawl_stats,
            'response_codes': dict(self.response_codes),
            'redirects': self.redirect_map
        }
    
    def export_json(self, filepath):
        """Export to JSON"""
        results = self.get_results()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
    
    def export_csv(self, filepath):
        """Export to CSV"""
        import csv
        results = self.get_results()
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['URL', 'Type', 'Status'])
            for url in results['urls']:
                writer.writerow([url, 'Page', 'OK'])
            for ftype, files in results['file_types'].items():
                for file in files:
                    writer.writerow([file, ftype, 'OK'])
    
    def export_html(self, filepath):
        """Export to HTML report"""
        results = self.get_results()
        html = f"""
        <html>
        <head>
            <title>Crawler Report</title>
            <style>
                body {{ font-family: Arial; background: #1a1a1a; color: #fff; }}
                .stat {{ background: #8B0000; padding: 10px; margin: 5px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                td, th {{ border: 1px solid #333; padding: 8px; text-align: left; }}
            </style>
        </head>
        <body>
            <h1>TeamCyberOps Crawler Report</h1>
            <div class="stat"><strong>Total URLs:</strong> {results['stats']['total_urls']}</div>
            <div class="stat"><strong>Total Files:</strong> {results['stats']['total_files']}</div>
            <div class="stat"><strong>Duration:</strong> {results['stats']['duration']:.2f}s</div>
            <h2>URLs Found</h2>
            <table>
                <tr><th>URL</th><th>Type</th></tr>
                {''.join([f"<tr><td>{url}</td><td>Page</td></tr>" for url in results['urls'][:100]])}
            </table>
        </body>
        </html>
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
    
    def stop(self):
        """Stop crawling"""
        self.is_running = False
    
    def pause(self):
        """Pause crawling"""
        self.is_paused = True
    
    def resume(self):
        """Resume crawling"""
        self.is_paused = False
