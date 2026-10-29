const { spawn } = require('child_process');

class ChromeCDP {
  constructor(port = 9222) {
    this.port = port;
    this.ws = null;
    this.id = 1;
    this.callbacks = new Map();
    this.consoleErrors = [];
  }

  async connect() {
    const listRes = await fetch(`http://127.0.0.1:${this.port}/json/list`);
    const pages = await listRes.json();
    const pageData = pages.find(p => p.type === 'page') || pages[0];
    
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(pageData.webSocketDebuggerUrl);
      this.ws.onopen = resolve;
      this.ws.onerror = reject;
      this.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') {
          this.consoleErrors.push(msg.params.args.map(a => a.value || a.description).join(' '));
        }
        if (msg.method === 'Runtime.exceptionThrown') {
          this.consoleErrors.push(msg.params.exceptionDetails.text);
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
    await new Promise(r => setTimeout(r, 800));
  }
}

async function runLiveTests() {
  console.log('--- STARTING LIVE GITHUB PAGES CLICK & ICON AUDIT ---');
  
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const chromeProc = spawn(chromePath, [
    '--headless=new',
    '--remote-debugging-port=9222',
    '--no-sandbox',
    '--disable-gpu',
    '--remote-allow-origins=*'
  ]);

  await new Promise(r => setTimeout(r, 1500));

  const cdp = new ChromeCDP(9222);
  await cdp.connect();
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');

  const liveBase = 'https://akhil-anandan.github.io/friends_sports_hub';
  const results = [];

  function record(pageName, testName, passed, details = '') {
    results.push({ page: pageName, test: testName, passed, details });
    const mark = passed ? '✅ [PASS]' : '❌ [FAIL]';
    console.log(` ${mark} ${pageName}: ${testName} ${details ? '(' + details + ')' : ''}`);
  }

  try {
    // 1. Live Home Page
    await cdp.setViewport(1920, 1080, false);
    await cdp.navigate(`${liveBase}/`);

    const title = await cdp.eval('document.querySelector("h1") ? document.querySelector("h1").innerText : ""');
    record('Live Home', 'Original Hero Heading Present', title.includes('PLAY HARD'), title.replace('\\n', ' '));

    const bookBtn = await cdp.eval('document.querySelector("a[href*=\'book.html\']") !== null');
    record('Live Home', 'Book a Slot Button Present', bookBtn);

    // 2. Live Book Page & Facility Switching
    await cdp.navigate(`${liveBase}/book.html`);
    const tabsCount = await cdp.eval('document.querySelectorAll(".facility-tab-pill").length');
    record('Live Book Page', 'Facility Tabs Rendered', tabsCount === 3, `${tabsCount} tabs`);

    // Test clicking vacant slot
    const slotClicked = await cdp.eval(`
      (() => {
        const slot = document.querySelector('.slot-btn.vacant');
        if (slot) {
          slot.click();
          return true;
        }
        return false;
      })()
    `);
    await new Promise(r => setTimeout(r, 400));
    const modalOpened = await cdp.eval('document.querySelector(".booking-modal-box") ? document.querySelector(".booking-modal-box").classList.contains("open") : false');
    record('Live Book Page', 'Slot Click Opens Modal Popup', modalOpened);

    // 3. Live Login & Owner Dashboard
    await cdp.navigate(`${liveBase}/login.html`);
    await cdp.eval(`
      document.querySelector("input[name='username']").value = 'Admin';
      document.querySelector("input[name='password']").value = 'admin1010';
      document.querySelector("form button[type='submit']").click();
    `);
    await new Promise(r => setTimeout(r, 600));

    const currentUrl = await cdp.eval('window.location.href');
    record('Live Auth', 'Admin Login Redirects to admin.html', currentUrl.includes('admin.html'), currentUrl);

    // Check Live Dashboard Elements
    const portalTag = await cdp.eval('document.querySelector(".badge.bg-warning") ? document.querySelector(".badge.bg-warning").innerText.trim() : ""');
    record('Live Owner Dashboard', 'Director Portal Badge Present', portalTag.includes('Owner / Director'), portalTag);

    const kpiCount = await cdp.eval('document.querySelectorAll(".row.g-3.mb-4 .card").length');
    record('Live Owner Dashboard', 'KPI Metric Row Operational', kpiCount === 4, `${kpiCount} cards`);

    const timelineHeading = await cdp.eval('document.querySelector("h5.text-white.fw-bold") ? document.querySelector("h5.text-white.fw-bold").innerText.trim() : ""');
    record('Live Owner Dashboard', 'Hourly Pitch Schedule Present', timelineHeading.includes('Hourly Pitch Schedule'), timelineHeading);

    // Check Console Errors
    const errors = cdp.consoleErrors;
    record('Live GitHub Pages', 'Zero Console Errors on Live Site', errors.length === 0, errors.join('; '));

  } catch (err) {
    console.error('Error in live test:', err);
    record('Live Execution', 'Completed without error', false, err.message);
  } finally {
    await cdp.send('Browser.close').catch(() => {});
    chromeProc.kill();
  }

  console.log('\n==========================================');
  console.log('       LIVE GITHUB PAGES TEST RESULTS     ');
  console.log('==========================================');
  const passedCount = results.filter(r => r.passed).length;
  const failedCount = results.filter(r => !r.passed).length;
  console.log(`TOTAL TESTS: ${results.length}`);
  console.log(`PASSED:      ${passedCount}`);
  console.log(`FAILED:      ${failedCount}`);
  console.log('==========================================');
}

runLiveTests();

