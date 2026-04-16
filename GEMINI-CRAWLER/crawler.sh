#!/bin/bash

# Colors for Nuclei Aesthetics
RE=$(tput setaf 1); GR=$(tput setaf 2); YE=$(tput setaf 3)
BL=$(tput setaf 4); MA=$(tput setaf 5); CY=$(tput setaf 6); NC=$(tput sgr0)

# Settings
MAX_DEPTH=4
CURRENT_DIR=$(pwd)
OUTPUT="$CURRENT_DIR/crawl_inventory.txt"
LOG="$CURRENT_DIR/crawler.log"
USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"

declare -A VISITED
> "$OUTPUT"; > "$LOG"

echo -e "${MA}[INFO]${NC} Multi-Layer Crawler v4.0 (Anti-Loop) - TeamCyberOps"

log_finding() {
    local type=$1; local path=$2; local color=$3
    echo -e "[$(date +%H:%M:%S)] [${color}${type}${NC}] $path" | tee -a "$LOG"
}

crawl() {
    local url=$1
    local depth=$2

    # Normalization & Loop Prevention
    url="${url%/}"
    [[ -n "${VISITED[$url]}" ]] && return
    [[ "$depth" -gt "$MAX_DEPTH" ]] && return
    VISITED[$url]=1

    # Fetch content
    local html_content
    html_content=$(curl -s -L -k -A "$USER_AGENT" --max-time 15 "$url/")
    [[ -z "$html_content" ]] && return

    # Extract Links
    echo "$html_content" | grep -oE 'href="([^"#? \t]+)"' | cut -d'"' -f2 | while read -r link; do
        
        # FILTER 1: Skip Navigation/Absolute/Garbage
        [[ "$link" == "../" ]] && continue
        [[ "$link" == "/" ]] && continue
        [[ "$link" == "http"* ]] && continue
        
        # FILTER 2: Specific to your target - ignore "wp-content" inside "uploads"
        # This prevents the recursion trap you're hitting
        [[ "$link" == "wp-content/" ]] && continue

        # Build clean URL
        local full_url="${url}/${link}"

        # Layer 3: Logic for Folders vs Files
        if [[ "$link" == */ ]]; then
            # Only log if it's a new directory
            log_finding "DIR" "$full_url" "$BL"
            echo "$full_url" >> "$OUTPUT"
            crawl "$full_url" $((depth + 1))
        else
            # SENSITIVE FILE DETECTION
            if [[ "$link" =~ \.(sql|zip|log|bak|env|php|txt|pdf|conf|json|db|old|swp|xml)$ ]]; then
                log_finding "SENSITIVE" "$full_url" "$RE"
                echo "$full_url" >> "$OUTPUT"
            else
                echo "$full_url" >> "$OUTPUT"
            fi
        fi
    done
}

process_target() {
    local target=$1
    [[ ! "$target" =~ http ]] && target="https://$target"
    echo -e "\n${BL}[*]${NC} Targeting: ${CY}$target${NC}"
    crawl "$target" 0
}

if [ -z "$1" ]; then
    echo -e "${RE}[!] Usage: ./crawler.sh <url> OR <list.txt>${NC}"
    exit 1
fi

if [ -f "$1" ]; then
    while IFS= read -r line; do [[ -n "$line" ]] && process_target "$line"; done < "$1"
else
    process_target "$1"
fi

echo -e "\n${GR}[+] Done. Results in $OUTPUT${NC}"
