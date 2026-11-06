"""
Generate the complete script for admin.html with Cloud Sync, robust Complete, Cancel, Collect actions,
and full mobile responsiveness.
"""

admin_script = """
<!-- Quick Walk-in Modal -->
<div class="modal fade" id="quickWalkinModal" tabindex="-1" aria-labelledby="quickWalkinModalLabel" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content bg-white border rounded-4 p-3 shadow-lg" style="border-color: #E5EEE8 !important;">
      <div class="modal-header border-0 pb-0">
        <h5 class="modal-title fw-bold d-flex align-items-center gap-2" id="quickWalkinModalLabel" style="color: #172B21;">
          <i class="bi bi-person-plus-fill text-emerald"></i> Direct Walk-in / Phone Booking
        </h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <div class="modal-body pt-3">
        <form id="modalWalkinForm" onsubmit="event.preventDefault(); submitQuickWalkin();">
          <div class="mb-3">
            <label class="form-label small fw-semibold" style="color: #64746B;">Sport Facility *</label>
            <select id="modalFacility" class="form-select border" style="border-color: #E5EEE8; background-color: #FFFFFF; color: #172B21;" required onchange="updateModalPrice()">
              <option value="turf" data-name="Football & Cricket Turf" data-price="900">Football & Cricket Turf (₹900/hr)</option>
              <option value="swimming-pool" data-name="Covered Swimming Pool" data-price="150">Swimming Pool (₹150/hr)</option>
              <option value="childrens-park" data-name="Children's Park" data-price="50">Children's Park (₹50/hr)</option>
            </select>
          </div>

          <div class="row g-2 mb-3">
            <div class="col-6">
              <label class="form-label small fw-semibold" style="color: #64746B;">Match Date *</label>
              <input type="date" id="modalDate" class="form-control border" style="border-color: #E5EEE8; background-color: #FFFFFF; color: #172B21;" required>
            </div>
            <div class="col-6">
              <label class="form-label small fw-semibold" style="color: #64746B;">Time Slot *</label>
              <select id="modalSlot" class="form-select border" style="border-color: #E5EEE8; background-color: #FFFFFF; color: #172B21;" required>
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
              <label class="form-label small fw-semibold" style="color: #64746B;">Customer Name *</label>
              <input type="text" id="modalCustomerName" class="form-control border" style="border-color: #E5EEE8; background-color: #FFFFFF; color: #172B21;" placeholder="e.g. Ashiq" required>
            </div>
            <div class="col-6">
              <label class="form-label small fw-semibold" style="color: #64746B;">Customer Mobile (WhatsApp) *</label>
              <input type="tel" id="modalCustomerPhone" class="form-control border" style="border-color: #E5EEE8; background-color: #FFFFFF; color: #172B21;" placeholder="10-digit number" required>
            </div>
          </div>

          <div class="row g-2 mb-3">
            <div class="col-4">
              <label class="form-label small fw-semibold" style="color: #64746B;">Total Fee (₹)</label>
              <input type="number" id="modalTotalPrice" class="form-control border" style="border-color: #E5EEE8; background-color: #FFFFFF; color: #172B21;" value="900" required>
            </div>
            <div class="col-4">
              <label class="form-label small fw-semibold" style="color: #64746B;">Advance (₹)</label>
              <input type="number" id="modalAdvance" class="form-control border" style="border-color: #E5EEE8; background-color: #FFFFFF; color: #172B21;" value="0" oninput="calculateModalBalance()">
            </div>
            <div class="col-4">
              <label class="form-label small fw-semibold" style="color: #64746B;">Payment Status</label>
              <select id="modalPaymentStatus" class="form-select border" style="border-color: #E5EEE8; background-color: #FFFFFF; color: #172B21;">
                <option value="PAID">Full Paid</option>
                <option value="ADVANCE_PAID">Advance Paid</option>
                <option value="UNPAID">Pay at Counter</option>
              </select>
            </div>
          </div>

          <button type="submit" class="btn btn-emerald w-100 rounded-pill fw-bold py-2 shadow-sm">
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

// Universal Cloud Database Real-Time MQTT Sync is powered by fsh_sync.js

function getLocalTodayString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function isSlotExpired(dateStr, slotStart) {
  if (!dateStr || !slotStart) return false;
  const now = new Date();
  const todayStr = getLocalTodayString();
  if (dateStr < todayStr) return true;
  if (dateStr > todayStr) return false;

  const parts = slotStart.split(':');
  const slotH = parseInt(parts[0], 10);
  const currentH = now.getHours();
  const currentM = now.getMinutes();

  return (slotH < currentH) || (slotH === currentH && currentM >= 0);
}

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

// Retrieve current bookings (starts clean with 0 bookings)
function getBookings() {
  let list = [];
  try {
    list = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]');
  } catch(e) { list = []; }
  return list;
}

function saveBookings(list) {
  localStorage.setItem('fsh_locked_slots', JSON.stringify(list));
  if (typeof window.pushCloudBookings === 'function') {
    window.pushCloudBookings(list);
  }
}

function getApiBaseUrl() {
  if (window.FSH_API_BASE_URL) return window.FSH_API_BASE_URL;
  const stored = window.localStorage.getItem('fsh_api_base_url');
  if (stored) return stored;
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return '';
  }
  return 'https://friends-sports-hub.onrender.com';
}

// Active PostgreSQL Cloud Synchronization
async function fetchCloudBookings() {
  const dateInput = document.querySelector('input[name="date"]');
  const facilitySelect = document.querySelector('select[name="facility"]');
  const selectedDate = (dateInput && dateInput.value) ? dateInput.value : getLocalTodayString();
  const selectedFacility = (facilitySelect && facilitySelect.value) ? facilitySelect.value : 'turf';

  const baseUrl = getApiBaseUrl();
  try {
    const res = await fetch(`${baseUrl}/api/bookings/availability/?facility_slug=${encodeURIComponent(selectedFacility)}&date=${encodeURIComponent(selectedDate)}&_t=${Date.now()}`, {
      method: 'GET',
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache'
      }
    });
    if (res.ok) {
      const data = await res.json();
      if (data && data.success && Array.isArray(data.slots)) {
        let list = getBookings();
        list = list.filter(b => !(b.date === selectedDate && (b.facility_slug === selectedFacility || !b.facility_slug)));
        data.slots.forEach(s => {
          if (s.is_booked || s.is_pending || s.status === 'APPROVED' || s.status === 'CONFIRMED' || s.status === 'PENDING_APPROVAL') {
            list.push({
              id: s.booking_id || ('BKG-' + s.start_time),
              booking_id: s.booking_id,
              date: selectedDate,
              start_time: s.start_time,
              end_time: s.end_time,
              display_time: s.display_time || (s.start_time + ' - ' + s.end_time),
              facility_slug: selectedFacility,
              facility_name: data.facility_name || FACILITY_NAMES[selectedFacility],
              status: s.status,
              customer_name: s.customer_name || 'Booked Player',
              customer_phone: s.customer_phone || 'Registered at Counter',
              total_price: s.price || 900,
              advance_amount: (s.status === 'APPROVED' || s.status === 'CONFIRMED') ? 900 : 0,
              balance_amount: (s.status === 'APPROVED' || s.status === 'CONFIRMED') ? 0 : 900,
              payment_status: (s.status === 'APPROVED' || s.status === 'CONFIRMED') ? 'PAID' : 'UNPAID'
            });
          }
        });
        saveBookings(list);
        return list;
      }
    }
  } catch(e) {
    console.warn('Admin live cloud sync error:', e);
  }
  return getBookings();
}

async function syncAndRefreshDashboard() {
  const btn = document.getElementById('btnManualRefresh');
  if (btn) btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Syncing...';
  renderDashboard();
  setTimeout(() => {
    if (btn) btn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i> Refresh';
  }, 400);
}

// Render Dashboard
document.addEventListener('DOMContentLoaded', function() {
  // Wire up filter controls
  const dateInput = document.querySelector('input[name="date"]');
  if (dateInput) {
    const today = getLocalTodayString();
    const urlParams = new URLSearchParams(window.location.search);
    const dateParam = urlParams.get('date');
    if (dateParam) {
      dateInput.value = dateParam;
    } else if (!dateInput.value || dateInput.value < today) {
      dateInput.value = today;
    }
  }

  const modalDateInput = document.getElementById('modalDate');
  if (modalDateInput) {
    modalDateInput.min = getLocalTodayString();
    modalDateInput.addEventListener('change', function() {
      if (this.value < getLocalTodayString()) {
        this.value = getLocalTodayString();
      }
      updateModalSlotsDropdown(this.value);
    });
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

function renderDashboard() {
  const allBookings = getBookings();
  const dateInput = document.querySelector('input[name="date"]');
  const facilitySelect = document.querySelector('select[name="facility"]');
  const searchInput = document.querySelector('input[name="q"]');

  const selectedDate = (dateInput && dateInput.value) ? dateInput.value : getLocalTodayString();
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
  const confirmed = dayBookings.filter(b => b.status === 'CONFIRMED' || b.status === 'APPROVED');
  const pending = dayBookings.filter(b => b.status === 'PENDING' || b.status === 'PENDING_APPROVAL');
  const completed = dayBookings.filter(b => b.status === 'COMPLETED');
  const cancelled = dayBookings.filter(b => b.status === 'CANCELLED');

  let revenuePaid = 0;
  let revenuePending = 0;
  dayBookings.forEach(b => {
    if (b.status !== 'CANCELLED' && b.status !== 'REJECTED') {
      revenuePaid += (b.payment_status === 'PAID') ? Number(b.total_price) : Number(b.advance_amount || 0);
      if (b.status === 'CONFIRMED' || b.status === 'APPROVED') {
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
    cancelledLabel.textContent = 'Cancelled: ' + cancelled.length + (pending.length > 0 ? ' | Pending: ' + pending.length : '');
  }

  // Update timeline header
  const facilityHeadingSpan = document.querySelector('h5.fw-bold span.text-emerald, h5.fw-bold span.text-success, h5 span.text-emerald');
  if (facilityHeadingSpan) {
    facilityHeadingSpan.textContent = FACILITY_NAMES[selectedFacility] || 'Football & Cricket Turf';
  }

  const timelineSmall = document.querySelector('h5.fw-bold + small, h5 + small');
  if (timelineSmall) {
    timelineSmall.innerHTML = `Timeline for ${selectedDate} &bull; Open 6:00 AM to 11:00 PM <span class="badge rounded-pill ms-2" style="background-color: #E8F7EE; color: #075B36; border: 1px solid #A7F3D0;"><i class="bi bi-broadcast me-1"></i> Live Cloud Synced</span>`;
  }

  // 3. Render Hourly Pitch Schedule (Section 1)
  const scheduleRow = document.querySelector('.row.row-cols-1.row-cols-md-2.row-cols-lg-3.row-cols-xl-4.g-3');
  if (scheduleRow) {
    scheduleRow.innerHTML = '';
    let visibleSlotCount = 0;

    TIME_SLOTS.forEach(slot => {
      // Find active (non-cancelled) booking
      const booking = dayBookings.find(b => b.start_time === slot.start && b.status !== 'CANCELLED' && b.status !== 'REJECTED');
      const isPast = isSlotExpired(selectedDate, slot.start);

      // If there is NO active booking and the slot has expired / time has already passed:
      if (!booking && isPast) {
        return;
      }

      visibleSlotCount++;
      const col = document.createElement('div');
      col.className = 'col';

      if (booking) {
        let badgeClass = 'bg-primary';
        let badgeText = 'APPROVED';
        if (booking.status === 'COMPLETED') {
          badgeClass = 'bg-info text-dark';
          badgeText = 'COMPLETED';
        } else if (booking.status === 'PENDING' || booking.status === 'PENDING_APPROVAL') {
          badgeClass = 'bg-warning text-dark';
          badgeText = 'PENDING APPROVAL';
        } else if (booking.payment_status === 'PAID') {
          badgeClass = 'bg-success';
          badgeText = 'PAID';
        } else if (booking.payment_status === 'ADVANCE_PAID') {
          badgeClass = 'bg-warning text-dark';
          badgeText = 'ADVANCE PAID';
        }

        const cardBorder = booking.status === 'COMPLETED' ? 'border: 1.5px solid #0284C7 !important;' : ((booking.status === 'PENDING' || booking.status === 'PENDING_APPROVAL') ? 'border: 1.5px solid #F59E0B !important;' : 'border: 1.5px solid #079B55 !important;');

        col.innerHTML = `
          <div class="card h-100 rounded-3 p-3 shadow-sm" style="background-color: #F4FAF6; ${cardBorder}">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="fw-bold fs-6" style="color: #172B21;">${slot.display}</span>
              <span class="badge ${badgeClass} small">${badgeText}</span>
            </div>
            <div class="mb-2">
              <div class="fw-bold text-truncate" style="color: #172B21;">${escapeHtml(booking.customer_name)}</div>
              <div class="small" style="color: #64746B;">
                <i class="bi bi-telephone text-emerald me-1"></i>
                <a href="tel:${booking.customer_phone}" class="text-decoration-none" style="color: #64746B;">${booking.customer_phone}</a>
              </div>
              <div class="small fw-bold mt-1" style="color: #079B55;">Fee: ₹${booking.total_price}</div>
              ${booking.payment_status === 'ADVANCE_PAID' && (booking.status === 'CONFIRMED' || booking.status === 'APPROVED') ? `
                <div class="small text-info"><i class="bi bi-qr-code text-emerald me-1"></i>Adv: ₹${booking.advance_amount}</div>
                <div class="small text-warning fw-bold">Bal: ₹${booking.balance_amount}</div>
              ` : ''}
            </div>
            <div class="d-flex gap-1 mt-auto pt-2 border-top flex-wrap" style="border-color: #E5EEE8 !important;">
              ${(booking.status === 'PENDING' || booking.status === 'PENDING_APPROVAL') ? `
                <button type="button" class="btn btn-xs btn-emerald rounded-pill px-2 py-1" style="font-size: 0.72rem;" onclick="approveBooking('${booking.id}')">
                  <i class="bi bi-check-circle-fill"></i> Approve
                </button>
                <button type="button" class="btn btn-xs btn-outline-danger rounded-pill px-2 py-1" style="font-size: 0.72rem;" onclick="rejectBooking('${booking.id}')">
                  <i class="bi bi-x-circle"></i> Reject
                </button>
                <button type="button" class="btn btn-xs btn-outline-secondary rounded-pill px-2 py-1" style="font-size: 0.72rem; border-color: #E5EEE8; color: #64746B;" onclick="cancelBooking('${booking.id}')">
                  Cancel
                </button>
              ` : (booking.status === 'CONFIRMED' || booking.status === 'APPROVED') ? `
                ${booking.payment_status !== 'PAID' ? `
                  <button type="button" class="btn btn-xs btn-emerald rounded-pill px-2 py-1" style="font-size: 0.72rem;" onclick="collectBalance('${booking.id}')">
                    <i class="bi bi-cash-coin"></i> Collect ₹${booking.balance_amount}
                  </button>
                ` : ''}
                <button type="button" class="btn btn-xs btn-outline-info rounded-pill px-2 py-1" style="font-size: 0.72rem;" onclick="markCompleted('${booking.id}')">
                  <i class="bi bi-check-all"></i> Complete
                </button>
                <button type="button" class="btn btn-xs btn-outline-danger rounded-pill px-2 py-1" style="font-size: 0.72rem;" onclick="cancelBooking('${booking.id}')">
                  Cancel
                </button>
              ` : `
                <span class="badge py-1 px-2" style="font-size: 0.72rem; background-color: #E5EEE8; color: #172B21;">
                  <i class="bi bi-check2"></i> Match Finished
                </span>
              `}
              <button type="button" class="btn btn-xs btn-outline-emerald rounded-pill px-2 py-1 ms-auto" style="font-size: 0.72rem;" onclick="sendWhatsAppVoucher('${booking.id}')" title="Send WhatsApp Voucher">
                <i class="bi bi-whatsapp"></i> Voucher
              </button>
            </div>
          </div>
        `;
      } else {
        col.innerHTML = `
          <div class="card h-100 rounded-3 p-3 shadow-sm" style="background-color: #FFFFFF; border: 1.5px solid #E5EEE8 !important;">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="fw-bold fs-6" style="color: #172B21;">${slot.display}</span>
              <span class="badge rounded-pill small" style="background-color: #E8F7EE; color: #075B36; border: 1px solid #A7F3D0;">FREE / OPEN</span>
            </div>
            <div class="mt-auto pt-3">
              <button type="button" class="btn btn-outline-emerald btn-sm w-100 rounded-pill" onclick="openQuickWalkinModal('${selectedFacility}', '${selectedDate}', '${slot.start}')">
                <i class="bi bi-plus-circle me-1"></i> Book Slot
              </button>
            </div>
          </div>
        `;
      }
      scheduleRow.appendChild(col);
    });

    if (visibleSlotCount === 0) {
      scheduleRow.innerHTML = `
        <div class="col-12 w-100 text-center py-5" style="color: #64746B;">
          <i class="bi bi-clock-history fs-1 mb-2 d-block" style="color: #A7F3D0;"></i>
          <h6 class="fw-bold mb-1" style="color: #172B21;">No Active Slots to Display</h6>
          <p class="small mb-0" style="color: #64746B;">All earlier slots for this date have passed and been removed.</p>
        </div>
      `;
    }
  }

  // 4. Render Section 2: Detailed Bookings Table (Desktop Table + Mobile Cards)
  const section2Card = document.getElementById('reservationsSection') || 
                       document.querySelector('.card.border.rounded-4.p-4');
  if (section2Card) {
    if (dayBookings.length === 0) {
      section2Card.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h5 class="fw-bold mb-0" style="color: #172B21;">All Scheduled Reservations (0)</h5>
          <div class="d-flex align-items-center gap-2">
            <span class="small" style="color: #64746B;">${selectedDate}</span>
            <button id="btnManualRefresh" class="btn btn-sm btn-outline-emerald rounded-pill px-3" onclick="syncAndRefreshDashboard()">
              <i class="bi bi-arrow-clockwise me-1"></i> Refresh
            </button>
          </div>
        </div>
        <div class="text-center py-4" style="color: #64746B;">
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
        const statusBadgeClass = (b.status === 'CONFIRMED' || b.status === 'APPROVED') ? 'bg-primary' : (b.status === 'PENDING' || b.status === 'PENDING_APPROVAL' ? 'bg-warning text-dark' : (b.status === 'COMPLETED' ? 'bg-info text-dark' : 'bg-danger'));

        // Desktop Table Row
        rowsHtml += `
          <tr style="border-bottom: 1px solid #E5EEE8;">
            <td class="font-monospace small fw-bold" style="color: #079B55;">${b.id}</td>
            <td>
              <div class="fw-bold" style="color: #172B21;">${escapeHtml(b.customer_name)}</div>
              <div class="small" style="color: #64746B;"><i class="bi bi-telephone text-emerald me-1"></i><a href="tel:${b.customer_phone}" class="text-decoration-none" style="color: #64746B;">${b.customer_phone}</a></div>
            </td>
            <td style="color: #172B21;">${escapeHtml(b.facility_name || FACILITY_NAMES[b.facility_slug])}</td>
            <td>
              <div class="fw-semibold" style="color: #172B21;">${b.display_time || b.start_time}</div>
              <small style="color: #64746B;">${b.date}</small>
            </td>
            <td>
              <div class="fw-bold text-emerald">₹${b.total_price}</div>
              ${b.payment_status === 'ADVANCE_PAID' && (b.status === 'CONFIRMED' || b.status === 'APPROVED') ? `
                <div class="small text-info">Adv: ₹${b.advance_amount}</div>
                <div class="small text-warning fw-bold">Bal: ₹${b.balance_amount}</div>
              ` : ''}
            </td>
            <td><span class="badge ${payBadgeClass}">${b.payment_status.replace('_', ' ')}</span></td>
            <td><span class="badge ${statusBadgeClass}">${b.status}</span></td>
            <td class="text-end">
              <div class="d-inline-flex gap-1 flex-wrap justify-content-end">
                ${(b.status === 'PENDING' || b.status === 'PENDING_APPROVAL') ? `
                  <button type="button" class="btn btn-sm btn-emerald rounded-pill px-2 py-1" title="Approve Booking" onclick="approveBooking('${b.id}')">
                    <i class="bi bi-check-circle-fill"></i> Approve
                  </button>
                  <button type="button" class="btn btn-sm btn-outline-danger rounded-pill px-2 py-1" title="Reject Booking" onclick="rejectBooking('${b.id}')">
                    <i class="bi bi-x-circle"></i> Reject
                  </button>
                  <button type="button" class="btn btn-sm btn-outline-secondary rounded-pill px-2 py-1" style="border-color: #E5EEE8; color: #64746B;" title="Cancel Booking" onclick="cancelBooking('${b.id}')">
                    Cancel
                  </button>
                ` : (b.status === 'CONFIRMED' || b.status === 'APPROVED') ? `
                  ${b.payment_status !== 'PAID' ? `
                    <button type="button" class="btn btn-sm btn-emerald rounded-pill px-2 py-1" title="Collect Balance" onclick="collectBalance('${b.id}')">
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
                  <span class="badge py-1 px-2" style="font-size: 0.72rem; background-color: #E5EEE8; color: #172B21;">
                    ${b.status === 'COMPLETED' ? '<i class="bi bi-check2"></i> Finished' : (b.status === 'REJECTED' ? '<i class="bi bi-x-circle"></i> Rejected' : '<i class="bi bi-x-circle"></i> Cancelled')}
                  </span>
                `}
                <button type="button" class="btn btn-sm btn-outline-emerald rounded-pill px-2 py-1" title="WhatsApp Confirmation" onclick="sendWhatsAppVoucher('${b.id}')">
                  <i class="bi bi-whatsapp"></i>
                </button>
              </div>
            </td>
          </tr>
        `;

        // Mobile Responsive Card
        cardsHtml += `
          <div class="card bg-white border rounded-3 p-3 mb-3 shadow-sm" style="border-color: #E5EEE8 !important;">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="font-monospace small fw-bold" style="color: #079B55;">${b.id}</span>
              <div class="d-flex gap-1">
                <span class="badge ${payBadgeClass} small">${b.payment_status.replace('_', ' ')}</span>
                <span class="badge ${statusBadgeClass} small">${b.status}</span>
              </div>
            </div>
            <div class="row g-2 mb-2">
              <div class="col-7">
                <div class="fw-bold fs-6" style="color: #172B21;">${escapeHtml(b.customer_name)}</div>
                <div class="small" style="color: #64746B;">
                  <i class="bi bi-telephone text-emerald me-1"></i>
                  <a href="tel:${b.customer_phone}" class="text-decoration-none" style="color: #64746B;">${b.customer_phone}</a>
                </div>
              </div>
              <div class="col-5 text-end">
                <div class="fw-bold fs-6" style="color: #079B55;">₹${b.total_price}</div>
                ${b.payment_status === 'ADVANCE_PAID' ? `<div class="small text-warning">Bal: ₹${b.balance_amount}</div>` : ''}
              </div>
            </div>
            <div class="d-flex justify-content-between align-items-center small py-1 border-top mb-2" style="border-color: #E5EEE8 !important; color: #64746B;">
              <span><i class="bi bi-geo-alt me-1 text-emerald"></i>${escapeHtml(b.facility_name || FACILITY_NAMES[b.facility_slug])}</span>
              <span class="fw-semibold" style="color: #172B21;"><i class="bi bi-clock me-1 text-emerald"></i>${b.display_time || b.start_time}</span>
            </div>
            <div class="d-flex gap-1 flex-wrap pt-1">
              ${(b.status === 'PENDING' || b.status === 'PENDING_APPROVAL') ? `
                <button type="button" class="btn btn-sm btn-emerald rounded-pill px-3 flex-grow-1" onclick="approveBooking('${b.id}')">
                  <i class="bi bi-check-circle-fill me-1"></i> Approve
                </button>
                <button type="button" class="btn btn-sm btn-outline-danger rounded-pill px-3 flex-grow-1" onclick="rejectBooking('${b.id}')">
                  <i class="bi bi-x-circle me-1"></i> Reject
                </button>
                <button type="button" class="btn btn-sm btn-outline-secondary rounded-pill px-3 flex-grow-1" style="border-color: #E5EEE8; color: #64746B;" onclick="cancelBooking('${b.id}')">
                  Cancel
                </button>
              ` : (b.status === 'CONFIRMED' || b.status === 'APPROVED') ? `
                ${b.payment_status !== 'PAID' ? `
                  <button type="button" class="btn btn-sm btn-emerald rounded-pill px-3 flex-grow-1" onclick="collectBalance('${b.id}')">
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
                <span class="badge py-2 px-3 w-100 text-center" style="background-color: #E5EEE8; color: #172B21;">
                  ${b.status === 'COMPLETED' ? '<i class="bi bi-check2 me-1"></i> Match Finished' : (b.status === 'REJECTED' ? '<i class="bi bi-x-circle me-1"></i> Reservation Rejected' : '<i class="bi bi-x-circle me-1"></i> Reservation Cancelled')}
                </span>
              `}
              <button type="button" class="btn btn-sm btn-outline-emerald rounded-pill px-3" onclick="sendWhatsAppVoucher('${b.id}')">
                <i class="bi bi-whatsapp"></i> Voucher
              </button>
            </div>
          </div>
        `;
      });

      section2Card.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
          <h5 class="fw-bold mb-0" style="color: #172B21;">All Scheduled Reservations (${dayBookings.length})</h5>
          <div class="d-flex align-items-center gap-2">
            <span class="small" style="color: #64746B;">${selectedDate}</span>
            <button id="btnManualRefresh" class="btn btn-sm btn-outline-emerald rounded-pill px-3" onclick="syncAndRefreshDashboard()">
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
          <table class="table table-hover mb-0 align-middle">
            <thead class="small" style="background-color: #F4FAF6; color: #64746B; border-bottom: 2px solid #E5EEE8;">
              <tr>
                <th class="py-3">Ref ID</th>
                <th class="py-3">Player / Customer</th>
                <th class="py-3">Facility</th>
                <th class="py-3">Slot Timing</th>
                <th class="py-3">Fee</th>
                <th class="py-3">Payment</th>
                <th class="py-3">Match Status</th>
                <th class="py-3 text-end">Quick Actions</th>
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

function approveBooking(id) {
  if (!confirm('Approve this booking? The slot will be confirmed and marked as BOOKED.')) return;
  const list = getBookings();
  const b = list.find(item => item.id === id);
  if (b) {
    b.status = 'APPROVED';
    saveBookings(list);
    renderDashboard();
    alert('Booking #' + id + ' for ' + b.customer_name + ' has been APPROVED and CONFIRMED! ✅');
  }
}

function rejectBooking(id) {
  if (!confirm('Reject this booking request? The reservation will be cancelled and the slot made AVAILABLE immediately.')) return;
  const list = getBookings();
  const b = list.find(item => item.id === id);
  if (b) {
    b.status = 'REJECTED';
    b.rejection_reason = 'Rejected by owner';
    saveBookings(list);
    renderDashboard();
    alert('Booking #' + id + ' for ' + b.customer_name + ' has been REJECTED. Slot is now free and available for other customers! ❌');
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
function updateModalSlotsDropdown(selectedDate, defaultSlot) {
  const slotSelect = document.getElementById('modalSlot');
  if (!slotSelect) return;
  if (!selectedDate) selectedDate = getLocalTodayString();

  slotSelect.innerHTML = '';
  let validCount = 0;

  TIME_SLOTS.forEach(slot => {
    if (!isSlotExpired(selectedDate, slot.start)) {
      validCount++;
      const opt = document.createElement('option');
      opt.value = slot.start;
      opt.textContent = slot.display;
      if (defaultSlot && slot.start === defaultSlot) {
        opt.selected = true;
      }
      slotSelect.appendChild(opt);
    }
  });

  if (validCount === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = '-- All slots expired for this date --';
    slotSelect.appendChild(opt);
    slotSelect.disabled = true;
  } else {
    slotSelect.disabled = false;
    if (!slotSelect.value && slotSelect.options.length > 0) {
      slotSelect.selectedIndex = 0;
    }
  }
}

function openQuickWalkinModal(facility, date, time) {
  const todayStr = getLocalTodayString();
  if (facility) document.getElementById('modalFacility').value = facility;

  const targetDate = (date && date >= todayStr) ? date : todayStr;
  const dateInput = document.getElementById('modalDate');
  if (dateInput) {
    dateInput.value = targetDate;
    dateInput.min = todayStr;
  }

  // Guard against expired time
  const targetTime = (time && !isSlotExpired(targetDate, time)) ? time : null;
  updateModalSlotsDropdown(targetDate, targetTime);

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

  if (!time || isSlotExpired(date, time)) {
    alert('Cannot book slot: The time for this slot has already passed.');
    return;
  }

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
