// Unified Real-Time Multi-Device Synchronization Engine
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
        const currentDate = window.currentSelectedDate || document.getElementById('slotDatePicker')?.value || document.querySelector('input[name="date"]')?.value || new Date().toISOString().split('T')[0];
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
      const todayStr = new Date().toISOString().split('T')[0];
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

  function initMqtt() {
    if (typeof mqtt === 'undefined') {
      console.warn('MQTT library not loaded yet, retrying in 300ms...');
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
        console.log('✅ Real-Time Cloud Synced connected via', brokerUrl);

        // Update live indicator badge if present
        document.querySelectorAll('.fsh-live-indicator').forEach(el => {
          el.innerHTML = '<span class="badge bg-success bg-opacity-25 text-success"><i class="bi bi-broadcast me-1"></i> Live Cloud Synced</span>';
        });

        // Subscribe to master sync topic
        mqttClient.subscribe(SYNC_TOPIC, { qos: 0 }, function(err) {
          if (err) console.warn('Subscription error:', err);
        });
      });

      mqttClient.on('message', function(topic, message, packet) {
        if (topic === SYNC_TOPIC) {
          try {
            const raw = message.toString();
            const cloudList = JSON.parse(raw);
            if (Array.isArray(cloudList)) {
              console.log('🔄 Cloud update received:', cloudList.length, 'bookings');
              saveLocalBookings(cloudList);
              triggerUIRefresh(cloudList);
            }
          } catch(e) {
            console.warn('Invalid sync payload received:', e);
          }
        }
      });

      mqttClient.on('error', function(err) {
        console.warn('MQTT connection warning:', err.message || err);
        // Switch to fallback broker if HiveMQ fails
        if (!isConnected && currentBrokerIdx < BROKERS.length - 1) {
          currentBrokerIdx++;
          try { mqttClient.end(true); } catch(e) {}
          setTimeout(initMqtt, 1000);
        }
      });

      mqttClient.on('offline', function() {
        isConnected = false;
        console.warn('Live Cloud Sync offline, relying on local storage cache');
      });

    } catch(err) {
      console.warn('MQTT init failed:', err);
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
        mqttClient.publish(SYNC_TOPIC, payload, { retain: true, qos: 0 }, function(err) {
          if (err) console.warn('Cloud publish error:', err);
          else console.log('☁️ Pushed update to Cloud Store across all devices');
        });
      } catch(e) {
        console.warn('MQTT publish exception:', e);
      }
    }
  };

  // Universal Fetch function
  window.fetchCloudBookings = async function() {
    return getLocalBookings();
  };

  window.FSH_SYNC = {
    getBookings: getLocalBookings,
    saveBookings: saveLocalBookings,
    refreshUI: triggerUIRefresh
  };

  // Start sync on page load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMqtt);
  } else {
    initMqtt();
  }
})();
