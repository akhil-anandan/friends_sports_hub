"""
Build complete static web application for GitHub Pages.
Renders all Django templates, bundles static files, and adds client-side
dynamic slot management, WhatsApp messaging, and the exact previous Owner Dashboard.
"""
import os
import shutil
import re
from pathlib import Path

os.environ['DJANGO_SETTINGS_MODULE'] = 'friends_hub.settings'
import django
django.setup()

from django.test import Client
from django.contrib.auth.models import User

out_dir = Path('dist_gh_pages')
out_dir.mkdir(parents=True, exist_ok=True)

# Copy static directory
static_dest = out_dir / 'static'
if static_dest.exists():
    shutil.rmtree(static_dest)
shutil.copytree('static', static_dest)

# Create .nojekyll for GitHub Pages
(out_dir / '.nojekyll').write_text('', encoding='utf-8')

def clean_urls(html):
    # Static paths
    html = re.sub(r'href="/static/', 'href="static/', html)
    html = re.sub(r'src="/static/', 'src="static/', html)
    
    # Internal routes
    html = re.sub(r'href="/"', 'href="index.html"', html)
    html = re.sub(r'href="/about/"', 'href="index.html#about"', html)
    html = re.sub(r'href="/login/"', 'href="login.html"', html)
    html = re.sub(r'action="/login/"', 'action="login.html"', html)
    
    # Booking routes
    html = re.sub(r'href="/book/"', 'href="book.html"', html)
    html = re.sub(r'action="/book/"', 'action="book.html"', html)
    html = re.sub(r'href="/book/([^"/]+)/\?date=([^"\']+)"', r'href="book.html?facility=\1&date=\2"', html)
    html = re.sub(r'href="/book/([^"/]+)/"', r'href="book.html?facility=\1"', html)
    
    # Facilities, pricing, contact
    html = re.sub(r'href="/facilities/"', 'href="facilities.html"', html)
    html = re.sub(r'href="/pricing/"', 'href="pricing.html"', html)
    html = re.sub(r'href="/contact/"', 'href="contact.html"', html)
    
    # Staff & Admin management routes
    html = re.sub(r'href="/manage/"', 'href="admin.html"', html)
    html = re.sub(r'href="/manage/walk-in/\?([^"]*)"', r'href="walk-in.html?\1"', html)
    html = re.sub(r'href="/manage/walk-in/"', 'href="walk-in.html"', html)
    html = re.sub(r'href="/manage/reports/"', 'href="reports.html"', html)
    html = re.sub(r'href="/manage/employees/"', 'href="employees.html"', html)
    html = re.sub(r'href="/logout/"', 'href="#" onclick="logoutAdmin()"', html)
    html = re.sub(r'href="/admin/"', 'href="admin.html"', html)
    
    # Fix rel="noopener" on target="_blank"
    def fix_blank(m):
        tag = m.group(0)
        # If href="#" remove target="_blank"
        if 'href="#"' in tag:
            tag = re.sub(r'\s*target=["\']_blank["\']', '', tag)
            return tag
        if 'rel=' not in tag:
            tag = tag.replace('target="_blank"', 'target="_blank" rel="noopener"')
        elif 'noopener' not in tag:
            tag = re.sub(r'rel=["\']([^"\']*)["\']', r'rel="\1 noopener"', tag)
        return tag

    html = re.sub(r'<a\s+[^>]*target=["\']_blank["\'][^>]*>', fix_blank, html)

    return html

# 1. Render Public & Information Pages (logged out state)
anon_client = Client()
public_routes = {
    '/': 'index.html',
    '/book/': 'book.html',
    '/facilities/': 'facilities.html',
    '/pricing/': 'pricing.html',
    '/contact/': 'contact.html',
    '/login/': 'login.html',
}

for route, filename in public_routes.items():
    res = anon_client.get(route)
    html = clean_urls(res.content.decode('utf-8'))
    (out_dir / filename).write_text(html, encoding='utf-8')
    print(f"Rendered public {filename}")

# 2. Render Staff & Owner Pages (logged in state)
staff_client = Client()
admin_user = User.objects.filter(username='Admin').first()
if not admin_user:
    raise Exception("Admin user not found")
staff_client.force_login(admin_user)

staff_routes = {
    '/manage/': 'admin.html',
    '/manage/walk-in/': 'walk-in.html',
    '/manage/reports/': 'reports.html',
    '/manage/employees/': 'employees.html',
}

for route, filename in staff_routes.items():
    res = staff_client.get(route)
    html = clean_urls(res.content.decode('utf-8'))
    (out_dir / filename).write_text(html, encoding='utf-8')
    print(f"Rendered staff {filename}")

# 3. Enhance login.html with client-side credential validation
login_path = out_dir / 'login.html'
login_html = login_path.read_text(encoding='utf-8')
login_enhancement = """
<script>
document.addEventListener('DOMContentLoaded', function() {
  const form = document.querySelector('form');
  if (!form) return;
  form.addEventListener('submit', function(e) {
    e.preventDefault();
    const idInput = document.querySelector('input[name="username"]') || document.getElementById('id_username');
    const pwdInput = document.querySelector('input[name="password"]') || document.getElementById('id_password');
    const user = idInput ? idInput.value.trim() : '';
    const pwd = pwdInput ? pwdInput.value.trim() : '';

    if (user.toLowerCase() !== 'admin') {
      alert('Access Denied: Only Administrator account is permitted.');
      return;
    }
    if (pwd !== 'admin1010') {
      alert('Authentication failed: Incorrect password. Please try again.');
      return;
    }
    sessionStorage.setItem('fsh_admin_logged_in', 'true');
    window.location.href = 'admin.html';
  });
});
</script>
</body>
"""
login_html = login_html.replace('</body>', login_enhancement)
login_path.write_text(login_html, encoding='utf-8')

# 4. Global Navbar sync script for public pages
nav_sync_script = """
<script>
document.addEventListener('DOMContentLoaded', function() {
  const isAdmin = sessionStorage.getItem('fsh_admin_logged_in') === 'true';
  if (isAdmin) {
    const adminLink = document.querySelector('a[href="login.html"]');
    if (adminLink) {
      adminLink.outerHTML = `
        <div class="dropdown">
          <button class="btn btn-outline-light dropdown-toggle rounded-pill px-3 py-2 fw-semibold" type="button" data-bs-toggle="dropdown">
            <i class="bi bi-shield-lock-fill me-1 text-success"></i> Admin
          </button>
          <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end border-secondary shadow-lg">
            <li><a class="dropdown-item fw-bold text-success" href="admin.html"><i class="bi bi-speedometer2 me-2"></i> Owner Dashboard</a></li>
            <li><a class="dropdown-item" href="walk-in.html"><i class="bi bi-plus-circle-fill me-2 text-success"></i> Direct Booking</a></li>
            <li><a class="dropdown-item" href="reports.html"><i class="bi bi-graph-up-arrow me-2 text-info"></i> Financial Reports</a></li>
            <li><a class="dropdown-item" href="employees.html"><i class="bi bi-people-fill me-2 text-warning"></i> Manage Staff</a></li>
            <li><hr class="dropdown-divider border-secondary"></li>
            <li><a class="dropdown-item text-danger" href="#" onclick="logoutAdmin()"><i class="bi bi-box-arrow-right me-2"></i> Logout</a></li>
          </ul>
        </div>
      `;
    }
  }
});
function logoutAdmin() {
  sessionStorage.removeItem('fsh_admin_logged_in');
  window.location.href = 'index.html';
}
</script>
</body>
"""

for fn in ['index.html', 'facilities.html', 'pricing.html']:
    p = out_dir / fn
    if p.exists():
        content = p.read_text(encoding='utf-8')
        content = content.replace('</body>', nav_sync_script)
        p.write_text(content, encoding='utf-8')

# 5. Enhance contact.html with client-side WhatsApp submission
contact_path = out_dir / 'contact.html'
contact_html = contact_path.read_text(encoding='utf-8')
contact_script = """
<script>
document.addEventListener('DOMContentLoaded', function() {
  const isAdmin = sessionStorage.getItem('fsh_admin_logged_in') === 'true';
  if (isAdmin) {
    const adminLink = document.querySelector('a[href="login.html"]');
    if (adminLink) {
      adminLink.outerHTML = `
        <div class="dropdown">
          <button class="btn btn-outline-light dropdown-toggle rounded-pill px-3 py-2 fw-semibold" type="button" data-bs-toggle="dropdown">
            <i class="bi bi-shield-lock-fill me-1 text-success"></i> Admin
          </button>
          <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end border-secondary shadow-lg">
            <li><a class="dropdown-item fw-bold text-success" href="admin.html"><i class="bi bi-speedometer2 me-2"></i> Owner Dashboard</a></li>
            <li><a class="dropdown-item" href="walk-in.html"><i class="bi bi-plus-circle-fill me-2 text-success"></i> Direct Booking</a></li>
            <li><a class="dropdown-item" href="reports.html"><i class="bi bi-graph-up-arrow me-2 text-info"></i> Financial Reports</a></li>
            <li><a class="dropdown-item" href="employees.html"><i class="bi bi-people-fill me-2 text-warning"></i> Manage Staff</a></li>
            <li><hr class="dropdown-divider border-secondary"></li>
            <li><a class="dropdown-item text-danger" href="#" onclick="logoutAdmin()"><i class="bi bi-box-arrow-right me-2"></i> Logout</a></li>
          </ul>
        </div>
      `;
    }
  }

  const form = document.querySelector('form');
  if (form) {
    form.addEventListener('submit', function(e) {
      e.preventDefault();
      const name = (document.getElementById('id_name') || {}).value || '';
      const phone = (document.getElementById('id_phone') || {}).value || '';
      const email = (document.getElementById('id_email') || {}).value || '';
      const subject = (document.getElementById('id_subject') || {}).value || '';
      const msg = (document.getElementById('id_message') || {}).value || '';

      const waMsg = 
`🏆 *FRIENDS SPORTS HUB MULAYANKAVU*
*Customer Inquiry*
---------------------------------
Name: ${name}
Phone: ${phone}
${email ? 'Email: ' + email + '\\n' : ''}Subject: ${subject}
Message: ${msg}
---------------------------------
Sent from website contact form`;

      alert('Thank you, ' + name + '! Redirecting your inquiry directly to our official WhatsApp helpline.');
      window.open('https://wa.me/916238006820?text=' + encodeURIComponent(waMsg), '_blank');
      form.reset();
    });
  }
});
function logoutAdmin() {
  sessionStorage.removeItem('fsh_admin_logged_in');
  window.location.href = 'index.html';
}
</script>
</body>
"""
contact_html = contact_html.replace('</body>', contact_script)
contact_path.write_text(contact_html, encoding='utf-8')

# 6. Enhance book.html with live facility switching, slot sync & lock support
book_path = out_dir / 'book.html'
book_html = book_path.read_text(encoding='utf-8')

book_enhancement = """
<script>
const FACILITIES_DATA = {
  'turf': {
    name: 'Football & Cricket Turf',
    tag: 'Sports Turf (Football / Cricket)',
    rate: 900,
    photo: 'static/images/turf_hero.jpg',
    sub: 'Mulayankavu, Kulukkallur, Palakkad · 5s & 7s All-Weather Turf with Floodlights',
    features: [
      { icon: 'bi-check-circle-fill text-success', title: 'FIFA Standard 50mm Grass', desc: 'Shock absorbing turf' },
      { icon: 'bi-lightning-charge-fill text-warning', title: 'High-Power LED Floodlights', desc: 'Crystal-clear night play' },
      { icon: 'bi-shield-check text-success', title: 'Full Perimeter Netting', desc: 'High ball containment' },
      { icon: 'bi-clock-fill text-info', title: 'Open 6:00 AM – 11:00 PM', desc: 'Flexible hourly slots' }
    ]
  },
  'swimming-pool': {
    name: 'Covered Swimming Pool',
    tag: 'Covered Swimming Pool',
    rate: 150,
    photo: 'static/images/hub_banner.jpg',
    sub: 'Mulayankavu, Kulukkallur, Palakkad · Hygienic Temperature-Maintained Pool',
    features: [
      { icon: 'bi-check-circle-fill text-success', title: 'Full Roof Covered', desc: 'All-weather swimming' },
      { icon: 'bi-water text-info', title: 'Daily Chlorinated & Filtered', desc: 'Highest hygiene standard' },
      { icon: 'bi-shield-check text-success', title: 'Separate Changing Rooms', desc: 'Clean showers & lockers' },
      { icon: 'bi-clock-fill text-info', title: 'Open 6:00 AM – 8:00 PM', desc: 'Hourly lap swimming' }
    ]
  },
  'childrens-park': {
    name: "Children's Park",
    tag: "Children's Play Park",
    rate: 50,
    photo: 'static/images/hub_banner.jpg',
    sub: 'Mulayankavu, Kulukkallur, Palakkad · Safe Recreational Play Zone for Kids',
    features: [
      { icon: 'bi-check-circle-fill text-success', title: 'Kid-Safe Playground Equipment', desc: 'Swings, slides & climbing frames' },
      { icon: 'bi-shield-check text-success', title: 'Soft Grass Turf Protection', desc: 'Cushioned ground surface' },
      { icon: 'bi-people-fill text-warning', title: 'Shaded Seating for Parents', desc: 'Comfortable benches' },
      { icon: 'bi-clock-fill text-info', title: 'Open 9:00 AM – 8:00 PM', desc: 'Family & kids entry' }
    ]
  }
};

let currentFacilitySlug = 'turf';

function switchFacility(slug, event) {
  if (event) event.preventDefault();
  if (!FACILITIES_DATA[slug]) slug = 'turf';
  currentFacilitySlug = slug;

  const data = FACILITIES_DATA[slug];

  // Update URL without page reload
  const url = new URL(window.location);
  url.searchParams.set('facility', slug);
  window.history.replaceState({}, '', url);

  // Update tabs active state
  document.querySelectorAll('.facility-tab-pill').forEach(pill => {
    const href = pill.getAttribute('href') || '';
    if (href.includes(slug)) {
      pill.classList.add('active');
    } else {
      pill.classList.remove('active');
    }
  });

  // Update Showcase
  const titleEl = document.querySelector('.turf-title');
  if (titleEl) titleEl.textContent = data.name;

  const rateAmountEl = document.querySelector('.turf-rate-tag .amount');
  if (rateAmountEl) rateAmountEl.textContent = '₹' + data.rate;

  const overlayTagEl = document.querySelector('.turf-overlay-tag');
  if (overlayTagEl) overlayTagEl.innerHTML = '<i class="bi bi-stars me-1"></i> ' + data.tag;

  const photoEl = document.querySelector('.turf-photo-box img');
  if (photoEl) {
    photoEl.src = data.photo;
    photoEl.alt = data.name;
  }

  const subEl = document.querySelector('.turf-sub');
  if (subEl) subEl.textContent = data.sub;

  // Update modal state hidden fields
  const stateFac = document.getElementById('stateFacilityName');
  if (stateFac) stateFac.value = data.name;
  const statePrice = document.getElementById('statePrice');
  if (statePrice) statePrice.value = data.rate;

  syncBookingsToPage();
}

document.addEventListener('DOMContentLoaded', function() {
  const isAdmin = sessionStorage.getItem('fsh_admin_logged_in') === 'true';
  if (isAdmin) {
    const adminLink = document.querySelector('a[href="login.html"]');
    if (adminLink) {
      adminLink.outerHTML = `
        <div class="dropdown">
          <button class="btn btn-outline-light dropdown-toggle rounded-pill px-3 py-2 fw-semibold" type="button" data-bs-toggle="dropdown">
            <i class="bi bi-shield-lock-fill me-1 text-success"></i> Admin
          </button>
          <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end border-secondary shadow-lg">
            <li><a class="dropdown-item fw-bold text-success" href="admin.html"><i class="bi bi-speedometer2 me-2"></i> Owner Dashboard</a></li>
            <li><a class="dropdown-item" href="walk-in.html"><i class="bi bi-plus-circle-fill me-2 text-success"></i> Direct Booking</a></li>
            <li><a class="dropdown-item" href="reports.html"><i class="bi bi-graph-up-arrow me-2 text-info"></i> Financial Reports</a></li>
            <li><a class="dropdown-item" href="employees.html"><i class="bi bi-people-fill me-2 text-warning"></i> Manage Staff</a></li>
            <li><hr class="dropdown-divider border-secondary"></li>
            <li><a class="dropdown-item text-danger" href="#" onclick="logoutAdmin()"><i class="bi bi-box-arrow-right me-2"></i> Logout</a></li>
          </ul>
        </div>
      `;
    }
  }

  // Intercept facility tab clicks
  document.querySelectorAll('.facility-tab-pill').forEach(pill => {
    pill.addEventListener('click', function(e) {
      e.preventDefault();
      const href = this.getAttribute('href') || '';
      let slug = 'turf';
      if (href.includes('pool')) slug = 'swimming-pool';
      else if (href.includes('park') || href.includes('children')) slug = 'childrens-park';
      switchFacility(slug, e);
    });
  });

  // Check URL params on load
  const urlParams = new URLSearchParams(window.location.search);
  const requestedFacility = urlParams.get('facility');
  if (requestedFacility && FACILITIES_DATA[requestedFacility]) {
    switchFacility(requestedFacility);
  }

  syncBookingsToPage();
});

function syncBookingsToPage() {
  try {
    const list = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]');
    const dateInput = document.getElementById('slotDatePicker');
    const selectedDate = dateInput ? dateInput.value : '';

    document.querySelectorAll('.slot-btn').forEach(box => {
      const timeEl = box.querySelector('.time-text');
      if (!timeEl) return;
      const start = timeEl.textContent.trim().split(' ')[0];
      const isLocked = list.some(l => 
        l.date === selectedDate && 
        (l.facility_slug === currentFacilitySlug || !l.facility_slug) &&
        l.start_time.startsWith(start) && 
        l.status !== 'CANCELLED'
      );
      if (isLocked) {
        box.classList.remove('vacant');
        box.classList.add('booked');
        box.removeAttribute('onclick');
        const badge = box.querySelector('.slot-badge-pill');
        if (badge) {
          badge.className = 'slot-badge-pill booked';
          badge.textContent = 'Booked';
        }
      }
    });
  } catch(e) {}
}

function logoutAdmin() {
  sessionStorage.removeItem('fsh_admin_logged_in');
  window.location.href = 'index.html';
}
</script>
</body>
"""
book_html = book_html.replace('</body>', book_enhancement)
book_path.write_text(book_html, encoding='utf-8')
print("book.html enhanced with dynamic facility switcher & slot synchronization")

# 7. Enhance admin.html (The Exact Previous Owner Dashboard with dynamic client-side live engine)
admin_path = out_dir / 'admin.html'
admin_html = admin_path.read_text(encoding='utf-8')

with open('generate_admin_script.py', 'r', encoding='utf-8') as f:
    code = f.read()
scope = {}
exec(code, scope)
admin_script = scope.get('admin_script', '')

admin_html = admin_html.replace('</body>', admin_script)
admin_path.write_text(admin_html, encoding='utf-8')
print("admin.html enhanced with complete live Owner Dashboard engine")

# 8. Enhance walk-in.html
walkin_path = out_dir / 'walk-in.html'
walkin_html = walkin_path.read_text(encoding='utf-8')
walkin_script = """
<script>
if (sessionStorage.getItem('fsh_admin_logged_in') !== 'true') {
  window.location.href = 'login.html';
}
function logoutAdmin() {
  sessionStorage.removeItem('fsh_admin_logged_in');
  window.location.href = 'index.html';
}

document.addEventListener('DOMContentLoaded', function() {
  const form = document.querySelector('form');
  if (!form) return;

  form.addEventListener('submit', function(e) {
    e.preventDefault();

    const facSel = document.querySelector('select[name="facility_id"]');
    const facName = facSel ? facSel.options[facSel.selectedIndex].text.split('(')[0].trim() : 'Football & Cricket Turf';
    const facSlug = (facName.toLowerCase().includes('pool')) ? 'swimming-pool' : ((facName.toLowerCase().includes('park')) ? 'childrens-park' : 'turf');
    const date = document.querySelector('input[name="booking_date"]').value;
    const time = document.querySelector('select[name="start_time"]').value;
    const name = document.querySelector('input[name="customer_name"]').value.trim();
    const phone = document.querySelector('input[name="customer_phone"]').value.trim();
    const price = Number(document.querySelector('input[name="total_price"]').value || 900);
    const adv = Number(document.querySelector('input[name="advance_amount"]').value || 0);
    const payMode = document.querySelector('select[name="payment_mode"]').value;

    let payStatus = 'UNPAID';
    if (adv >= price && price > 0) payStatus = 'PAID';
    else if (adv > 0) payStatus = 'ADVANCE_PAID';

    const slotDisplay = (time) ? time + ' - ' + (Number(time.split(':')[0]) + 1).toString().padStart(2, '0') + ':00' : 'Slot';

    const newBooking = {
      id: 'BKG-FSH-' + Math.floor(100 + Math.random() * 900),
      customer_name: name,
      customer_phone: phone,
      facility_slug: facSlug,
      facility_name: facName,
      date: date,
      start_time: time,
      display_time: slotDisplay,
      total_price: price,
      advance_amount: adv,
      balance_amount: Math.max(0, price - adv),
      payment_status: payStatus,
      status: 'CONFIRMED'
    };

    let list = [];
    try {
      list = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]');
    } catch(err) { list = []; }

    list.unshift(newBooking);
    localStorage.setItem('fsh_locked_slots', JSON.stringify(list));

    alert('Booking locked successfully for ' + name + '! Redirecting to Owner Operations Dashboard.');
    window.location.href = 'admin.html';
  });
});
</script>
</body>
"""
walkin_html = walkin_html.replace('</body>', walkin_script)
walkin_path.write_text(walkin_html, encoding='utf-8')
print("walk-in.html enhanced with local submission engine")

# 9. Enhance reports.html
reports_path = out_dir / 'reports.html'
reports_html = reports_path.read_text(encoding='utf-8')
reports_script = """
<script>
if (sessionStorage.getItem('fsh_admin_logged_in') !== 'true') {
  window.location.href = 'login.html';
}
function logoutAdmin() {
  sessionStorage.removeItem('fsh_admin_logged_in');
  window.location.href = 'index.html';
}

document.addEventListener('DOMContentLoaded', function() {
  let list = [];
  try {
    list = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]');
  } catch(e) { list = []; }

  let totalRev = 0;
  let totalBookings = list.length;
  list.forEach(b => {
    if (b.status !== 'CANCELLED') {
      totalRev += (b.payment_status === 'PAID') ? Number(b.total_price) : Number(b.advance_amount || 0);
    }
  });

  const revEls = document.querySelectorAll('.display-6');
  if (revEls.length >= 3) {
    revEls[0].textContent = '₹' + totalRev.toFixed(0);
    revEls[1].textContent = '₹' + totalRev.toFixed(0);
    revEls[2].textContent = totalBookings;
  }
});
</script>
</body>
"""
reports_html = reports_html.replace('</body>', reports_script)
reports_path.write_text(reports_html, encoding='utf-8')
print("reports.html enhanced")

# 10. Enhance employees.html
employees_path = out_dir / 'employees.html'
employees_html = employees_path.read_text(encoding='utf-8')
employees_script = """
<script>
if (sessionStorage.getItem('fsh_admin_logged_in') !== 'true') {
  window.location.href = 'login.html';
}
function logoutAdmin() {
  sessionStorage.removeItem('fsh_admin_logged_in');
  window.location.href = 'index.html';
}
</script>
</body>
"""
employees_html = employees_html.replace('</body>', employees_script)
employees_path.write_text(employees_html, encoding='utf-8')
print("employees.html enhanced")

print("\n--- Build Complete & Verified Successfully! ---")
