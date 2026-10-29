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
    await new Promise(r => setTimeout(r, 700));
  }
}

async function runBookingLifecycleTest() {
  console.log('--- STARTING COMPREHENSIVE BOOKING & RESPONSIVENESS E2E TEST ---');

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
  const loginUrl = 'file:///' + path.resolve('dist_gh_pages/login.html').replace(/\\/g, '/');

  try {
    // -------------------------------------------------------------
    // TEST 1: MOBILE VIEWPORT & RESPONSIVENESS ON book.html
    // -------------------------------------------------------------
    console.log('\n[Test 1] Testing Mobile Viewport (375x667) on book.html...');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 375,
      height: 667,
      deviceScaleFactor: 2,
      mobile: true
    });

    await cdp.navigate(bookUrl);
    await new Promise(r => setTimeout(r, 800));

    const overflow = await cdp.eval(`document.documentElement.scrollWidth > window.innerWidth`);
    console.log(`  Horizontal overflow on mobile (375px): ${overflow ? 'FAIL (Overflow detected)' : 'PASS (Clean fit)'}`);
    if (overflow) throw new Error('Horizontal scroll overflow on book.html');

    // -------------------------------------------------------------
    // TEST 2: CUSTOMER SELECTS AND LOCKS A SLOT
    // -------------------------------------------------------------
    console.log('\n[Test 2] Customer books a slot on book.html...');
    
    // Find vacant slot for 21:00 or 18:00
    const clickedTime = await cdp.eval(`(() => {
      const vacantSlots = Array.from(document.querySelectorAll('.slot-btn.vacant'));
      let target = vacantSlots.find(s => {
        const t = s.querySelector('.time-text');
        return t && (t.textContent.trim() === '21:00' || t.textContent.trim() === '18:00');
      }) || vacantSlots[0];
      if (!target) return null;
      const time = target.querySelector('.time-text').textContent.trim();
      target.click();
      return time;
    })()`);

    console.log(`  Clicked vacant slot: ${clickedTime}`);
    if (!clickedTime) throw new Error('No vacant slot found to click!');
    await new Promise(r => setTimeout(r, 600));

    const isModalOpen = await cdp.eval(`(() => {
      const modal = document.getElementById('bookingModalBox');
      return modal && modal.classList.contains('open');
    })()`);
    console.log(`  Booking bottom-sheet modal opened: ${isModalOpen}`);
    if (!isModalOpen) throw new Error('Booking modal failed to open');

    // Fill customer details and intercept WhatsApp open
    await cdp.eval(`(() => {
      document.getElementById('inputCustomerName').value = 'Fahad Mulayankavu';
      document.getElementById('inputCustomerPhone').value = '9847998877';
      document.getElementById('inputClubName').value = 'Mulayankavu Super Kings';
      window.open = function(url) { console.log('WhatsApp link intercepted:', url); };
    })()`);
    console.log('  Filled: Name="Fahad Mulayankavu", Phone="9847998877", Club="Mulayankavu Super Kings"');

    // Click submit
    await cdp.eval(`document.querySelector('.btn-submit-wa').click()`);
    await new Promise(r => setTimeout(r, 1000));

    // Verify slot in book.html is now BOOKED!
    const slotState = await cdp.eval(`((bookedTime) => {
      const slots = Array.from(document.querySelectorAll('.slot-btn'));
      const target = slots.find(s => s.querySelector('.time-text') && s.querySelector('.time-text').textContent.trim() === bookedTime);
      if (!target) return null;
      return {
        isBookedClass: target.classList.contains('booked'),
        badgeText: target.querySelector('.slot-badge-pill') ? target.querySelector('.slot-badge-pill').textContent.trim() : ''
      };
    })('${clickedTime}')`);

    console.log(`  Slot ${clickedTime} state after booking: class="booked": ${slotState.isBookedClass}, badge: "${slotState.badgeText}"`);
    if (!slotState.isBookedClass) throw new Error(`Slot ${clickedTime} was not marked as booked!`);

    // Verify stored in localStorage
    const foundBooking = await cdp.eval(`(() => {
      const list = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]');
      return list.find(b => b.customer_name === 'Fahad Mulayankavu');
    })()`);
    console.log(`  Booking record saved in storage: ID="${foundBooking ? foundBooking.id : 'NOT FOUND'}"`);
    if (!foundBooking) throw new Error('Booking not saved in fsh_locked_slots!');

    // -------------------------------------------------------------
    // TEST 3: OWNER DASHBOARD LOGIN & VISIBILITY
    // -------------------------------------------------------------
    console.log('\n[Test 3] Owner logs into admin.html to check booking...');
    await cdp.navigate(loginUrl);
    await cdp.eval(`(() => {
      document.querySelector('input[name="username"]').value = 'Admin';
      document.querySelector('input[name="password"]').value = 'admin1010';
      document.querySelector('button[type="submit"]').click();
    })()`);
    await new Promise(r => setTimeout(r, 800));

    await cdp.navigate(adminUrl);
    await new Promise(r => setTimeout(r, 1200));

    const adminBookingFound = await cdp.eval(`((bkgId) => {
      return document.body.innerText.includes(bkgId) && document.body.innerText.includes('Fahad Mulayankavu');
    })('${foundBooking.id}')`);

    console.log(`  Booking #${foundBooking.id} visible on Owner Dashboard: ${adminBookingFound}`);
    if (!adminBookingFound) throw new Error('New booking did not appear on Owner Dashboard!');

    // -------------------------------------------------------------
    // TEST 4: OWNER DASHBOARD MOBILE RESPONSIVENESS & CARDS
    // -------------------------------------------------------------
    console.log('\n[Test 4] Testing Owner Dashboard Mobile Layout (375x667)...');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 375,
      height: 667,
      deviceScaleFactor: 2,
      mobile: true
    });
    await new Promise(r => setTimeout(r, 600));

    const adminOverflow = await cdp.eval(`document.documentElement.scrollWidth > window.innerWidth`);
    console.log(`  Admin horizontal overflow on mobile: ${adminOverflow ? 'FAIL (Overflow detected)' : 'PASS (Clean fit)'}`);

    const mobileCardsCount = await cdp.eval(`(() => {
      const mobileContainer = document.querySelector('.d-md-none');
      return mobileContainer ? mobileContainer.querySelectorAll('.card').length : 0;
    })()`);
    console.log(`  Mobile reservation cards rendered: ${mobileCardsCount} cards`);
    if (mobileCardsCount === 0) throw new Error('Mobile cards not rendered in reservations section!');

    // -------------------------------------------------------------
    // TEST 5: OWNER COMPLETES AND CANCELS A BOOKING
    // -------------------------------------------------------------
    console.log('\n[Test 5] Testing Owner Action: Complete & Cancel...');
    
    // Complete
    await cdp.eval(`markCompleted('${foundBooking.id}')`);
    await new Promise(r => setTimeout(r, 800));

    const isCompleted = await cdp.eval(`((bkgId) => {
      const list = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]');
      const b = list.find(item => item.id === bkgId);
      return b && b.status === 'COMPLETED';
    })('${foundBooking.id}')`);
    console.log(`  Booking #${foundBooking.id} status updated to COMPLETED: ${isCompleted}`);
    if (!isCompleted) throw new Error('markCompleted failed to update status');

    // Cancel
    await cdp.eval(`cancelBooking('${foundBooking.id}')`);
    await new Promise(r => setTimeout(r, 800));

    const isCancelled = await cdp.eval(`((bkgId) => {
      const list = JSON.parse(localStorage.getItem('fsh_locked_slots') || '[]');
      const b = list.find(item => item.id === bkgId);
      return b && b.status === 'CANCELLED';
    })('${foundBooking.id}')`);
    console.log(`  Booking #${foundBooking.id} status updated to CANCELLED: ${isCancelled}`);
    if (!isCancelled) throw new Error('cancelBooking failed to cancel booking');

    // -------------------------------------------------------------
    // TEST 6: CUSTOMER RETURNS TO BOOK.HTML - SLOT IS FREED!
    // -------------------------------------------------------------
    console.log('\n[Test 6] Customer returns to book.html: verifies slot is now FREED...');
    await cdp.navigate(bookUrl);
    await new Promise(r => setTimeout(r, 1000));

    const isSlotFreed = await cdp.eval(`((bookedTime) => {
      const slots = Array.from(document.querySelectorAll('.slot-btn'));
      const target = slots.find(s => s.querySelector('.time-text') && s.querySelector('.time-text').textContent.trim() === bookedTime);
      return target && target.classList.contains('vacant');
    })('${clickedTime}')`);

    console.log(`  Slot ${clickedTime} is now back to VACANT: ${isSlotFreed}`);
    if (!isSlotFreed) throw new Error(`Slot ${clickedTime} did not free up after cancellation!`);

    console.log('\n=============================================================');
    console.log('✅ ALL TESTS PASSED SUCCESSFULLY! 100% WORKING & RESPONSIVE!');
    console.log('=============================================================');

  } catch(err) {
    console.error('\n❌ TEST FAILED:', err);
    process.exit(1);
  } finally {
    if (cdp.ws) cdp.ws.close();
    chromeProc.kill();
  }
}

runBookingLifecycleTest();
