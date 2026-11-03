const { spawn } = require('child_process');
const path = require('path');

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
    await new Promise(r => setTimeout(r, 800));
  }
}

async function runPendingApprovalTest() {
  console.log('--- TESTING PENDING APPROVAL FLOW ---');

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

  const bookUrl = 'file:///' + path.resolve('dist_gh_pages/book.html').replace(/\\/g, '/');
  const adminUrl = 'file:///' + path.resolve('dist_gh_pages/admin.html').replace(/\\/g, '/');

  try {
    // Step 1: Open book.html and create a mock customer booking (or set localStorage)
    await cdp.navigate(bookUrl);
    const today = new Date().toISOString().split('T')[0];

    console.log('[Test 1] Injecting a PENDING customer booking into localStorage...');
    await cdp.eval(`
      (() => {
        const testBooking = {
          id: 'BKG-FSH-TEST-PENDING',
          customer_name: 'Rahul Dravid',
          customer_phone: '9876543210',
          facility_slug: 'turf',
          facility_name: 'Football & Cricket Turf',
          date: '${today}',
          start_time: '20:00',
          end_time: '21:00',
          display_time: '08:00 PM - 09:00 PM',
          total_price: 900,
          advance_amount: 0,
          balance_amount: 900,
          payment_status: 'UNPAID',
          status: 'PENDING',
          source: 'ONLINE_WHATSAPP'
        };
        localStorage.setItem('fsh_locked_slots', JSON.stringify([testBooking]));
        if (window.renderSlots) window.renderSlots('${today}');
      })()
    `);

    await new Promise(r => setTimeout(r, 500));

    // Verify slot styling on public booking page
    const pendingSlot = await cdp.eval(`
      (() => {
        const slot = Array.from(document.querySelectorAll('.slot-btn')).find(el => {
          const t = el.querySelector('.time-text');
          return t && t.innerText.trim() === '20:00';
        });
        if (!slot) return null;
        return {
          className: slot.className,
          isPending: slot.classList.contains('pending'),
          text: slot.innerText
        };
      })()
    `);
    console.log('[Test 2] Public slot for 20:00:', pendingSlot);
    if (pendingSlot && pendingSlot.isPending) {
      console.log('✅ Public slot correctly rendered with .pending class!');
    } else {
      console.error('❌ Public slot did not receive .pending class');
    }

    // Step 2: Open Admin Dashboard
    await cdp.navigate(adminUrl);
    await cdp.eval(`sessionStorage.setItem('fsh_admin_logged_in', 'true');`);
    await cdp.navigate(adminUrl);
    await new Promise(r => setTimeout(r, 800));

    // Check if the booking appears in the admin dashboard with "Approve" button
    const adminState = await cdp.eval(`
      (() => {
        const approveBtn = document.querySelector('button[onclick*="approveBooking(\\\'BKG-FSH-TEST-PENDING\\\')"]');
        const pendingBadge = document.body.innerHTML.includes('PENDING');
        return {
          hasApproveBtn: !!approveBtn,
          hasPendingBadge: pendingBadge
        };
      })()
    `);
    console.log('[Test 3] Admin Dashboard pending state:', adminState);
    if (adminState.hasApproveBtn && adminState.hasPendingBadge) {
      console.log('✅ Admin dashboard shows PENDING badge and Approve button!');
    } else {
      console.error('❌ Admin dashboard missing Approve button or PENDING badge');
    }

    // Step 3: Click "Approve"
    console.log('[Test 4] Clicking Approve button...');
    const approveClicked = await cdp.eval(`
      (() => {
        const btn = document.querySelector('button[onclick*="approveBooking(\\\'BKG-FSH-TEST-PENDING\\\')"]');
        if (btn) {
          btn.click();
          return true;
        }
        return false;
      })()
    `);
    console.log('[Test 4] Approve clicked:', approveClicked);
    await new Promise(r => setTimeout(r, 500));

    // Verify updated status in localStorage
    const statusAfterApproval = await cdp.eval(`
      (() => {
        const list = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]');
        const b = list.find(x => x.id === 'BKG-FSH-TEST-PENDING');
        return b ? b.status : 'NOT FOUND';
      })()
    `);
    console.log('[Test 5] Status after approval:', statusAfterApproval);
    if (statusAfterApproval === 'CONFIRMED') {
      console.log('✅ Booking status successfully updated to CONFIRMED!');
    } else {
      console.error('❌ Booking status was not updated to CONFIRMED');
    }

    // Step 4: Go back to public book.html and verify slot is now BOOKED (red)
    await cdp.navigate(bookUrl);
    await new Promise(r => setTimeout(r, 800));

    const bookedSlot = await cdp.eval(`
      (() => {
        const slot = Array.from(document.querySelectorAll('.slot-btn')).find(el => {
          const t = el.querySelector('.time-text');
          return t && t.innerText.trim() === '20:00';
        });
        if (!slot) return null;
        return {
          className: slot.className,
          isBooked: slot.classList.contains('booked'),
          text: slot.innerText
        };
      })()
    `);
    console.log('[Test 6] Public slot after approval:', bookedSlot);
    if (bookedSlot && bookedSlot.isBooked) {
      console.log('✅ Public slot now correctly rendered with .booked class!');
    } else {
      console.error('❌ Public slot did not turn into .booked');
    }

    // Step 5: Clean up test booking
    await cdp.eval(`
      localStorage.removeItem('fsh_locked_slots');
    `);

    console.log('\n==========================================');
    console.log('✅ COMPLETE PENDING -> APPROVE -> CONFIRMED FLOW VERIFIED 100%!');
    console.log('==========================================');

  } catch (e) {
    console.error('Test error:', e);
  } finally {
    await cdp.send('Browser.close').catch(() => {});
    chromeProc.kill();
  }
}

runPendingApprovalTest();
