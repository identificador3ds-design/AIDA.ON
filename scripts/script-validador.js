/* ==========================================================================
   AIDA — validador de código de acesso antecipado (TAC)
   ==========================================================================
   Extraído do HTML para que a página rode sob a CSP sem `unsafe-inline`.
   Continua sendo validação de front-end: serve como protótipo visual. Para
   uso real, a conferência do código precisa acontecer no backend.
   ========================================================================== */

const accessTickets = [
  { ticketCode: '563-621-1960', phase: 'F1', accessId: '014', lot: 'M' },
  { ticketCode: '633-709-8940', phase: 'F1', accessId: '015', lot: 'M' },
  { ticketCode: '609-425-8913', phase: 'F1', accessId: '016', lot: 'M' },
  { ticketCode: '531-192-9752', phase: 'F1', accessId: '017', lot: 'M' },
  { ticketCode: '594-533-7744', phase: 'F1', accessId: '018', lot: 'M' },
  { ticketCode: '449-127-6681', phase: 'F2', accessId: '019', lot: 'M' },
  { ticketCode: '782-314-2057', phase: 'F2', accessId: '020', lot: 'M' },
  { ticketCode: '218-906-4473', phase: 'F2', accessId: '021', lot: 'M' },
  { ticketCode: '375-842-1906', phase: 'F2', accessId: '022', lot: 'M' },
  { ticketCode: '846-275-6318', phase: 'F2', accessId: '023', lot: 'M' },
  { ticketCode: '927-160-5842', phase: 'F3', accessId: '024', lot: 'M' },
  { ticketCode: '184-653-9721', phase: 'F3', accessId: '025', lot: 'M' },
  { ticketCode: '668-491-3054', phase: 'F3', accessId: '026', lot: 'M' },
  { ticketCode: '302-778-1469', phase: 'F3', accessId: '027', lot: 'M' },
  { ticketCode: '715-234-8801', phase: 'F1', accessId: '028', lot: 'M' },
  { ticketCode: '491-860-2275', phase: 'F1', accessId: '029', lot: 'M' },
  { ticketCode: '256-719-6348', phase: 'F2', accessId: '030', lot: 'M' },
  { ticketCode: '880-342-5176', phase: 'F2', accessId: '031', lot: 'M' },
  { ticketCode: '643-195-7083', phase: 'F3', accessId: '032', lot: 'M' },
  { ticketCode: '519-486-9314', phase: 'F3', accessId: '033', lot: 'M' }
];

const phaseMap = { F1: 1, F2: 2, F3: 3, F4: 4 };

function lotValue(letter) {
  return letter.toUpperCase().charCodeAt(0) - 64;
}

// Nova lÃ³gica: um Ãºnico tipo de acesso, entÃ£o o TAC depende sÃ³ de lote, fase e ID.
function calculateVerifier(lot, phase, accessId) {
  const phaseValue = phaseMap[phase];
  const idValue = Number(accessId);
  const total = (phaseValue * 17) + (idValue * 7) + (lotValue(lot) * 3) + 11;
  return String(total % 100).padStart(2, '0');
}

function buildTac(ticket) {
  const vv = calculateVerifier(ticket.lot, ticket.phase, ticket.accessId);
  return `${ticket.lot}-${ticket.phase}-${ticket.accessId}-${vv}`;
}

const database = accessTickets.map(ticket => ({ ...ticket, tac: buildTac(ticket) }));

const resultBox = document.getElementById('resultBox');
const lotInput = document.getElementById('lotInput');
const phaseInput = document.getElementById('phaseInput');
const idInput = document.getElementById('idInput');
const vvInput = document.getElementById('vvInput');
const checkBtn = document.getElementById('checkBtn');

function normalizeTacPart(value) {
  return value.trim().toUpperCase().replace(/\s+/g, '');
}

function openProtectedArea(ticket) {
  sessionStorage.setItem('aida_early_access', 'granted');
  sessionStorage.setItem('aida_ticket_code', ticket.ticketCode);
  sessionStorage.setItem('aida_tac', ticket.tac);

  // Troque pela rota real do seu site.
  setTimeout(() => {
    window.location.href = '../index.html';
  }, 1200);
}

function validateTac() {
  const lot = normalizeTacPart(lotInput.value);
  const phase = normalizeTacPart(phaseInput.value);
  const accessId = normalizeTacPart(idInput.value);
  const receivedVerifier = normalizeTacPart(vvInput.value);
  const raw = `${lot}-${phase}-${accessId}-${receivedVerifier}`;

  if (!lot || !phase || !accessId || !receivedVerifier) {
    resultBox.innerHTML = `<div class="status warning">Preencha todos os campos do TAC para validar.</div>`;
    return;
  }

  if (!phaseMap[phase] || !/^\d{3}$/.test(accessId) || !/^[A-Z]$/.test(lot) || !/^\d{2}$/.test(receivedVerifier)) {
    resultBox.innerHTML = `
      <div class="status error">Os dados informados nÃ£o seguem a estrutura esperada pelo sistema.</div>
    `;
    return;
  }

  const expectedVerifier = calculateVerifier(lot, phase, accessId);
  const fullTac = `${lot}-${phase}-${accessId}-${expectedVerifier}`;
  const existing = database.find(item => item.tac === raw);
  const sameBaseExists = database.find(item => item.lot === lot && item.phase === phase && item.accessId === accessId);

  if (existing && receivedVerifier === expectedVerifier) {
    resultBox.innerHTML = `
      <div class="status success">TAC vÃ¡lido. Acesso liberado com sucesso.</div>
      <div class="details">
        <div class="detail-box"><small>Ticket Code</small><strong>${existing.ticketCode}</strong></div>
        <div class="detail-box"><small>Fase</small><strong>${existing.phase}</strong></div>
        <div class="detail-box"><small>ID de acesso</small><strong>${existing.accessId}</strong></div>
        <div class="detail-box"><small>Status</small><strong>Liberado</strong></div>
      </div>
      <p class="foot">Redirecionando para a Ã¡rea do projeto...</p>
    `;
    openProtectedArea(existing);
    return;
  }

  if (sameBaseExists && receivedVerifier !== expectedVerifier) {
    resultBox.innerHTML = `
      <div class="status error">TAC invÃ¡lido. O verificador final nÃ£o confere.</div>
      <div class="details">
        <div class="detail-box"><small>TAC informado</small><strong class="mono">${raw}</strong></div>
        <div class="detail-box"><small>TAC correto</small><strong class="mono">${fullTac}</strong></div>
      </div>
      <p class="foot">Esse cÃ³digo parece ter sido alterado manualmente.</p>
    `;
    return;
  }

  if (!sameBaseExists && receivedVerifier === expectedVerifier) {
    resultBox.innerHTML = `
      <div class="status warning">O TAC Ã© coerente pela fÃ³rmula, mas nÃ£o existe na base autorizada.</div>
      <div class="details">
        <div class="detail-box"><small>Status</small><strong>NÃ£o autorizado</strong></div>
        <div class="detail-box"><small>TAC calculado</small><strong class="mono">${fullTac}</strong></div>
      </div>
      <p class="foot">Somente TACs cadastrados pela equipe liberam acesso.</p>
    `;
    return;
  }

  resultBox.innerHTML = `
    <div class="status error">TAC invÃ¡lido e nÃ£o autorizado.</div>
    <div class="details">
      <div class="detail-box"><small>TAC informado</small><strong class="mono">${raw}</strong></div>
      <div class="detail-box"><small>Verificador esperado</small><strong>${expectedVerifier}</strong></div>
    </div>
    <p class="foot">O cÃ³digo nÃ£o corresponde a um convite real de acesso antecipado.</p>
  `;
}

checkBtn.addEventListener('click', validateTac);
[lotInput, phaseInput, idInput, vvInput].forEach((input, index, inputs) => {
  input.addEventListener('input', () => {
input.value = normalizeTacPart(input.value);
const max = Number(input.getAttribute('maxlength'));
if (input.value.length >= max && inputs[index + 1]) {
  inputs[index + 1].focus();
}
  });

  input.addEventListener('keydown', (event) => {
if (event.key === 'Enter') validateTac();
  });
});

checkBtn.addEventListener('click', validateTac);

// Dificulta atalhos comuns de inspeÃ§Ã£o, mas nÃ£o substitui backend.
document.addEventListener('contextmenu', (event) => event.preventDefault());
document.addEventListener('keydown', (event) => {
  const key = event.key.toUpperCase();
  if (
    key === 'F12' ||
    (event.ctrlKey && event.shiftKey && ['I', 'J', 'C'].includes(key)) ||
    (event.ctrlKey && key === 'U')
  ) {
    event.preventDefault();
  }
});
