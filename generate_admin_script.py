"""
Generate the complete script for admin.html with Cloud Sync, robust Complete, Cancel, Collect actions,
and full mobile responsiveness.
"""

admin_script = """
<!-- Quick Walk-in Modal -->
<div class="modal fade" id="quickWalkinModal" tabindex="-1" aria-labelledby="quickWalkinModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content bg-black border border-success border-opacity-40 text-light rounded-4 p-3 shadow-lg">
      <div class="modal-header border-0 pb-0">
        <h5 class="modal-title fw-bold text-white d-flex align-items-center gap-2" id="quickWalkinModalLabel">
          <i class="bi bi-person-plus-fill text-success"></i> Direct Walk-in / Phone Booking
        </h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body pt-3">
        <form id="modalWalkinForm" onsubmit="event.preventDefault(); submitQuickWalkin();">
          <div class="mb-3">
            <label class="form-label text-secondary small fw-semibold">Sport Facility *</label>
            <select id="modalFacility" class="form-select bg-dark text-white border-secondary" required onchange="updateModalPrice()">
              <option value="turf" data-name="Football & Cricket Turf" data-price="900">Football & Cricket Turf (₹900/hr)</option>
              <option value="swimming-pool" data-name="Covered Swimming Pool" data-price="150">Swimming Pool (₹150/hr)</option>
              <option value="childrens-park" data-name="Children's Park" data-price="50">Children's Park (₹50/hr)</option>
            </select>
          </div>

          <div class="row g-2 mb-3">
            <div class="col-6">
              <label class="form-label text-secondary small fw-semibold">Match Date *</label>
              <input type="date" id="modalDate" class="form-control bg-dark text-white border-secondary" required>
            </div>
            <div class="col-6">
              <label class="form-label text-secondary small fw-semibold">Time Slot *</label>
              <select id="modalSlot" class="form-select bg-dark text-white border-secondary" required>
                <option value="06:00">06:00 AM - 07:00 AM</option>
                <option value="07:00">07:00 AM - 08:00 AM</option>
                <option value="08:00">08:00 AM - 09:00 AM</option>
                <option value="09:00">09:00 AM - 10:00 AM</option>
                <option value="10:00">10:00 AM - 11:00 AM</option>
                <option value="11:00">11:00 AM - 12:00 PM</option>
                <option value="12:00">12:00 PM - 01:00 PM</option>
                <option value="13:00">01:00 PM - 02:00 PM</option>
                <option value="14:00">02:00 PM - 03:00 PM</option>
                <option value="15:00">03:00 PM - 04:00 PM</option>
                <option value="16:00">04:00 PM - 05:00 PM</option>
                <option value="17:00">05:00 PM - 06:00 PM</option>
                <option value="18:00">06:00 PM - 07:00 PM</option>
                <option value="19:00" selected>07:00 PM - 08:00 PM</option>
                <option value="20:00">08:00 PM - 09:00 PM</option>
                <option value="21:00">09:00 PM - 10:00 PM</option>
                <option value="22:00">10:00 PM - 11:00 PM</option>
              </select>
            </div>
          </div>

          <div class="row g-2 mb-3">
            <div class="col-6">
              <label class="form-label text-secondary small fw-semibold">Customer Name *</label>
              <input type="text" id="modalCustomerName" class="form-control bg-dark text-white border-secondary" placeholder="e.g. Ashiq" required>
            </div>
            <div class="col-6">
              <label class="form-label text-secondary small fw-semibold">Customer Mobile (WhatsApp) *</label>
              <input type="tel" id="modalCustomerPhone" class="form-control bg-dark text-white border-secondary" placeholder="10-digit number" required>
            </div>
          </div>

          <div class="row g-2 mb-3">
            <div class="col-4">
              <label class="form-label text-secondary small fw-semibold">Total Fee (₹)</label>
              <input type="number" id="modalTotalPrice" class="form-control bg-dark text-white border-secondary" value="900" required>
            </div>
            <div class="col-4">
              <label class="form-label text-secondary small fw-semibold">Advance (₹)</label>
              <input type="number" id="modalAdvance" class="form-control bg-dark text-white border-secondary" value="0" oninput="calculateModalBalance()">
            </div>
            <div class="col-4">
              <label class="form-label text-secondary small fw-semibold">Payment Status</label>
              <select id="modalPaymentStatus" class="form-select bg-dark text-white border-secondary">
                <option value="PAID">Full Paid</option>
                <option value="ADVANCE_PAID">Advance Paid</option>
                <option value="UNPAID">Pay at Counter</option>
              </select>
            </div>
          </div>

          <button type="submit" class="btn btn-success w-100 rounded-pill fw-bold py-2 shadow">
            <i class="bi bi-check-circle-fill me-1"></i> Confirm & Lock Slot
          </button>
        </form>
      </div>
    </div>
  </div>
</div>

<script>
// Authentication check
if (sessionStorage.getItem('fsh_admin_logged_in') !== 'true') {
  window.location.href = 'login.html';
}

function logoutAdmin() {
  sessionStorage.removeItem('fsh_admin_logged_in');
  window.location.href = 'index.html';
}

// Universal Cloud Database API Endpoint (CORS enabled for GitHub Pages)
const FSH_CLOUD_API_URL = 'https://api.restful-api.dev/objects/ff808181a09d98f701a186b286c4486c';

// Slot definitions
const TIME_SLOTS = [
  { start: "06:00", end: "07:00", display: "06:00 AM - 07:00 AM" },
  { start: "07:00", end: "08:00", display: "07:00 AM - 08:00 AM" },
  { start: "08:00", end: "09:00", display: "08:00 AM - 09:00 AM" },
  { start: "09:00", end: "10:00", display: "09:00 AM - 10:00 AM" },
  { start: "10:00", end: "11:00", display: "10:00 AM - 11:00 AM" },
  { start: "11:00", end: "12:00", display: "11:00 AM - 12:00 PM" },
  { start: "12:00", end: "13:00", display: "12:00 PM - 01:00 PM" },
  { start: "13:00", end: "14:00", display: "01:00 PM - 02:00 PM" },
  { start: "14:00", end: "15:00", display: "02:00 PM - 03:00 PM" },
  { start: "15:00", end: "16:00", display: "03:00 PM - 04:00 PM" },
  { start: "16:00", end: "17:00", display: "04:00 PM - 05:00 PM" },
  { start: "17:00", end: "18:00", display: "05:00 PM - 06:00 PM" },
  { start: "18:00", end: "19:00", display: "06:00 PM - 07:00 PM" },
  { start: "19:00", end: "20:00", display: "07:00 PM - 08:00 PM" },
  { start: "20:00", end: "21:00", display: "08:00 PM - 09:00 PM" },
  { start: "21:00", end: "22:00", display: "09:00 PM - 10:00 PM" },
  { start: "22:00", end: "23:00", display: "10:00 PM - 11:00 PM" },
];

const FACILITY_NAMES = {
  'turf': 'Football & Cricket Turf',
  'swimming-pool': 'Covered Swimming Pool',
  'childrens-park': "Children's Park"
};

// Seed initial bookings only once if empty
function getBookings() {
  let list = [];
  try {
    list = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]');
  } catch(e) { list = []; }

  const isInit = localStorage.getItem('fsh_data_initialized') === 'true';
  if (!isInit && list.length === 0) {
    const today = new Date().toISOString().split('T')[0];
    list = [
      {
        id: 'BKG-FSH-101',
        customer_name: 'Mohammed Nihal',
        customer_phone: '9847123456',
        club_name: 'Friends FC',
        facility_slug: 'turf',
        facility_name: 'Football & Cricket Turf',
        date: today,
        start_time: '19:00',
        end_time: '20:00',
        display_time: '07:00 PM - 08:00 PM',
        total_price: 1000,
        advance_amount: 1000,
        balance_amount: 0,
        payment_status: 'PAID',
        status: 'CONFIRMED'
      },
      {
        id: 'BKG-FSH-102',
        customer_name: 'Salman Faris',
        customer_phone: '9745987654',
        club_name: 'Kulukkallur Stars',
        facility_slug: 'turf',
        facility_name: 'Football & Cricket Turf',
        date: today,
        start_time: '20:00',
        end_time: '21:00',
        display_time: '08:00 PM - 09:00 PM',
        total_price: 1000,
        advance_amount: 500,
        balance_amount: 500,
        payment_status: 'ADVANCE_PAID',
        status: 'CONFIRMED'
      }
    ];
    localStorage.setItem('fsh_locked_slots', JSON.stringify(list));
    localStorage.setItem('fsh_data_initialized', 'true');
  }
  return list;
}

function saveBookings(list) {
  localStorage.setItem('fsh_locked_slots', JSON.stringify(list));
  pushCloudBookings(list);
}

// Cloud Synchronization
async function fetchCloudBookings() {
  try {
    const res = await fetch(FSH_CLOUD_API_URL + '?t=' + Date.now());
    if (!res.ok) return null;
    const json = await res.json();
    if (json && json.data && json.data.json) {
      const cloudList = JSON.parse(json.data.json);
      if (Array.isArray(cloudList)) {
        let localList = [];
        try { localList = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]'); } catch(e){}

        const map = new Map();
        // Add cloud bookings
        cloudList.forEach(b => { if (b && b.id) map.set(b.id, b); });
        // Retain local bookings if newer or not yet synced
        localList.forEach(b => {
          if (b && b.id && !map.has(b.id)) {
            map.set(b.id, b);
          }
        });

        const merged = Array.from(map.values());
        localStorage.setItem('fsh_locked_slots', JSON.stringify(merged));
        localStorage.setItem('fsh_data_initialized', 'true');
        return merged;
      }
    }
  } catch(err) {
    console.warn('Live Cloud Sync offline, running on local storage cache:', err);
  }
  return null;
}

async function pushCloudBookings(list) {
  try {
    const payload = {
      name: 'Friends Sports Hub Master Live Store',
      data: {
        json: JSON.stringify(list)
      }
    };
    await fetch(FSH_CLOUD_API_URL, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  } catch(err) {
    console.warn('Live Cloud Push failed, saved to local cache:', err);
  }
}

// Render Dashboard
document.addEventListener('DOMContentLoaded', function() {
  // Wire up filter controls
  const dateInput = document.querySelector('input[name="date"]');
  if (dateInput && !dateInput.value) {
    const today = new Date().toISOString().split('T')[0];
    dateInput.value = today;
  }

  const filterForm = document.querySelector('form');
  if (filterForm) {
    filterForm.addEventListener('submit', function(e) {
      e.preventDefault();
      renderDashboard();
    });
  }

  // Intercept "New Walk-in Booking" and "Add Walk-in" buttons
  document.querySelectorAll('a[href*="walk-in"]').forEach(btn => {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      openQuickWalkinModal();
    });
  });

  // Render cached data immediately
  renderDashboard();

  // Then sync with cloud in background and re-render
  fetchCloudBookings().then(cloudData => {
    if (cloudData) renderDashboard();
  });

  // Periodic real-time poll every 10 seconds to catch new customer WhatsApp bookings
  setInterval(async () => {
    const synced = await fetchCloudBookings();
    if (synced) renderDashboard();
  }, 10000);
});

async function syncAndRefreshDashboard() {
  const btn = document.getElementById('btnManualRefresh');
  if (btn) btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Syncing...';
  await fetchCloudBookings();
  renderDashboard();
  if (btn) btn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i> Refresh';
}

function renderDashboard() {
  const allBookings = getBookings();
  const dateInput = document.querySelector('input[name="date"]');
  const facilitySelect = document.querySelector('select[name="facility"]');
  const searchInput = document.querySelector('input[name="q"]');

  const selectedDate = dateInput ? dateInput.value : new Date().toISOString().split('T')[0];
  const selectedFacility = (facilitySelect && facilitySelect.value) ? facilitySelect.value : 'turf';
  const query = searchInput ? searchInput.value.trim().toLowerCase() : '';

  // 1. Filter bookings
  let dayBookings = allBookings.filter(b => b.date === selectedDate);
  if (selectedFacility) {
    dayBookings = dayBookings.filter(b => b.facility_slug === selectedFacility || !b.facility_slug);
  }
  if (query) {
    dayBookings = dayBookings.filter(b => 
      (b.customer_name && b.customer_name.toLowerCase().includes(query)) ||
      (b.customer_phone && b.customer_phone.includes(query)) ||
      (b.id && b.id.toLowerCase().includes(query))
    );
  }

  // 2. Update KPI Metrics
  const confirmed = dayBookings.filter(b => b.status === 'CONFIRMED');
  const completed = dayBookings.filter(b => b.status === 'COMPLETED');
  const cancelled = dayBookings.filter(b => b.status === 'CANCELLED');

  let revenuePaid = 0;
  let revenuePending = 0;
  dayBookings.forEach(b => {
    if (b.status !== 'CANCELLED') {
      revenuePaid += (b.payment_status === 'PAID') ? Number(b.total_price) : Number(b.advance_amount || 0);
      if (b.status === 'CONFIRMED') {
        revenuePending += Number(b.balance_amount || 0);
      }
    }
  });

  // KPI elements
  const kpiCols = document.querySelectorAll('.row.g-3.mb-4 .fs-2');
  if (kpiCols.length >= 4) {
    kpiCols[0].textContent = confirmed.length;
    kpiCols[1].textContent = '₹' + revenuePaid.toFixed(0);
    kpiCols[2].textContent = '₹' + revenuePending.toFixed(0);
    kpiCols[3].textContent = completed.length;
  }
  const cancelledLabel = document.querySelector('.row.g-3.mb-4 .col-6.col-lg-3:last-child small');
  if (cancelledLabel) {
    cancelledLabel.textContent = 'Cancelled: ' + cancelled.length;
  }

  // Update timeline header
  const facilityHeadingSpan = document.querySelector('h5.text-white.fw-bold.mb-0 span.text-success');
  if (facilityHeadingSpan) {
    facilityHeadingSpan.textContent = FACILITY_NAMES[selectedFacility] || 'Football & Cricket Turf';
  }

  const timelineSmall = document.querySelector('h5.text-white.fw-bold.mb-0 + small.text-secondary');
  if (timelineSmall) {
    timelineSmall.innerHTML = `Timeline for ${selectedDate} &bull; Open 6:00 AM to 11:00 PM <span class="badge bg-success bg-opacity-25 text-success ms-2"><i class="bi bi-broadcast me-1"></i> Live Cloud Synced</span>`;
  }

  // 3. Render Hourly Pitch Schedule (Section 1)
  const scheduleRow = document.querySelector('.row.row-cols-1.row-cols-md-2.row-cols-lg-3.row-cols-xl-4.g-3');
  if (scheduleRow) {
    scheduleRow.innerHTML = '';
    TIME_SLOTS.forEach(slot => {
      // Find active (non-cancelled) booking
      const booking = dayBookings.find(b => b.start_time === slot.start && b.status !== 'CANCELLED');
      const col = document.createElement('div');
      col.className = 'col';

      if (booking) {
        let badgeClass = 'bg-primary';
        let badgeText = 'CONFIRMED';
        if (booking.status === 'COMPLETED') {
          badgeClass = 'bg-info text-dark';
          badgeText = 'COMPLETED';
        } else if (booking.payment_status === 'PAID') {
          badgeClass = 'bg-success';
          badgeText = 'PAID';
        } else if (booking.payment_status === 'ADVANCE_PAID') {
          badgeClass = 'bg-warning text-dark';
          badgeText = 'ADVANCE PAID';
        }

        col.innerHTML = `
          <div class="card h-100 rounded-3 p-3 border ${booking.status === 'COMPLETED' ? 'border-info' : 'border-success'} bg-dark bg-opacity-75 shadow-sm">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="fw-bold text-white fs-6">${slot.display}</span>
              <span class="badge ${badgeClass} small">${badgeText}</span>
            </div>
            <div class="mb-2">
              <div class="text-light fw-bold text-truncate">${escapeHtml(booking.customer_name)}</div>
              <div class="small text-secondary">
                <i class="bi bi-telephone text-success me-1"></i>
                <a href="tel:${booking.customer_phone}" class="text-secondary text-decoration-none">${booking.customer_phone}</a>
              </div>
              <div class="small text-success fw-bold mt-1">Fee: ₹${booking.total_price}</div>
              ${booking.payment_status === 'ADVANCE_PAID' && booking.status === 'CONFIRMED' ? `
                <div class="small text-info"><i class="bi bi-qr-code text-success me-1"></i>Adv: ₹${booking.advance_amount}</div>
                <div class="small text-warning fw-bold">Bal: ₹${booking.balance_amount}</div>
              ` : ''}
            </div>
            <div class="d-flex gap-1 mt-auto pt-2 border-top border-secondary border-opacity-25 flex-wrap">
              ${booking.status === 'CONFIRMED' ? `
                ${booking.payment_status !== 'PAID' ? `
                  <button type="button" class="btn btn-xs btn-success rounded-pill px-2 py-1" style="font-size: 0.75rem;" onclick="collectBalance('${booking.id}')">
                    <i class="bi bi-cash-coin"></i> Collect ₹${booking.balance_amount}
                  </button>
                ` : ''}
                <button type="button" class="btn btn-xs btn-outline-info rounded-pill px-2 py-1" style="font-size: 0.75rem;" onclick="markCompleted('${booking.id}')">
                  <i class="bi bi-check-all"></i> Complete
                </button>
                <button type="button" class="btn btn-xs btn-outline-danger rounded-pill px-2 py-1" style="font-size: 0.75rem;" onclick="cancelBooking('${booking.id}')">
                  Cancel
                </button>
              ` : `
                <span class="badge bg-secondary bg-opacity-50 text-light py-1 px-2" style="font-size: 0.75rem;">
                  <i class="bi bi-check2"></i> Match Finished
                </span>
              `}
              <button type="button" class="btn btn-xs btn-outline-success rounded-pill px-2 py-1 ms-auto" style="font-size: 0.75rem;" onclick="sendWhatsAppVoucher('${booking.id}')" title="Send WhatsApp Voucher">
                <i class="bi bi-whatsapp"></i> Voucher
              </button>
            </div>
          </div>
        `;
      } else {
        col.innerHTML = `
          <div class="card h-100 rounded-3 p-3 border border-secondary border-opacity-25 bg-dark">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="fw-bold text-white fs-6">${slot.display}</span>
              <span class="badge bg-success bg-opacity-25 text-success small">FREE / OPEN</span>
            </div>
            <div class="mt-auto pt-3">
              <button type="button" class="btn btn-outline-success btn-sm w-100 rounded-pill" onclick="openQuickWalkinModal('${selectedFacility}', '${selectedDate}', '${slot.start}')">
                <i class="bi bi-plus-circle me-1"></i> Book Slot
              </button>
            </div>
          </div>
        `;
      }
      scheduleRow.appendChild(col);
    });
  }

  // 4. Render Section 2: Detailed Bookings Table (Desktop Table + Mobile Cards)
  const section2Card = document.getElementById('reservationsSection') || 
                       document.querySelector('.card.bg-black.border.border-secondary.border-opacity-25.rounded-4.p-4.shadow');
  if (section2Card) {
    if (dayBookings.length === 0) {
      section2Card.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h5 class="text-white fw-bold mb-0">All Scheduled Reservations (0)</h5>
          <div class="d-flex align-items-center gap-2">
            <span class="small text-secondary">${selectedDate}</span>
            <button id="btnManualRefresh" class="btn btn-sm btn-outline-success rounded-pill px-3" onclick="syncAndRefreshDashboard()">
              <i class="bi bi-arrow-clockwise me-1"></i> Refresh
            </button>
          </div>
        </div>
        <div class="text-center py-4 text-secondary">
          <i class="bi bi-inbox fs-2 mb-2 d-block"></i>
          No bookings found for the selected date or search filter.
        </div>
      `;
    } else {
      let rowsHtml = '';
      let cardsHtml = '';

      dayBookings.forEach(b => {
        const isPaid = b.payment_status === 'PAID';
        const payBadgeClass = isPaid ? 'bg-success' : (b.payment_status === 'ADVANCE_PAID' ? 'bg-info text-dark' : 'bg-warning text-dark');
        const statusBadgeClass = b.status === 'CONFIRMED' ? 'bg-primary' : (b.status === 'COMPLETED' ? 'bg-info text-dark' : 'bg-danger');

        // Desktop Table Row
        rowsHtml += `
          <tr>
            <td class="font-monospace small text-success fw-bold">${b.id}</td>
            <td>
              <div class="fw-bold text-white">${escapeHtml(b.customer_name)}</div>
              <div class="small text-secondary"><i class="bi bi-telephone text-success me-1"></i><a href="tel:${b.customer_phone}" class="text-secondary text-decoration-none">${b.customer_phone}</a></div>
            </td>
            <td class="text-light">${escapeHtml(b.facility_name || FACILITY_NAMES[b.facility_slug])}</td>
            <td>
              <div class="text-warning fw-semibold">${b.display_time || b.start_time}</div>
              <small class="text-secondary">${b.date}</small>
            </td>
            <td>
              <div class="fw-bold text-success">₹${b.total_price}</div>
              ${b.payment_status === 'ADVANCE_PAID' && b.status === 'CONFIRMED' ? `
                <div class="small text-info">Adv: ₹${b.advance_amount}</div>
                <div class="small text-warning fw-bold">Bal: ₹${b.balance_amount}</div>
              ` : ''}
            </td>
            <td><span class="badge ${payBadgeClass}">${b.payment_status.replace('_', ' ')}</span></td>
            <td><span class="badge ${statusBadgeClass}">${b.status}</span></td>
            <td class="text-end">
              <div class="d-inline-flex gap-1 flex-wrap justify-content-end">
                ${b.status === 'CONFIRMED' ? `
                  ${b.payment_status !== 'PAID' ? `
                    <button type="button" class="btn btn-sm btn-success rounded-pill px-2 py-1" title="Collect Balance" onclick="collectBalance('${b.id}')">
                      <i class="bi bi-cash-stack"></i> Collect ₹${b.balance_amount}
                    </button>
                  ` : ''}
                  <button type="button" class="btn btn-sm btn-outline-info rounded-pill px-2 py-1" title="Mark Completed" onclick="markCompleted('${b.id}')">
                    <i class="bi bi-check2"></i> Complete
                  </button>
                  <button type="button" class="btn btn-sm btn-outline-danger rounded-pill px-2 py-1" title="Cancel Booking" onclick="cancelBooking('${b.id}')">
                    <i class="bi bi-x-circle"></i> Cancel
                  </button>
                ` : `
                  <span class="badge bg-secondary bg-opacity-50 text-light py-1 px-2" style="font-size: 0.75rem;">
                    ${b.status === 'COMPLETED' ? '<i class="bi bi-check2"></i> Finished' : '<i class="bi bi-x-circle"></i> Cancelled'}
                  </span>
                `}
                <button type="button" class="btn btn-sm btn-outline-success rounded-pill px-2 py-1" title="WhatsApp Confirmation" onclick="sendWhatsAppVoucher('${b.id}')">
                  <i class="bi bi-whatsapp"></i>
                </button>
              </div>
            </td>
          </tr>
        `;

        // Mobile Responsive Card
        cardsHtml += `
          <div class="card bg-dark border border-secondary border-opacity-30 rounded-3 p-3 mb-3 shadow-sm">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="font-monospace small text-success fw-bold">${b.id}</span>
              <div class="d-flex gap-1">
                <span class="badge ${payBadgeClass} small">${b.payment_status.replace('_', ' ')}</span>
                <span class="badge ${statusBadgeClass} small">${b.status}</span>
              </div>
            </div>
            <div class="row g-2 mb-2">
              <div class="col-7">
                <div class="fw-bold text-white fs-6">${escapeHtml(b.customer_name)}</div>
                <div class="small text-secondary">
                  <i class="bi bi-telephone text-success me-1"></i>
                  <a href="tel:${b.customer_phone}" class="text-light text-decoration-none">${b.customer_phone}</a>
                </div>
              </div>
              <div class="col-5 text-end">
                <div class="fw-bold text-success fs-6">₹${b.total_price}</div>
                ${b.payment_status === 'ADVANCE_PAID' ? `<div class="small text-warning">Bal: ₹${b.balance_amount}</div>` : ''}
              </div>
            </div>
            <div class="d-flex justify-content-between align-items-center text-secondary small py-1 border-top border-secondary border-opacity-25 mb-2">
              <span><i class="bi bi-geo-alt me-1 text-success"></i>${escapeHtml(b.facility_name || FACILITY_NAMES[b.facility_slug])}</span>
              <span class="text-warning fw-semibold"><i class="bi bi-clock me-1"></i>${b.display_time || b.start_time}</span>
            </div>
            <div class="d-flex gap-1 flex-wrap pt-1">
              ${b.status === 'CONFIRMED' ? `
                ${b.payment_status !== 'PAID' ? `
                  <button type="button" class="btn btn-sm btn-success rounded-pill px-3 flex-grow-1" onclick="collectBalance('${b.id}')">
                    <i class="bi bi-cash-stack me-1"></i> Collect ₹${b.balance_amount}
                  </button>
                ` : ''}
                <button type="button" class="btn btn-sm btn-outline-info rounded-pill px-3 flex-grow-1" onclick="markCompleted('${b.id}')">
                  <i class="bi bi-check2 me-1"></i> Complete
                </button>
                <button type="button" class="btn btn-sm btn-outline-danger rounded-pill px-3 flex-grow-1" onclick="cancelBooking('${b.id}')">
                  <i class="bi bi-x-circle me-1"></i> Cancel
                </button>
              ` : `
                <span class="badge bg-secondary bg-opacity-50 text-light py-2 px-3 w-100 text-center">
                  ${b.status === 'COMPLETED' ? '<i class="bi bi-check2 me-1"></i> Match Finished' : '<i class="bi bi-x-circle me-1"></i> Reservation Cancelled'}
                </span>
              `}
              <button type="button" class="btn btn-sm btn-outline-success rounded-pill px-3" onclick="sendWhatsAppVoucher('${b.id}')">
                <i class="bi bi-whatsapp"></i> Voucher
              </button>
            </div>
          </div>
        `;
      });

      section2Card.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
          <h5 class="text-white fw-bold mb-0">All Scheduled Reservations (${dayBookings.length})</h5>
          <div class="d-flex align-items-center gap-2">
            <span class="small text-secondary">${selectedDate}</span>
            <button id="btnManualRefresh" class="btn btn-sm btn-outline-success rounded-pill px-3" onclick="syncAndRefreshDashboard()">
              <i class="bi bi-arrow-clockwise me-1"></i> Refresh
            </button>
          </div>
        </div>

        <!-- Mobile Card View (< 768px) -->
        <div class="d-md-none">
          ${cardsHtml}
        </div>

        <!-- Desktop Table View (>= 768px) -->
        <div class="table-responsive d-none d-md-block">
          <table class="table table-dark table-hover mb-0 align-middle">
            <thead class="border-secondary text-secondary small">
              <tr>
                <th>Ref ID</th>
                <th>Player / Customer</th>
                <th>Facility</th>
                <th>Slot Timing</th>
                <th>Fee</th>
                <th>Payment</th>
                <th>Match Status</th>
                <th class="text-end">Quick Actions</th>
              </tr>
            </thead>
            <tbody>
              ${rowsHtml}
            </tbody>
          </table>
        </div>
      `;
    }
  }
}

// Actions
function collectBalance(id) {
  const list = getBookings();
  const b = list.find(item => item.id === id);
  if (b) {
    b.payment_status = 'PAID';
    b.advance_amount = b.total_price;
    b.balance_amount = 0;
    saveBookings(list);
    renderDashboard();
    alert('Payment collected for ' + b.customer_name + '! Status marked as PAID.');
  }
}

function markCompleted(id) {
  const list = getBookings();
  const b = list.find(item => item.id === id);
  if (b) {
    b.status = 'COMPLETED';
    saveBookings(list);
    renderDashboard();
    alert('Match #' + id + ' for ' + b.customer_name + ' marked as COMPLETED! ✅');
  }
}

function cancelBooking(id) {
  if (!confirm('Are you sure you want to cancel booking #' + id + '? The slot will be freed immediately.')) return;
  const list = getBookings();
  const b = list.find(item => item.id === id);
  if (b) {
    b.status = 'CANCELLED';
    saveBookings(list);
    renderDashboard();
    alert('Booking #' + id + ' for ' + b.customer_name + ' has been CANCELLED and slot is opened for booking! ❌');
  }
}

function sendWhatsAppVoucher(id) {
  const list = getBookings();
  const b = list.find(item => item.id === id);
  if (!b) return;

  const phone = (b.customer_phone || '').replace(/[^0-9]/g, '');
  const cleanPhone = phone.length === 10 ? '91' + phone : phone;

  const msg = 
`🏆 *FRIENDS SPORTS HUB MULAYANKAVU*
*Ground Booking Confirmation*
---------------------------------
Ref ID: ${b.id}
Player: ${b.customer_name}
Facility: ${b.facility_name || FACILITY_NAMES[b.facility_slug]}
Date: ${b.date}
Timing: ${b.display_time || b.start_time}
Fee: ₹${b.total_price} (Status: ${b.payment_status})
Match Status: ${b.status}
---------------------------------
📍 Location: Kulukkallur, Palakkad, Kerala
🗺️ Google Maps: https://maps.app.goo.gl/J1tQoft1vWQTDUio9
📞 Helpline: 6238006820
Thank you for choosing Friends Sports Hub!`;

  window.open('https://wa.me/' + cleanPhone + '?text=' + encodeURIComponent(msg), '_blank');
}

// Quick Walk-in Modal Handlers
function openQuickWalkinModal(facility, date, time) {
  if (facility) document.getElementById('modalFacility').value = facility;
  if (date) document.getElementById('modalDate').value = date;
  else document.getElementById('modalDate').value = new Date().toISOString().split('T')[0];
  if (time) document.getElementById('modalSlot').value = time;
  
  updateModalPrice();
  const modalEl = document.getElementById('quickWalkinModal');
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();
}

function updateModalPrice() {
  const sel = document.getElementById('modalFacility');
  const price = sel.options[sel.selectedIndex].getAttribute('data-price') || 900;
  document.getElementById('modalTotalPrice').value = price;
  calculateModalBalance();
}

function calculateModalBalance() {
  const total = Number(document.getElementById('modalTotalPrice').value || 0);
  const adv = Number(document.getElementById('modalAdvance').value || 0);
  const statusSel = document.getElementById('modalPaymentStatus');
  if (adv >= total && total > 0) {
    statusSel.value = 'PAID';
  } else if (adv > 0) {
    statusSel.value = 'ADVANCE_PAID';
  } else {
    statusSel.value = 'UNPAID';
  }
}

function submitQuickWalkin() {
  const facSel = document.getElementById('modalFacility');
  const facSlug = facSel.value;
  const facName = facSel.options[facSel.selectedIndex].getAttribute('data-name');
  const date = document.getElementById('modalDate').value;
  const time = document.getElementById('modalSlot').value;
  const name = document.getElementById('modalCustomerName').value.trim();
  const phone = document.getElementById('modalCustomerPhone').value.trim();
  const total = Number(document.getElementById('modalTotalPrice').value || 900);
  const adv = Number(document.getElementById('modalAdvance').value || 0);
  const status = document.getElementById('modalPaymentStatus').value;

  const slotObj = TIME_SLOTS.find(s => s.start === time) || { start: time, end: time, display: time };

  const newBooking = {
    id: 'BKG-FSH-' + Math.floor(100 + Math.random() * 900),
    customer_name: name,
    customer_phone: phone,
    facility_slug: facSlug,
    facility_name: facName,
    date: date,
    start_time: time,
    end_time: slotObj.end,
    display_time: slotObj.display,
    total_price: total,
    advance_amount: adv,
    balance_amount: Math.max(0, total - adv),
    payment_status: status,
    status: 'CONFIRMED'
  };

  const list = getBookings();
  list.unshift(newBooking);
  saveBookings(list);

  const modalEl = document.getElementById('quickWalkinModal');
  const modal = bootstrap.Modal.getInstance(modalEl);
  if (modal) modal.hide();

  renderDashboard();
  alert('Slot ' + slotObj.display + ' locked for ' + name + '! Saved to system and synced to cloud.');
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
</script>
"""
