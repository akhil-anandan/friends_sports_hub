const { spawn } = require('child_process');
const path = require('path');

class ChromeCDP {
  constructor(port = 9222) {
    this.port = port;
    this.ws = null;
    this.id = 1;
    this.callbacks = new Map();
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

  async setViewport(width, height) {
    await this.send('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 2,
      mobile: width < 768
    });
  }

  async navigate(url) {
    await this.send('Page.navigate', { url });
    await new Promise(r => setTimeout(r, 600));
  }
}

async function auditResponsiveness() {
  console.log('--- STARTING MULTI-DEVICE RESPONSIVENESS AUDIT ---');

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

  const viewports = [
    { name: 'Small Phone (iPhone SE)', width: 320, height: 568 },
    { name: 'Standard Phone (iPhone 13/14)', width: 375, height: 812 },
    { name: 'Large Phone (Galaxy S22 / Pro Max)', width: 414, height: 896 },
    { name: 'Tablet Portrait (iPad Mini/Air)', width: 768, height: 1024 },
    { name: 'Tablet Landscape / Laptop', width: 1024, height: 768 },
    { name: 'Desktop Monitor', width: 1440, height: 900 }
  ];

  const pages = [
    { name: 'Home Page', file: 'dist_gh_pages/index.html' },
    { name: 'Booking Page', file: 'dist_gh_pages/book.html' },
    { name: 'Admin Dashboard', file: 'dist_gh_pages/admin.html' },
    { name: 'About Page', file: 'dist_gh_pages/about.html' },
    { name: 'Walk-in Page', file: 'dist_gh_pages/walk-in.html' },
    { name: 'Login Page', file: 'dist_gh_pages/login.html' },
    { name: 'Contact Page', file: 'dist_gh_pages/contact.html' },
    { name: 'Facilities Page', file: 'dist_gh_pages/facilities.html' },
    { name: 'Pricing Page', file: 'dist_gh_pages/pricing.html' },
    { name: 'Reports Page', file: 'dist_gh_pages/reports.html' },
    { name: 'Employees Page', file: 'dist_gh_pages/employees.html' }
  ];

  let totalIssues = 0;

  for (const page of pages) {
    const fileUrl = 'file:///' + path.resolve(page.file).replace(/\\/g, '/');
    console.log(`\nTesting ${page.name} (${page.file})...`);

    for (const vp of viewports) {
      await cdp.setViewport(vp.width, vp.height);
      await cdp.navigate(fileUrl);
      if (page.name === 'Admin Dashboard') {
        await cdp.eval(`sessionStorage.setItem('fsh_admin_logged_in', 'true');`);
        await cdp.navigate(fileUrl);
      }
      await new Promise(r => setTimeout(r, 400));

      const overflow = await cdp.eval(`
        (() => {
          const docEl = document.documentElement;
          const body = document.body;
          const scrollWidth = Math.max(docEl.scrollWidth, body.scrollWidth);
          const clientWidth = docEl.clientWidth;
          const hasOverflow = scrollWidth > clientWidth + 1; // 1px threshold for rounding
          let overflowingElements = [];
          if (hasOverflow) {
            document.querySelectorAll('*').forEach(el => {
              const rect = el.getBoundingClientRect();
              if (rect.right > clientWidth + 2) {
                overflowingElements.push({
                  tag: el.tagName,
                  class: el.className,
                  id: el.id,
                  right: rect.right,
                  width: rect.width
                });
              }
            });
          }
          return { hasOverflow, scrollWidth, clientWidth, overflowingElements: overflowingElements.slice(0, 3) };
        })()
      `);

      if (overflow && overflow.hasOverflow) {
        console.error(`  ❌ [OVERFLOW] ${vp.name} (${vp.width}px): scrollWidth=${overflow.scrollWidth}px vs clientWidth=${overflow.clientWidth}px`);
        console.error('     Elements causing overflow:', JSON.stringify(overflow.overflowingElements));
        totalIssues++;
      } else {
        console.log(`  ✅ [PASS] ${vp.name} (${vp.width}px): No horizontal overflow`);
      }
    }
  }

  console.log('\n==========================================');
  console.log(`RESPONSIVENESS AUDIT COMPLETE: ${totalIssues} issues found.`);
  console.log('==========================================');

  await cdp.send('Browser.close').catch(() => {});
  chromeProc.kill();
}

auditResponsiveness();
