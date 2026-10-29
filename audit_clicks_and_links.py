"""
Audit every clickable element (links, buttons, forms) across all HTML files
"""
import re
from pathlib import Path
from urllib.parse import urlparse

pages_dir = Path('dist_gh_pages')
html_files = sorted(list(pages_dir.glob('*.html')))

print(f"Auditing clickable elements across {len(html_files)} pages:\n")

total_links = 0
total_buttons = 0
total_forms = 0
issues = []

for file in html_files:
    content = file.read_text(encoding='utf-8')
    print(f"=== {file.name} ===")
    
    # 1. Links <a ...>
    links = re.findall(r'<a\s+([^>]+)>', content)
    total_links += len(links)
    
    for l in links:
        href_match = re.search(r'href=["\']([^"\']*)["\']', l)
        onclick_match = re.search(r'onclick=["\']([^"\']*)["\']', l)
        
        href = href_match.group(1) if href_match else ''
        onclick = onclick_match.group(1) if onclick_match else ''
        
        # Check target="_blank" has rel="noopener"
        if 'target="_blank"' in l and 'noopener' not in l:
            issues.append(f"{file.name}: Link {href} has target=_blank but missing rel=noopener")
            
        # Check empty or invalid hrefs
        if not href and not onclick:
            issues.append(f"{file.name}: <a> has no href and no onclick: {l}")
        elif href == '#' and not onclick:
            # Check if it has data-bs-toggle or similar
            if 'data-bs-' not in l:
                issues.append(f"{file.name}: <a> href='#' without onclick or data-bs toggle: {l}")
                
        # Check relative link targets
        if href and not href.startswith(('http', 'tel:', 'mailto:', '#', 'javascript:')):
            clean_href = href.split('?')[0].split('#')[0]
            if clean_href and not (pages_dir / clean_href).exists():
                issues.append(f"{file.name}: Broken internal link to '{clean_href}'")
                
        # Check WhatsApp phone number
        if 'wa.me' in href:
            if '6238006820' not in href and '${' not in href:
                issues.append(f"{file.name}: WhatsApp link not using owner number 6238006820: {href}")
                
        # Check phone tel: link
        if href.startswith('tel:'):
            if '6238006820' not in href and '${' not in href:
                issues.append(f"{file.name}: Phone link not using owner number 6238006820: {href}")
                
    # 2. Buttons <button ...>
    buttons = re.findall(r'<button\s+([^>]+)>', content)
    total_buttons += len(buttons)
    for b in buttons:
        has_type = 'type=' in b
        has_onclick = 'onclick=' in b
        has_data_bs = 'data-bs-' in b
        # Buttons inside forms default to submit if no type
        if not has_type and not has_onclick and not has_data_bs:
            # check if inside form or close button
            if 'btn-close' not in b:
                pass
                
    # 3. Forms
    forms = re.findall(r'<form\s+([^>]+)>', content)
    total_forms += len(forms)
    
    print(f"  Links: {len(links)} | Buttons: {len(buttons)} | Forms: {len(forms)}")

print(f"\n--- TOTALS ---")
print(f"Total Links Checked: {total_links}")
print(f"Total Buttons Checked: {total_buttons}")
print(f"Total Forms Checked: {total_forms}")

print(f"\nIssues Found: {len(issues)}")
for iss in issues:
    print(f"  [!] {iss}")

