// Unified Real-Time Multi-Device Synchronization & Cache Reconciliation Engine
// Friends Sports Hub - Kerala
(function() {
  const SYNC_TOPIC = 'friends_sports_hub_kerala/master_live_v5';
  const BROKERS = [
    'wss://broker.hivemq.com:8884/mqtt',
    'wss://broker.emqx.io:8084/mqtt'
  ];

  let mqttClient = null;
  let isConnected = false;
  let currentBrokerIdx = 0;
  let lastReconciledTime = 0;

  function getLocalTodayString() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function getLocalBookings() {
    try {
      return JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]');
    } catch(e) {
      return [];
    }
  }

  function saveLocalBookings(list) {
    try {
      localStorage.setItem('fsh_locked_slots', JSON.stringify(list));
    } catch(e) {}
  }

  function triggerUIRefresh(list) {
    if (!list) list = getLocalBookings();

    // 1. If on public booking / front page
    if (typeof window.renderSlots === 'function') {
      try {
        const currentDate = window.currentSelectedDate || document.getElementById('slotDatePicker')?.value || document.querySelector('input[name="date"]')?.value || getLocalTodayString();
        window.renderSlots(currentDate);
      } catch(e) { console.warn('renderSlots error:', e); }
    }

    // 2. If on admin dashboard
    if (typeof window.renderDashboard === 'function') {
      try {
        window.renderDashboard();
      } catch(e) { console.warn('renderDashboard error:', e); }
    }

    // 3. Update any available slot badges
    try {
      const todayStr = getLocalTodayString();
      const selectedDate = window.currentSelectedDate || todayStr;
      const matrix = document.querySelector('.slots-matrix');
      if (matrix) {
        const vacantCount = matrix.querySelectorAll('.slot-btn.vacant').length;
        const badge = document.getElementById('availableSlotsBadge');
        if (badge) badge.textContent = vacantCount;
        const legendCount = document.getElementById('legendVacantCount');
        if (legendCount) legendCount.textContent = vacantCount;
      }
    } catch(e) {}

    // Dispatch global event
    window.dispatchEvent(new CustomEvent('fsh_sync_updated', { detail: { bookings: list } }));
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

  // Active Server API Reconciliation (PostgreSQL Single Source of Truth over HTTPS)
  async function reconcileServerState(force = false) {
    const now = Date.now();
    if (!force && now - lastReconciledTime < 1500) return; // Debounce rapid requests
    lastReconciledTime = now;

    try {
      const targetDate = window.currentSelectedDate || document.getElementById('slotDatePicker')?.value || getLocalTodayString();
      const facilitySlug = window.currentFacilitySlug || 'turf';
      const baseUrl = getApiBaseUrl();
      const apiUrl = `${baseUrl}/api/bookings/availability/?facility_slug=${encodeURIComponent(facilitySlug)}&date=${encodeURIComponent(targetDate)}&_t=${now}`;

      const res = await fetch(apiUrl, { method: 'GET' });

      if (res.ok) {
        const data = await res.json();
        if (data && data.success && Array.isArray(data.slots)) {
          // Reconcile server slots into activeBookings for this facility and date
          const activeBookings = getLocalBookings().filter(b => 
            !(b.date === targetDate && (b.facility_slug === facilitySlug || !b.facility_slug))
          );
          
          data.slots.forEach(s => {
            if (s.status === 'PENDING_APPROVAL' || s.status === 'APPROVED' || s.status === 'CONFIRMED' || s.is_booked || s.is_pending) {
              activeBookings.push({
                id: s.booking_id || ('BKG-' + s.start_time),
                booking_id: s.booking_id,
                date: targetDate,
                time: s.start_time,
                start_time: s.start_time,
                end_time: s.end_time,
                facility_slug: facilitySlug,
                status: s.status,
                customer_name: s.customer_name || 'Booked Player',
                total_price: s.price || 900
              });
            }
          });

          saveLocalBookings(activeBookings);
          triggerUIRefresh(activeBookings);
        }
      }
    } catch (err) {
      // Offline fallback: UI continues using existing state
    }
  }

  function initMqtt() {
    if (typeof mqtt === 'undefined') {
      setTimeout(initMqtt, 300);
      return;
    }

    const brokerUrl = BROKERS[currentBrokerIdx];
    const clientId = 'fsh_' + Math.random().toString(16).substr(2, 8);

    try {
      mqttClient = mqtt.connect(brokerUrl, {
        clientId: clientId,
        clean: true,
        connectTimeout: 6000,
        reconnectPeriod: 3000
      });

      mqttClient.on('connect', function() {
        isConnected = true;
        document.querySelectorAll('.fsh-live-indicator').forEach(el => {
          el.innerHTML = '<span class="badge rounded-pill" style="background-color: #E8F7EE; color: #075B36; border: 1px solid #A7F3D0;"><i class="bi bi-broadcast me-1"></i> Live Cloud Synced</span>';
        });

        mqttClient.subscribe(SYNC_TOPIC, { qos: 0 }, function(err) {
          if (err) console.warn('Subscription error:', err);
        });

        // Reconcile server state immediately on connection
        reconcileServerState(true);
      });

      mqttClient.on('message', function(topic, message) {
        if (topic === SYNC_TOPIC) {
          try {
            const raw = message.toString();
            const cloudList = JSON.parse(raw);
            if (Array.isArray(cloudList)) {
              saveLocalBookings(cloudList);
              triggerUIRefresh(cloudList);
            }
          } catch(e) {}
          // Always re-verify against authoritative PostgreSQL database
          reconcileServerState(true);
        }
      });

      mqttClient.on('error', function(err) {
        if (!isConnected && currentBrokerIdx < BROKERS.length - 1) {
          currentBrokerIdx++;
          try { mqttClient.end(true); } catch(e) {}
          setTimeout(initMqtt, 1000);
        }
      });

      mqttClient.on('offline', function() {
        isConnected = false;
      });

    } catch(err) {
      console.warn('MQTT init exception:', err);
    }
  }

  // Universal Push function callable by any page or form
  window.pushCloudBookings = function(list) {
    if (!Array.isArray(list)) list = getLocalBookings();
    saveLocalBookings(list);
    triggerUIRefresh(list);

    if (mqttClient && isConnected) {
      try {
        const payload = JSON.stringify(list);
        mqttClient.publish(SYNC_TOPIC, payload, { retain: true, qos: 0 });
      } catch(e) {}
    }
    // Reconcile with server database
    reconcileServerState(true);
  };

  // Universal Fetch function
  window.fetchCloudBookings = async function() {
    await reconcileServerState(true);
    return getLocalBookings();
  };

  window.reconcileServerState = reconcileServerState;

  window.FSH_SYNC = {
    getBookings: getLocalBookings,
    saveBookings: saveLocalBookings,
    refreshUI: triggerUIRefresh,
    reconcile: reconcileServerState
  };

  // Revalidate on browser window focus, visibility change, and network reconnect
  window.addEventListener('focus', function() { reconcileServerState(true); });
  window.addEventListener('online', function() { reconcileServerState(true); });
  document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'visible') {
      reconcileServerState(true);
    }
  });

  // Background HTTPS reconciliation interval every 6 seconds
  setInterval(function() {
    reconcileServerState(false);
  }, 6000);

  // Start HTTPS sync immediately on load without waiting for MQTT
  function startSync() {
    reconcileServerState(true);
    initMqtt();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startSync);
  } else {
    startSync();
  }
})();
