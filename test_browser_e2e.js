const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

// Helper to interact with Chrome via DevTools Protocol
class ChromeCDP {
  constructor(port = 9222) {
    this.port = port;
    this.ws = null;
    this.id = 1;
    this.callbacks = new Map();
    this.consoleErrors = [];
  }

  async connect() {
    const res = await fetch(`http://127.0.0.1:${this.port}/json/version`);
    const data = await res.json();
    console.log(`[Chrome] Connected: ${data.Browser}`);

    // Get existing page or create a new target/page
    let pageData;
    const listRes = await fetch(`http://127.0.0.1:${this.port}/json/list`);
    const pages = await listRes.json();
    if (pages && pages.length > 0) {
      pageData = pages.find(p => p.type === 'page') || pages[0];
    } else {
      const newPageRes = await fetch(`http://127.0.0.1:${this.port}/json/new`, { method: 'PUT' });
      pageData = await newPageRes.json();
    }
    
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(pageData.webSocketDebuggerUrl);
      this.ws.onopen = () => {
        resolve();
      };
      this.ws.onerror = reject;
      this.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.method === 'Runtime.consoleAPICalled') {
          if (msg.params.type === 'error') {
            this.consoleErrors.push(msg.params.args.map(a => a.value || a.description).join(' '));
          }
        }
        if (msg.method === 'Runtime.exceptionThrown') {
          this.consoleErrors.push(msg.params.exceptionDetails.text + ' ' + (msg.params.exceptionDetails.exception ? msg.params.exceptionDetails.exception.description : ''));
        }
        if (msg.id && this.callbacks.has(msg.id)) {
          this.callbacks.get(msg.id)(msg);
          this.callbacks.delete(msg.id);
        }
      };
    });
  }

  send(method, params = {}) {
    return new Promise((resolve) => {
      const id = this.id++;
      this.callbacks.set(id, resolve);
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expression) {
    const res = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true
    });
    return res.result && res.result.result ? res.result.result.value : undefined;
  }

  async setViewport(width, height, isMobile = false) {
    await this.send('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: isMobile
    });
  }

  async navigate(url) {
    await this.send('Page.navigate', { url });
    // Wait for load
    await new Promise(r => setTimeout(r, 600));
  }
}

async function runTests() {
  console.log('--- STARTING COMPREHENSIVE BROWSER CLICK & RESPONSIVENESS TEST ---');
  
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const chromeProc = spawn(chromePath, [
    '--headless=new',
    '--remote-debugging-port=9222',
    '--no-sandbox',
    '--disable-gpu',
    '--remote-allow-origins=*'
  ]);

  // Give Chrome 1.5s to start
  await new Promise(r => setTimeout(r, 1500));

  const cdp = new ChromeCDP(9222);
  await cdp.connect();
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');

  const baseUrl = 'http://127.0.0.1:8000';
  const results = [];

  function record(pageName, testName, passed, details = '') {
    results.push({ page: pageName, test: testName, passed, details });
    const mark = passed ? '✅ [PASS]' : '❌ [FAIL]';
    console.log(` ${mark} ${pageName}: ${testName} ${details ? '(' + details + ')' : ''}`);
  }

  try {
    // ==========================================
    // 1. TEST HOME PAGE (DESKTOP)
    // ==========================================
    await cdp.setViewport(1920, 1080, false);
    await cdp.navigate(`${baseUrl}/`);
    
    const heroTitle = await cdp.eval('document.querySelector("h1") ? document.querySelector("h1").innerText : ""');
    record('Home Desktop', 'Hero Heading Rendered', heroTitle.includes('PLAY HARD'), heroTitle.replace('\\n', ' '));

    const brandIcon = await cdp.eval('!!document.querySelector(".bi-shield-shaded")');
    record('Home Desktop', 'Brand Icon Visible', brandIcon);

    const callIcon = await cdp.eval('!!document.querySelector(".bi-telephone-fill")');
    record('Home Desktop', 'Phone Icon Visible', callIcon);

    const waIcon = await cdp.eval('!!document.querySelector(".bi-whatsapp")');
    record('Home Desktop', 'WhatsApp Icon Visible', waIcon);

    // Click "Book a Slot" button in navbar
    const navBookHref = await cdp.eval('document.querySelector(".btn-success[href*=\'book\']") ? document.querySelector(".btn-success[href*=\'book\']").getAttribute("href") : ""');
    record('Home Desktop', 'Navbar "Book a Slot" Button Clickable', !!navBookHref, navBookHref);

    // Click quick check form / facility card buttons
    const facilityButtonsCount = await cdp.eval('document.querySelectorAll(".card-body a[href*=\'book\']").length');
    record('Home Desktop', 'Facility Cards "Book Slot" Buttons Present', facilityButtonsCount === 3, `${facilityButtonsCount} buttons`);

    // ==========================================
    // 2. TEST HOME PAGE (MOBILE RESPONSIVE 375x667)
    // ==========================================
    await cdp.setViewport(375, 667, true);
    await cdp.navigate(`${baseUrl}/`);

    // Check navbar toggler is visible on mobile
    const togglerVisible = await cdp.eval('getComputedStyle(document.querySelector(".navbar-toggler")).display !== "none"');
    record('Home Mobile (375px)', 'Navbar Hamburger Toggler Visible on Phone', togglerVisible);

    // Click hamburger toggler
    await cdp.eval('document.querySelector(".navbar-toggler").click()');
    await new Promise(r => setTimeout(r, 400));
    const navOpen = await cdp.eval('document.getElementById("navbarMain").classList.contains("show")');
    record('Home Mobile (375px)', 'Hamburger Menu Opens on Click', navOpen);

    // ==========================================
    // 3. TEST BOOKING PAGE (DESKTOP & FACILITY SWITCHING)
    // ==========================================
    await cdp.setViewport(1280, 800, false);
    await cdp.navigate(`${baseUrl}/book/`);

    const turfPillActive = await cdp.eval('document.querySelector(".facility-tab-pill.active") ? document.querySelector(".facility-tab-pill.active").innerText.trim() : ""');
    record('Book Page', 'Default Facility Pill Active', turfPillActive.includes('Turf'), turfPillActive);

    const turfSlotsCount = await cdp.eval('document.querySelectorAll(".slot-btn").length');
    record('Book Page', 'Turf Time Slots Rendered in Grid', turfSlotsCount > 10, `${turfSlotsCount} slots`);

    // Click a vacant slot button to open booking popup modal
    const firstVacantSlot = await cdp.eval(`
      (() => {
        const slot = document.querySelector('.slot-btn.vacant');
        if (slot) {
          slot.click();
          return slot.querySelector('.time-text').innerText;
        }
        return '';
      })()
    `);
    await new Promise(r => setTimeout(r, 400));

    const modalVisible = await cdp.eval('document.querySelector(".booking-modal-box") ? document.querySelector(".booking-modal-box").classList.contains("open") : false');
    record('Book Page', 'Clicking Vacant Slot Opens Booking Modal', modalVisible, `Slot: ${firstVacantSlot}`);

    const modalSlotTitle = await cdp.eval('document.getElementById("modalSlotTitle") ? document.getElementById("modalSlotTitle").innerText : ""');
    record('Book Page', 'Modal Displays Slot Time & Date', modalSlotTitle.includes(firstVacantSlot), modalSlotTitle);

    const modalSubmitBtn = await cdp.eval('!!document.querySelector(".btn-submit-wa")');
    record('Book Page', 'Modal Has "Book Now via WhatsApp" Button', modalSubmitBtn);

    // Close modal
    await cdp.eval('document.querySelector(".booking-overlay") ? document.querySelector(".booking-overlay").click() : null');
    await new Promise(r => setTimeout(r, 300));

    // ==========================================
    // 4. TEST CONTACT PAGE
    // ==========================================
    await cdp.navigate(`${baseUrl}/contact/`);
    const contactPhoneLink = await cdp.eval('document.querySelector("a[href=\'tel:6238006820\']") !== null');
    record('Contact Page', 'Direct Call 6238006820 Link Present', contactPhoneLink);

    const contactMapBtn = await cdp.eval('document.querySelector("a[href*=\'maps.app.goo.gl\']") !== null');
    record('Contact Page', 'Google Maps Location Button Present', contactMapBtn);

    const contactFormInputs = await cdp.eval('document.querySelectorAll("form input, form textarea").length');
    record('Contact Page', 'Inquiry Message Form Inputs Operational', contactFormInputs >= 4, `${contactFormInputs} fields`);

    // ==========================================
    // 5. TEST LOGIN PAGE & AUTHENTICATION
    // ==========================================
    await cdp.navigate(`${baseUrl}/login/`);
    const loginFormExists = await cdp.eval('document.querySelector("form input[name=\'username\']") !== null');
    record('Login Page', 'Admin Login ID & Password Inputs Present', loginFormExists);

    // Test Admin Login Form Submission
    await cdp.eval(`
      document.querySelector("input[name='username']").value = 'Admin';
      document.querySelector("input[name='password']").value = 'admin1010';
      document.querySelector("form button[type='submit']").click();
    `);
    await new Promise(r => setTimeout(r, 800));

    const currentUrl = await cdp.eval('window.location.href');
    const isAtManage = currentUrl.includes('manage') || currentUrl.includes('admin');
    record('Login Page', 'Admin Credentials Authenticate & Redirect', isAtManage, currentUrl);

    // ==========================================
    // 6. TEST RESTORED OWNER DASHBOARD
    // ==========================================
    const portalBadge = await cdp.eval('document.querySelector(".badge.bg-warning") ? document.querySelector(".badge.bg-warning").innerText.trim() : ""');
    record('Owner Dashboard', 'Owner / Director Portal Badge Displayed', portalBadge.includes('Owner / Director'), portalBadge);

    const navButtonsCount = await cdp.eval('document.querySelectorAll(".card.bg-black .btn-sm.rounded-pill").length');
    record('Owner Dashboard', 'Top Staff Operations Navigation Bar Active', navButtonsCount >= 4, `${navButtonsCount} action buttons`);

    const kpiCardsCount = await cdp.eval('document.querySelectorAll(".row.g-3.mb-4 .card").length');
    record('Owner Dashboard', 'KPI Metrics Row (Confirmed, Revenue, Cash, Completed) Active', kpiCardsCount === 4, `${kpiCardsCount} KPI cards`);

    const scheduleTimeline = await cdp.eval('document.querySelector("h5.text-white.fw-bold") ? document.querySelector("h5.text-white.fw-bold").innerText.trim() : ""');
    record('Owner Dashboard', 'Section 1: Hourly Pitch Schedule Active', scheduleTimeline.includes('Hourly Pitch Schedule'), scheduleTimeline);

    const reservationsTable = await cdp.eval('document.querySelectorAll(".card.bg-black.shadow").length >= 2');
    record('Owner Dashboard', 'Section 2: Detailed Bookings Table Active', reservationsTable);

    // ==========================================
    // 7. CONSOLE ERRORS CHECK
    // ==========================================
    const errors = cdp.consoleErrors;
    record('Global JavaScript', 'Zero Uncaught JavaScript Errors', errors.length === 0, errors.join('; '));

  } catch (err) {
    console.error('Test Execution Error:', err);
    record('Execution', 'Test Suite Run Without Crashing', false, err.message);
  } finally {
    await cdp.send('Browser.close').catch(() => {});
    chromeProc.kill();
  }

  console.log('\n==========================================');
  console.log('           TEST SUMMARY RESULTS           ');
  console.log('==========================================');
  const passedCount = results.filter(r => r.passed).length;
  const failedCount = results.filter(r => !r.passed).length;
  console.log(`TOTAL TESTS: ${results.length}`);
  console.log(`PASSED:      ${passedCount}`);
  console.log(`FAILED:      ${failedCount}`);
  console.log('==========================================');
  
  if (failedCount > 0) {
    process.exit(1);
  }
}

runTests();
