"""
Build complete static web application for GitHub Pages.
Renders all Django templates, bundles static files, and adds client-side
dynamic slot management, WhatsApp messaging, and Admin portal.
"""
import os
import shutil
import re
from pathlib import Path

os.environ['DJANGO_SETTINGS_MODULE'] = 'friends_hub.settings'
import django
django.setup()

from django.test import Client

client = Client()
out_dir = Path('dist_gh_pages')
out_dir.mkdir(parents=True, exist_ok=True)

# Copy static directory
static_dest = out_dir / 'static'
if static_dest.exists():
    shutil.rmtree(static_dest)
shutil.copytree('static', static_dest)

# Create .nojekyll for GitHub Pages
(out_dir / '.nojekyll').write_text('', encoding='utf-8')

# Render core pages from Django
routes = {
    '/': 'index.html',
    '/book/': 'book.html',
    '/facilities/': 'facilities.html',
    '/pricing/': 'pricing.html',
    '/contact/': 'contact.html',
    '/login/': 'login.html',
}

for route, filename in routes.items():
    res = client.get(route)
    html = res.content.decode('utf-8')

    # Convert paths to relative
    html = re.sub(r'href="/static/', 'href="static/', html)
    html = re.sub(r'src="/static/', 'src="static/', html)
    html = re.sub(r'href="/"', 'href="index.html"', html)
    html = re.sub(r'href="/book/"', 'href="book.html"', html)
    html = re.sub(r'action="/book/"', 'action="book.html"', html)
    html = re.sub(r'href="/facilities/"', 'href="facilities.html"', html)
    html = re.sub(r'href="/pricing/"', 'href="pricing.html"', html)
    html = re.sub(r'href="/contact/"', 'href="contact.html"', html)
    html = re.sub(r'href="/login/"', 'href="login.html"', html)
    html = re.sub(r'href="/manage/"', 'href="admin.html"', html)
    html = re.sub(r'href="/logout/"', 'href="login.html"', html)

    target_file = out_dir / filename
    target_file.write_text(html, encoding='utf-8')
    print(f"Rendered {filename}")

# 1. Enhance login.html with client-side credential validation
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

# 2. Enhance book.html with client-side slot syncing & admin direct locking
book_path = out_dir / 'book.html'
book_html = book_path.read_text(encoding='utf-8')
book_enhancement = """
<script>
// Check if admin is logged in
document.addEventListener('DOMContentLoaded', function() {
  const isAdmin = sessionStorage.getItem('fsh_admin_logged_in') === 'true';
  if (isAdmin) {
    const adminBtn = document.querySelector('a[href="login.html"]');
    if (adminBtn) {
      adminBtn.outerHTML = `
        <div class="dropdown">
          <button class="btn btn-success dropdown-toggle rounded-pill px-3 py-2 fw-semibold" type="button" data-bs-toggle="dropdown">
            <i class="bi bi-shield-lock-fill me-1"></i> Admin
          </button>
          <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end border-secondary shadow-lg">
            <li><a class="dropdown-item fw-bold text-success" href="admin.html"><i class="bi bi-speedometer2 me-2"></i> Owner Dashboard</a></li>
            <li><hr class="dropdown-divider border-secondary"></li>
            <li><a class="dropdown-item text-danger" href="#" onclick="sessionStorage.removeItem('fsh_admin_logged_in'); location.reload();"><i class="bi bi-box-arrow-right me-2"></i> Logout</a></li>
          </ul>
        </div>
      `;
    }
  }

  // Sync locked slots from local storage
  syncSlotsFromStorage();
});

function syncSlotsFromStorage() {
  try {
    const locked = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]');
    const dateInput = document.getElementById('slotDatePicker');
    const selectedDate = dateInput ? dateInput.value : '';

    document.querySelectorAll('.slot-box').forEach(box => {
      const timeEl = box.querySelector('.slot-time');
      if (!timeEl) return;
      const start = timeEl.textContent.trim().split(' ')[0];
      const isLocked = locked.some(l => l.date === selectedDate && l.start === start);
      if (isLocked) {
        box.classList.remove('vacant');
        box.classList.add('booked');
        box.removeAttribute('onclick');
        const badge = box.querySelector('.slot-status-badge');
        if (badge) {
          badge.className = 'slot-status-badge booked';
          badge.textContent = 'Booked';
        }
      }
    });
  } catch(e) {}
}

// Admin slot lock directly in modal
window.submitAdminBooking = function() {
  const name  = document.getElementById('inputCustomerName').value.trim();
  const phone = document.getElementById('inputCustomerPhone').value.trim();
  const club  = document.getElementById('inputClubName').value.trim();
  const slot  = document.getElementById('modalSlotTitle').textContent.replace('📅 Slot: ', '');
  const date  = document.getElementById('stateDate').value;
  const start = document.getElementById('stateStart').value;
  const fac   = document.getElementById('stateFacilityName').value;
  const price = document.getElementById('statePrice').value;

  if (!name || !phone) {
    alert('Please enter Customer Name and Phone Number.');
    return;
  }

  const booking = {
    id: 'FSH-' + Date.now().toString(36).toUpperCase(),
    name: name,
    phone: phone,
    club: club,
    slot: slot,
    date: date,
    start: start,
    facility: fac,
    price: price,
    time: new Date().toLocaleString()
  };

  const existing = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]');
  existing.push(booking);
  localStorage.setItem('fsh_locked_slots', JSON.stringify(existing));

  alert('Slot locked in system for ' + name + '! Redirecting to Owner Portal to send WhatsApp confirmation.');
  window.location.href = 'admin.html?latest=' + encodeURIComponent(booking.id);
};
</script>
</body>
"""
book_html = book_html.replace('</body>', book_enhancement)
book_path.write_text(book_html, encoding='utf-8')

# 3. Create rich, fully interactive admin.html
admin_html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Owner & Admin Portal | Friends Sports Hub</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
  <link href="static/css/style.css" rel="stylesheet">
  <style>
    body { background: #0a0f0d; color: #fff; }
    .admin-wrap { max-width: 960px; margin: 0 auto; padding: 24px 16px 80px; }
    .portal-card { background: #0e1712; border: 1px solid #1e2e22; border-radius: 18px; padding: 20px; margin-bottom: 20px; }
    .stat-box { background: #131e16; border: 1px solid #1e2e22; border-radius: 14px; padding: 16px; text-align: center; }
    .stat-val { font-size: 1.8rem; font-weight: 800; color: #22c55e; }
    .stat-lbl { font-size: 0.75rem; color: #8aab92; text-transform: uppercase; font-weight: 700; }
    .field-label { font-size: 0.75rem; font-weight: 700; color: #8aab92; text-transform: uppercase; margin-bottom: 5px; }
    .form-control, .form-select { background: #121c15; border: 1px solid #1e2e22; color: #fff; border-radius: 10px; }
    .form-control:focus, .form-select:focus { background: #152219; border-color: #22c55e; color: #fff; box-shadow: none; }
    .btn-lock { background: #16a34a; color: #fff; font-weight: 700; border-radius: 12px; padding: 12px; border: none; width: 100%; }
    .btn-lock:hover { background: #15803d; color: #fff; }
    .voucher-preview { background: #131e16; border: 1.5px solid #22c55e; border-radius: 16px; padding: 20px; margin-top: 20px; }
    .btn-wa-send { background: #25D366; color: #fff; font-weight: 800; border-radius: 12px; padding: 12px; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; gap: 8px; width: 100%; border: none; }
    .btn-wa-send:hover { background: #1ebe5d; color: #fff; }
    .btn-wa-owner { background: #141f17; border: 1px solid #1e2e22; color: #8aab92; font-weight: 700; border-radius: 10px; padding: 8px; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; gap: 6px; width: 100%; }
    .btn-wa-owner:hover { border-color: #22c55e; color: #22c55e; }
    .table-dark-custom { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 0.85rem; }
    .table-dark-custom th { background: #131e16; color: #8aab92; padding: 12px; font-weight: 700; border-bottom: 1px solid #1e2e22; }
    .table-dark-custom td { padding: 12px; border-bottom: 1px solid #141f17; vertical-align: middle; }
  </style>
</head>
<body>

  <!-- Top Navbar -->
  <nav class="navbar navbar-dark bg-black border-bottom border-secondary border-opacity-25 sticky-top py-2">
    <div class="container-fluid px-3">
      <a class="navbar-brand fw-extrabold text-white d-flex align-items-center gap-2" href="index.html">
        <i class="bi bi-shield-shaded text-success fs-4"></i>
        <span>FRIENDS SPORTS HUB</span>
      </a>
      <div class="d-flex align-items-center gap-2">
        <a href="index.html" class="btn btn-sm btn-outline-light rounded-pill px-3">
          <i class="bi bi-eye me-1"></i> Public View
        </a>
        <button type="button" class="btn btn-sm btn-outline-danger rounded-pill px-3" onclick="logoutAdmin()">
          <i class="bi bi-box-arrow-right me-1"></i> Logout
        </button>
      </div>
    </div>
  </nav>

  <div class="admin-wrap">
    <!-- Header -->
    <div class="d-flex align-items-center justify-content-between mb-4 flex-wrap gap-2">
      <div>
        <h2 class="h4 fw-bold text-white mb-0"><i class="bi bi-speedometer2 text-success me-2"></i>Owner & Staff Portal</h2>
        <small class="text-secondary">Friends Sports Hub Mulayankavu · Helpline: 6238006820</small>
      </div>
      <span class="badge bg-success bg-opacity-25 text-success border border-success rounded-pill px-3 py-2">
        <i class="bi bi-shield-check me-1"></i> Authenticated as Admin
      </span>
    </div>

    <!-- Stats -->
    <div class="row g-3 mb-4">
      <div class="col-md-4">
        <div class="stat-box">
          <div class="stat-val" id="statTotalBookings">0</div>
          <div class="stat-lbl">Total Locked Slots</div>
        </div>
      </div>
      <div class="col-md-4">
        <div class="stat-box">
          <div class="stat-val" id="statTodayBookings">0</div>
          <div class="stat-lbl">Today's Matches</div>
        </div>
      </div>
      <div class="col-md-4">
        <div class="stat-box">
          <div class="stat-val" id="statRevenue">₹0</div>
          <div class="stat-lbl">Expected Revenue</div>
        </div>
      </div>
    </div>

    <!-- Walk-in Booking Form -->
    <div class="portal-card">
      <h3 class="h6 fw-bold text-white mb-3"><i class="bi bi-plus-circle-fill text-success me-2"></i>Quick Walk-in / Phone Call Booking</h3>
      <form id="walkinForm" onsubmit="handleWalkinBooking(event)">
        <div class="row g-3">
          <div class="col-md-4">
            <label class="field-label">Facility</label>
            <select class="form-select" id="walkinFacility" required>
              <option value="Football & Cricket Turf">Football & Cricket Turf (₹900/hr)</option>
              <option value="Swimming Pool">Swimming Pool (₹150/hr)</option>
              <option value="Children's Park">Children's Park (₹50/hr)</option>
            </select>
          </div>
          <div class="col-md-4">
            <label class="field-label">Date</label>
            <input type="date" class="form-control" id="walkinDate" required>
          </div>
          <div class="col-md-4">
            <label class="field-label">Time Slot</label>
            <select class="form-select" id="walkinSlot" required>
              <option value="06:00 – 07:00">06:00 AM – 07:00 AM</option>
              <option value="07:00 – 08:00">07:00 AM – 08:00 AM</option>
              <option value="08:00 – 09:00">08:00 AM – 09:00 AM</option>
              <option value="09:00 – 10:00">09:00 AM – 10:00 AM</option>
              <option value="16:00 – 17:00">04:00 PM – 05:00 PM</option>
              <option value="17:00 – 18:00">05:00 PM – 06:00 PM</option>
              <option value="18:00 – 19:00" selected>06:00 PM – 07:00 PM</option>
              <option value="19:00 – 20:00">07:00 PM – 08:00 PM</option>
              <option value="20:00 – 21:00">08:00 PM – 09:00 PM</option>
              <option value="21:00 – 22:00">09:00 PM – 10:00 PM</option>
              <option value="22:00 – 23:00">10:00 PM – 11:00 PM</option>
            </select>
          </div>

          <div class="col-md-4">
            <label class="field-label">Player / Contact Name *</label>
            <input type="text" class="form-control" id="walkinName" placeholder="e.g. Rahul Kumar" required>
          </div>
          <div class="col-md-4">
            <label class="field-label">Club / Team Name</label>
            <input type="text" class="form-control" id="walkinClub" placeholder="e.g. Friends FC (optional)">
          </div>
          <div class="col-md-4">
            <label class="field-label">Phone Number *</label>
            <input type="tel" class="form-control" id="walkinPhone" placeholder="10-digit mobile" required>
          </div>

          <div class="col-12 mt-3">
            <button type="submit" class="btn-lock">
              <i class="bi bi-shield-check me-1"></i> Lock & Reserve Slot
            </button>
          </div>
        </div>
      </form>

      <!-- Latest Voucher Display -->
      <div id="voucherBox" style="display:none;" class="voucher-preview mt-4">
        <div class="d-flex align-items-center justify-content-between mb-2">
          <span class="badge bg-success rounded-pill px-3 py-1">Slot Reserved Successfully</span>
          <small class="text-secondary" id="voucherRef"></small>
        </div>
        <h4 class="text-white fw-bold mb-1" id="voucherTitle"></h4>
        <p class="text-success small fw-bold mb-3" id="voucherMeta"></p>

        <div class="row g-2 mb-3">
          <div class="col-md-6">
            <a href="#" target="_blank" id="btnCustomerWa" class="btn-wa-send">
              <i class="bi bi-whatsapp fs-5"></i> Send WhatsApp to Customer
            </a>
          </div>
          <div class="col-md-6">
            <a href="#" target="_blank" id="btnOwnerWa" class="btn-wa-owner">
              <i class="bi bi-shield-check"></i> Copy to Owner (6238006820)
            </a>
          </div>
        </div>
      </div>
    </div>

    <!-- Bookings Table -->
    <div class="portal-card">
      <h3 class="h6 fw-bold text-white mb-3"><i class="bi bi-calendar2-check-fill text-success me-2"></i>System Reserved Slots</h3>
      <div class="table-responsive">
        <table class="table-dark-custom">
          <thead>
            <tr>
              <th>REF ID</th>
              <th>FACILITY</th>
              <th>DATE & TIME</th>
              <th>PLAYER / CLUB</th>
              <th>PHONE</th>
              <th>FEE</th>
              <th>ACTION</th>
            </tr>
          </thead>
          <tbody id="bookingsTableBody">
            <tr><td colspan="7" class="text-center text-secondary py-4">No walk-in bookings recorded yet.</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    // Authentication guard
    if (sessionStorage.getItem('fsh_admin_logged_in') !== 'true') {
      window.location.href = 'login.html';
    }

    function logoutAdmin() {
      sessionStorage.removeItem('fsh_admin_logged_in');
      window.location.href = 'index.html';
    }

    // Set today as default date
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('walkinDate').value = today;

    function renderBookings() {
      const bookings = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]');
      const tbody = document.getElementById('bookingsTableBody');
      const statTotal = document.getElementById('statTotalBookings');
      const statToday = document.getElementById('statTodayBookings');
      const statRev   = document.getElementById('statRevenue');

      statTotal.textContent = bookings.length;
      const todayCount = bookings.filter(b => b.date === today).length;
      statToday.textContent = todayCount;
      const totalRev = bookings.reduce((sum, b) => sum + (parseInt(b.price) || 900), 0);
      statRev.textContent = '₹' + totalRev;

      if (bookings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-secondary py-4">No walk-in bookings recorded yet.</td></tr>';
        return;
      }

      tbody.innerHTML = bookings.slice().reverse().map((b, idx) => `
        <tr>
          <td><span class="badge bg-dark border border-secondary text-secondary">${b.id || 'FSH'}</span></td>
          <td><strong>${b.facility || 'Turf'}</strong></td>
          <td>${b.date}<br><span class="text-success small">${b.slot || ''}</span></td>
          <td><strong>${b.name}</strong>${b.club ? '<br><small class="text-secondary">' + b.club + '</small>' : ''}</td>
          <td><a href="tel:${b.phone}" class="text-white text-decoration-none">${b.phone}</a></td>
          <td class="text-warning fw-bold">₹${b.price || '900'}</td>
          <td>
            <button class="btn btn-sm btn-outline-danger" onclick="cancelSlot(${bookings.length - 1 - idx})">
              <i class="bi bi-trash"></i> Free Slot
            </button>
          </td>
        </tr>
      `).join('');
    }

    function cancelSlot(index) {
      if (!confirm('Free up this slot and make it vacant again?')) return;
      const bookings = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]');
      bookings.splice(index, 1);
      localStorage.setItem('fsh_locked_slots', JSON.stringify(bookings));
      renderBookings();
    }

    function handleWalkinBooking(e) {
      e.preventDefault();
      const fac   = document.getElementById('walkinFacility').value;
      const date  = document.getElementById('walkinDate').value;
      const slot  = document.getElementById('walkinSlot').value;
      const name  = document.getElementById('walkinName').value.trim();
      const club  = document.getElementById('walkinClub').value.trim();
      const phone = document.getElementById('walkinPhone').value.trim();
      const price = fac.includes('150') ? '150' : (fac.includes('50') ? '50' : '900');

      const id = 'FSH-' + Date.now().toString(36).toUpperCase();
      const booking = {
        id: id,
        facility: fac.split(' (')[0],
        date: date,
        slot: slot,
        start: slot.split(' – ')[0],
        name: name,
        club: club,
        phone: phone,
        price: price,
        time: new Date().toLocaleString()
      };

      const existing = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]');
      existing.push(booking);
      localStorage.setItem('fsh_locked_slots', JSON.stringify(existing));

      // Display voucher box
      const msgLines = [
        '🏆 *FRIENDS SPORTS HUB MULAYANKAVU*',
        '✅ *Booking Confirmed!*',
        '',
        '📋 *Ref ID:* ' + id,
        '👤 *Name:* ' + name,
        club ? ('👥 *Club/Team:* ' + club) : '',
        '🏟️ *Facility:* ' + booking.facility,
        '📅 *Date:* ' + date,
        '⏰ *Time:* ' + slot,
        '💰 *Fee:* ₹' + price + ' (Pay at Venue)',
        '',
        '📍 *Location:* Kulukkallur, Mulayankavu, Palakkad',
        '📞 *Helpline:* 6238006820',
        '',
        '⚠️ *Instructions:*',
        '• Please report 10 minutes before slot time.',
        '• Turf shoes or sports sneakers only (no metal studs).',
        '',
        'See you on the pitch! ⚽'
      ].filter(Boolean).join('\\n');

      let cleanCustPhone = phone.replace(/\\D/g, '');
      if (cleanCustPhone.length === 11 && cleanCustPhone.startsWith('0')) cleanCustPhone = cleanCustPhone.substring(1);
      if (cleanCustPhone.length === 10) cleanCustPhone = '91' + cleanCustPhone;

      const custUrl = 'https://api.whatsapp.com/send?phone=' + cleanCustPhone + '&text=' + encodeURIComponent(msgLines);
      const ownerUrl = 'https://api.whatsapp.com/send?phone=916238006820&text=' + encodeURIComponent(msgLines);

      document.getElementById('voucherTitle').textContent = booking.facility + ' · ' + slot;
      document.getElementById('voucherMeta').textContent = name + (club ? ' (' + club + ')' : '') + ' · ' + phone + ' · ₹' + price;
      document.getElementById('voucherRef').textContent = 'Ref: ' + id;
      document.getElementById('btnCustomerWa').href = custUrl;
      document.getElementById('btnOwnerWa').href = ownerUrl;
      document.getElementById('voucherBox').style.display = 'block';

      renderBookings();

      // Automatically launch WhatsApp with customer confirmation
      setTimeout(function() {
        window.open(custUrl, '_blank');
      }, 700);
    }

    renderBookings();
  </script>
</body>
</html>
"""
(out_dir / 'admin.html').write_text(admin_html_content, encoding='utf-8')
print("Generated admin.html with client-side slot storage & WhatsApp generator")

