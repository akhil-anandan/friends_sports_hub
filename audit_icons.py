"""
Audit all icons across all HTML files in dist_gh_pages and templates
"""
import re
from pathlib import Path

pages_dir = Path('dist_gh_pages')
html_files = list(pages_dir.glob('*.html'))

print(f"Auditing {len(html_files)} HTML files in dist_gh_pages:")

icon_usage = {}
missing_cdn = []
total_icons_found = 0

for file in sorted(html_files):
    content = file.read_text(encoding='utf-8')
    
    # Check Bootstrap Icons link
    has_bi_cdn = 'bootstrap-icons' in content
    if not has_bi_cdn:
        missing_cdn.append(file.name)
        
    # Find all <i class="..."> tags
    matches = re.findall(r'<i\s+class=["\']([^"\']+)["\']', content)
    total_icons_found += len(matches)
    
    file_icons = []
    for cls in matches:
        classes = cls.split()
        bi_classes = [c for c in classes if c.startswith('bi-')]
        file_icons.extend(bi_classes)
        for bi in bi_classes:
            icon_usage[bi] = icon_usage.get(bi, 0) + 1
            
    print(f" - {file.name:15}: {len(matches)} icons (CDN linked: {has_bi_cdn})")

print(f"\nTotal icon occurrences: {total_icons_found}")
print(f"Unique icon classes: {len(icon_usage)}")
print("\nUnique Icons Found:")
for icon, count in sorted(icon_usage.items()):
    print(f"  {icon:30} : used {count} times")

if missing_cdn:
    print(f"\nWARNING: Bootstrap Icons CDN missing in: {missing_cdn}")
else:
    print("\nALL pages have Bootstrap Icons CDN linked!")

