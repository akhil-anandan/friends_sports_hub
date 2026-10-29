// Friends Sports Hub Mulayankavu Main JS

function buildBookingMessage() {
  const el = document.getElementById('bookingData');
  if (!el) return '';
  const d = el.dataset;
  const lines = [
    '🏆 *FRIENDS SPORTS HUB MULAYANKAVU*',
    '✅ *Booking Confirmed!*',
    '',
    '📋 *Ref ID:* ' + (d.id || ''),
    '👤 *Name:* ' + (d.name || ''),
    d.club ? ('👥 *Club/Team:* ' + d.club) : '',
    '🏟️ *Facility:* ' + (d.facility || ''),
    '📅 *Date:* ' + (d.date || ''),
    '⏰ *Time:* ' + (d.start || '') + ' – ' + (d.end || ''),
    '💰 *Fee:* ₹' + (d.price || '0') + ' (Pay at Venue)',
    '',
    '📍 *Location:* Kulukkallur, Mulayankavu, Palakkad',
    '📞 *Helpline:* 6238006820',
    '',
    '⚠️ *Instructions:*',
    '• Please report 10 minutes before slot time.',
    '• Turf shoes or sports sneakers only (no metal studs).',
    '',
    'See you on the pitch! ⚽'
  ];
  return lines.filter(Boolean).join('\n');
}

function sendCustomerWhatsApp() {
  const el = document.getElementById('bookingData');
  if (!el) return;
  const d = el.dataset;
  let rawPhone = (d.phone || '').replace(/\D/g, '');
  if (rawPhone.length === 11 && rawPhone.startsWith('0')) {
    rawPhone = rawPhone.substring(1);
  }
  const cleanPhone = rawPhone.length === 10 ? '91' + rawPhone : rawPhone;
  const msg = buildBookingMessage();
  const url = cleanPhone
    ? 'https://api.whatsapp.com/send?phone=' + cleanPhone + '&text=' + encodeURIComponent(msg)
    : 'https://api.whatsapp.com/send?text=' + encodeURIComponent(msg);

  const isMobile = /Android|iPhone|iPad|iPod|webOS|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
  if (isMobile) {
    window.location.href = url;
  } else {
    const link = document.createElement('a');
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    document.body.appendChild(link);
    link.click();
    link.remove();
  }
}

function copyBookingDetails() {
  const msg = buildBookingMessage();
  if (!msg) return;
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(msg).then(() => {
      alert('Booking confirmation copied to clipboard!');
    }).catch(() => {
      prompt('Copy this text:', msg);
    });
  } else {
    prompt('Copy this text:', msg);
  }
}
