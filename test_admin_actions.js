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
        if (msg.method === 'Page.javascriptDialogOpening') {
          // Auto-accept alert/confirm prompts
          this.send('Page.handleJavaScriptDialog', { accept: true });
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

  async navigate(url) {
    await this.send('Page.navigate', { url });
    await new Promise(r => setTimeout(r, 600));
  }
}

async function runTest() {
  console.log('--- TESTING OWNER DASHBOARD COMPLETE & CANCEL BUTTONS ---');

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

  try {
    // 1. Open admin.html directly with session auth set
    await cdp.navigate('http://127.0.0.1:8000/login/');
    await cdp.eval(`
      sessionStorage.setItem('fsh_admin_logged_in', 'true');
    `);

    // Let's load dist_gh_pages/admin.html via file or serve it
    // Wait, let's load http://127.0.0.1:8000/manage/ AND also file://
    const adminFilePath = 'file:///' + 'c:/Users/User/OneDrive/Desktop/Friends_soprts_hub/dist_gh_pages/admin.html'.replace(/\\\\/g, '/');
    await cdp.navigate(adminFilePath);
    await cdp.eval(`sessionStorage.setItem('fsh_admin_logged_in', 'true');`);
    await cdp.navigate(adminFilePath);
    await new Promise(r => setTimeout(r, 600));

    console.log('[Test] admin.html loaded');

    // 2. Check initial bookings
    const initialCompletedKpi = await cdp.eval('document.querySelectorAll(".row.g-3.mb-4 .fs-2")[3].innerText');
    console.log('[Test] Initial Completed KPI:', initialCompletedKpi);

    const initialConfirmedKpi = await cdp.eval('document.querySelectorAll(".row.g-3.mb-4 .fs-2")[0].innerText');
    console.log('[Test] Initial Confirmed KPI:', initialConfirmedKpi);

    // 3. Click "Complete" button on first booking (BKG-FSH-101)
    console.log('[Test] Clicking "Complete" button on BKG-FSH-101...');
    const completeClicked = await cdp.eval(`
      (() => {
        const btn = document.querySelector('button[onclick*="markCompleted(\\\'BKG-FSH-101\\\')"]');
        if (btn) {
          btn.click();
          return true;
        }
        return false;
      })()
    `);
    console.log('[Test] Complete button found and clicked:', completeClicked);
    await new Promise(r => setTimeout(r, 400));

    // Verify status updated to COMPLETED
    const bkg101Badge = await cdp.eval(`
      (() => {
        const b = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]').find(x => x.id === 'BKG-FSH-101');
        return b ? b.status : 'NOT FOUND';
      })()
    `);
    console.log('[Test] BKG-FSH-101 status in storage:', bkg101Badge);

    const completedKpiAfter = await cdp.eval('document.querySelectorAll(".row.g-3.mb-4 .fs-2")[3].innerText');
    console.log('[Test] Completed KPI after clicking Complete:', completedKpiAfter);

    const isCompleteFinished = await cdp.eval(`
      (() => {
        const row = document.querySelector('tr td.font-monospace');
        return document.body.innerHTML.includes('Finished');
      })()
    `);
    console.log('[Test] Displays "Finished" badge on finished match:', isCompleteFinished);

    // 4. Click "Cancel" button on second booking (BKG-FSH-102)
    console.log('[Test] Clicking "Cancel" button on BKG-FSH-102...');
    const cancelClicked = await cdp.eval(`
      (() => {
        const btn = document.querySelector('button[onclick*="cancelBooking(\\\'BKG-FSH-102\\\')"]');
        if (btn) {
          btn.click();
          return true;
        }
        return false;
      })()
    `);
    console.log('[Test] Cancel button found and clicked:', cancelClicked);
    await new Promise(r => setTimeout(r, 400));

    // Verify slot freed in schedule
    const isSlotFreed = await cdp.eval(`
      (() => {
        const freeSlots = Array.from(document.querySelectorAll('.card.h-100')).filter(c => c.innerText.includes('FREE / OPEN'));
        return freeSlots.some(s => s.innerText.includes('08:00 PM - 09:00 PM'));
      })()
    `);
    console.log('[Test] 08:00 PM - 09:00 PM slot is now FREE / OPEN in schedule:', isSlotFreed);

    const cancelledLabel = await cdp.eval('document.querySelector(".row.g-3.mb-4 .col-6.col-lg-3:last-child small").innerText');
    console.log('[Test] Cancelled KPI counter updated:', cancelledLabel);

    const tableHasCancelled = await cdp.eval(`
      (() => {
        return document.querySelector('#reservationsSection') ? document.querySelector('#reservationsSection').innerText.includes('CANCELLED') : false;
      })()
    `);
    console.log('[Test] Detailed Bookings table displays CANCELLED status:', tableHasCancelled);

    const allPassed = completeClicked && bkg101Badge === 'COMPLETED' && isSlotFreed && tableHasCancelled;
    console.log('\n==========================================');
    if (allPassed) {
      console.log('✅ ALL OWNER DASHBOARD ACTIONS (COMPLETE & CANCEL) VERIFIED WORKING 100%!');
    } else {
      console.log('❌ SOME ACTIONS FAILED');
    }
    console.log('==========================================');

  } catch(e) {
    console.error('Test error:', e);
  } finally {
    await cdp.send('Browser.close').catch(() => {});
    chromeProc.kill();
  }
}

runTest();
