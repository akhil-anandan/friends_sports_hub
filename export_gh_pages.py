import os
import sys
import shutil
import re
from pathlib import Path

os.environ['DJANGO_SETTINGS_MODULE'] = 'friends_hub.settings'
import django
django.setup()

from django.test import Client

client = Client()
out_dir = Path('dist_gh_pages')
if out_dir.exists():
    shutil.rmtree(out_dir)
out_dir.mkdir(parents=True)

# Copy static directory
shutil.copytree('static', out_dir / 'static')

# Add .nojekyll for GitHub Pages
(out_dir / '.nojekyll').write_text('', encoding='utf-8')

routes = {
    '/': 'index.html',
    '/facilities/': 'facilities.html',
    '/pricing/': 'pricing.html',
    '/contact/': 'contact.html',
    '/login/': 'login.html',
}

for route, filename in routes.items():
    res = client.get(route)
    html = res.content.decode('utf-8')

    # Convert absolute paths to relative for GitHub Pages subpath compatibility
    html = re.sub(r'href="/static/', 'href="static/', html)
    html = re.sub(r'src="/static/', 'src="static/', html)
    html = re.sub(r'href="/"', 'href="index.html"', html)
    html = re.sub(r'href="/book/"', 'href="index.html"', html)
    html = re.sub(r'href="/facilities/"', 'href="facilities.html"', html)
    html = re.sub(r'href="/pricing/"', 'href="pricing.html"', html)
    html = re.sub(r'href="/contact/"', 'href="contact.html"', html)
    html = re.sub(r'href="/login/"', 'href="login.html"', html)
    html = re.sub(r'href="/manage/"', 'href="admin.html"', html)
    html = re.sub(r'href="/logout/"', 'href="login.html"', html)

    target_file = out_dir / filename
    target_file.write_text(html, encoding='utf-8')
    print(f"Generated {filename} ({len(html)} bytes)")

print("Static site build for GitHub Pages completed successfully!")

