// ============ PULSAR MINI APP — FULL BACKEND INTEGRATION ============

const API_BASE = '';  // Same origin

const tg = window.Telegram?.WebApp;
if (tg) {
  tg.expand();
  tg.enableClosingConfirmation();
}

// Get initData from Telegram
function getInitData() {
  return tg?.initData || '';
}

// API call helper
async function apiCall(endpoint, method = 'POST', body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) {
    opts.body = JSON.stringify({ ...body, init_data: getInitData() });
  } else {
    opts.body = JSON.stringify({ init_data: getInitData() });
  }
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, opts);
    const data = await res.json();
    if (!res.ok && res.status !== 200) {
      return { error: data.error || 'Server error', status: res.status, ...data };
    }
    return data;
  } catch (e) {
    console.error('API Error:', e);
    return { error: 'Network error' };
  }
}

// ============ STATE ============

const state = {
  balance: 0,
  gems: 0,
  energy: 100,
  maxEnergy: 100,
  level: 1,
  xp: 0,
  xpNeed: 100,
  passivePerHour: 0,
  combo: 0,
  comboMult: 1.0,
  activeSkin: { name: 'STANDART', tapBonus: 1 },
  dailyStreak: 0,
  userId: 0,
  username: '',
  fullName: '',
  tapBuffer: 0,  // Taplarni yig'ish — serverga yuborish uchun
};

// ============ SOUND ============

const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
function playSynthSound(type) {
  if (audioCtx.state === 'suspended') audioCtx.resume();
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  if (type === 'tap') {
    osc.frequency.setValueAtTime(440, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(880, audioCtx.currentTime + 0.05);
    gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.05);
    osc.start(); osc.stop(audioCtx.currentTime + 0.05);
  } else if (type === 'win') {
    osc.frequency.setValueAtTime(523.25, audioCtx.currentTime);
    osc.frequency.setValueAtTime(659.25, audioCtx.currentTime + 0.1);
    osc.frequency.setValueAtTime(783.99, audioCtx.currentTime + 0.2);
    gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
    osc.start(); osc.stop(audioCtx.currentTime + 0.35);
  }
}

// ============ DOM ELEMENTS ============

const mainBalEl = document.getElementById('main-balance');
const headerGemsEl = document.getElementById('header-gems');
const profGemsEl = document.getElementById('prof-gems');
const energyCurEl = document.getElementById('energy-cur');
const energyBarEl = document.getElementById('energy-bar');
const xpBarEl = document.getElementById('xp-bar');
const levelLabelEl = document.getElementById('level-label');
const xpLabelEl = document.getElementById('xp-label');
const comboBadgeEl = document.getElementById('combo-badge');
const comboCountEl = document.getElementById('combo-count');
const comboMultEl = document.getElementById('combo-mult');
const pulsarCoreEl = document.getElementById('pulsar-core');

// ============ UI UPDATE ============

function updateUI() {
  if (mainBalEl) mainBalEl.innerText = state.balance.toLocaleString();
  if (headerGemsEl) headerGemsEl.innerText = state.gems;
  if (profGemsEl) profGemsEl.innerText = state.gems;
  if (energyCurEl) energyCurEl.innerText = state.energy;
  if (energyBarEl) energyBarEl.style.width = (state.energy / state.maxEnergy * 100) + '%';
  if (xpBarEl) xpBarEl.style.width = (state.xp / state.xpNeed * 100) + '%';
  if (levelLabelEl) levelLabelEl.innerText = `DARAJA ${state.level}/20`;
  if (xpLabelEl) xpLabelEl.innerText = `XP: ${state.xp} / ${state.xpNeed}`;
  document.getElementById('passive-rate').innerText = `+${state.passivePerHour.toLocaleString()}`;
  document.getElementById('my-rank-bal').innerText = state.balance.toLocaleString();
  // Profile
  const profName = document.getElementById('prof-username');
  if (profName) profName.innerText = `@${state.username || 'O\'yinchi'}`;
  const userName = document.getElementById('user-name');
  if (userName) userName.innerText = `@${state.username || 'PulsarPlayer'}`;
}

// ============ INIT — BARCHA MA'LUMOTLARNI SERVERDAN OLISH ============

async function initApp() {
  // 1. Foydalanuvchi ma'lumotlari
  const userData = await apiCall('/api/user', 'POST');
  if (userData.error) {
    console.error('User load error:', userData.error);
    return;
  }

  state.userId = userData.user_id;
  state.username = userData.username;
  state.fullName = userData.full_name;
  state.balance = userData.balance;
  state.gems = userData.quasar_gems;
  state.energy = userData.energy;
  state.maxEnergy = userData.max_energy;
  state.level = userData.level;
  state.xp = userData.xp;
  state.xpNeed = Math.round(100 * Math.pow(1.8, state.level - 1));
  state.passivePerHour = userData.passive_per_hour;
  state.dailyStreak = userData.daily_streak || 0;

  updateUI();

  // 2. Mining binolarini yuklash
  await loadMiningBuildings();

  // 3. Spin holatini tekshirish
  await checkSpinStatus();

  // 4. Chat xabarlarini yuklash
  await loadChatMessages();

  // 5. Referal linkni to'g'rilash
  updateRefLink();

  // 6. Kunlik streak UI
  renderStreak();

  // 7. Spin timer countdown
  startSpinTimer();
}

function updateRefLink() {
  const refLinkEl = document.getElementById('ref-link-val');
  if (refLinkEl && tg) {
    // Bot username from init data or default
    refLinkEl.value = `https://t.me/PulsarTapBot?start=ref_${state.userId}`;
  }
}

// ============ TAP — BACKEND VALIDATION ============

let tapBatchTimer = null;

pulsarCoreEl.addEventListener('pointerdown', (e) => {
  if (state.energy <= 0) return;

  state.energy--;
  state.combo++;

  if (state.combo > 40) state.comboMult = 3.0;
  else if (state.combo > 20) state.comboMult = 2.0;
  else state.comboMult = 1.0;

  const earned = Math.round(1 * state.activeSkin.tapBonus * state.comboMult);
  state.balance += earned;
  state.xp += earned;

  // Level Up Check (client-side preview — server ham tekshiradi)
  if (state.xp >= state.xpNeed && state.level < 20) {
    state.level++;
    state.xp -= state.xpNeed;
    state.xpNeed = Math.round(state.xpNeed * 1.8);
    playSynthSound('win');
    if (tg?.showPopup) tg.showPopup({ title: 'Level Up!', message: `Tabriklaymiz! Siz ${state.level}-darajaga ko'tarildingiz.` });
  }

  // Combo UI
  comboCountEl.innerText = state.combo;
  comboMultEl.innerText = `x${state.comboMult}.0 ${state.comboMult >= 3 ? 'SUPER TAP!' : (state.comboMult >= 2 ? 'TEZKOR TAP' : 'NORMAL')}`;

  playSynthSound('tap');
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light');

  // Floating text
  const floatEl = document.createElement('div');
  floatEl.className = 'float-num';
  floatEl.innerText = `+${earned}`;
  floatEl.style.left = `${e.clientX - 20}px`;
  floatEl.style.top = `${e.clientY - 40}px`;
  document.body.appendChild(floatEl);
  setTimeout(() => floatEl.remove(), 750);

  updateUI();

  // Bufferga qo'shish — keyin serverga yuborish
  state.tapBuffer++;

  // Agar oldin timer bo'lmasa, yangi yaratish
  if (!tapBatchTimer) {
    tapBatchTimer = setTimeout(flushTaps, 500); // 500ms da bir serverga yuboradi
  }
});

async function flushTaps() {
  const taps = state.tapBuffer;
  state.tapBuffer = 0;
  tapBatchTimer = null;

  if (taps <= 0) return;

  const result = await apiCall('/api/tap', 'POST', { taps });
  if (result.error) {
    // Server rad etdi — client state ni qaytarish
    if (result.status === 429) {
      // Anticheat — foydalanuvchi changlatyapti
      console.warn('Rate limit exceeded');
    }
    if (result.balance !== undefined) {
      state.balance = result.balance;
    }
    if (result.energy !== undefined) {
      state.energy = result.energy;
    }
    updateUI();
  } else {
    // Server muvaffaqiyatli — server balance ni tekshirish
    state.balance = result.balance;
    state.energy = result.energy;
    state.xp = result.xp;
    state.level = result.level;
    state.xpNeed = Math.round(100 * Math.pow(1.8, state.level - 1));
    updateUI();
  }
}

// ============ ENERGY REGEN ============

setInterval(async () => {
  if (state.energy < state.maxEnergy) {
    state.energy++;
    updateUI();
    // Serverga xabar berish (ixtiyoriy — server ham regen qiladi)
  }
}, 1800);

// ============ COMBO RESET ============

let comboTimer;
pulsarCoreEl.addEventListener('pointerup', () => {
  clearTimeout(comboTimer);
  comboTimer = setTimeout(() => {
    state.combo = 0;
    state.comboMult = 1.0;
    comboCountEl.innerText = 0;
    comboMultEl.innerText = 'x1.0 NORMAL';
  }, 2500);
});

// ============ TAB SWITCHER ============

function switchTab(tabId) {
  document.querySelectorAll('.screen-tab').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
  const target = document.getElementById(`tab-${tabId}`);
  if (target) target.classList.add('active');
  const btn = Array.from(document.querySelectorAll('.nav-btn')).find(b => b.innerText.toLowerCase().includes(tabId));
  if (btn) btn.classList.add('active');

  // Tab o'zgarganda yangilash
  if (tabId === 'reyting') loadLeaderboard();
  if (tabId === 'profil') updateUI();
}

function switchShopSub(subId) {
  document.querySelectorAll('.shop-content-section').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('#tab-dokan .sub-btn').forEach(el => el.classList.remove('active'));
  document.getElementById(`shop-${subId}`).classList.add('active');
  event.target.classList.add('active');
}

function switchTaskSub(subId) {
  document.querySelectorAll('.task-content-section').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('#tab-vazifalar .sub-btn').forEach(el => el.classList.remove('active'));
  document.getElementById(`task-${subId}`).classList.add('active');
  event.target.classList.add('active');
}

// ============ LEADERBOARD — REAL BACKEND ============

async function loadLeaderboard() {
  const container = document.getElementById('leaderboard-container');
  container.innerHTML = '<div style="text-align:center;color:var(--text-muted);">Yuklanmoqda...</div>';

  const data = await apiCall('/api/leaderboard', 'POST');
  if (data.error) {
    container.innerHTML = '<div style="text-align:center;color:#ff0055;">Xatolik yuz berdi</div>';
    return;
  }

  container.innerHTML = '';
  data.leaders.forEach((l, i) => {
    const rank = i + 1;
    const medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `#${rank}`;
    const name = l.username ? `@${l.username}` : (l.full_name || 'O\'yinchi');
    container.innerHTML += `
      <div class="rank-item">
        <div class="rank-pos">${medal}</div>
        <div style="flex:1"><strong>${name}</strong></div>
        <div style="color:var(--primary-cyan);font-weight:bold;">⚡ ${l.balance.toLocaleString()}</div>
      </div>
    `;
  });

  // Mening o'rnim
  if (data.my_rank > 0) {
    document.querySelector('.my-rank-num').innerText = `#${data.my_rank}`;
  }
}

// ============ SPIN — SERVER-SIDE RNG ============

const spinCanvas = document.getElementById('wheel-canvas');
const spinCtx = spinCanvas.getContext('2d');
const spinPrizes = ["5,000", "15,000", "50,000", "100k", "5 QSR", "ENERGIYA", "+500 XP", "25,000"];
const spinColors = ["#1b1035", "#7928ca", "#00f2fe", "#ff007a", "#ffd700", "#100926", "#4facfe", "#ff0055"];
let isSpinning = false;
let spinCooldownSeconds = 0;

function drawWheel(angleOffset = 0) {
  const num = spinPrizes.length;
  const arc = (2 * Math.PI) / num;
  const cx = spinCanvas.width / 2;
  const cy = spinCanvas.height / 2;
  spinCtx.clearRect(0, 0, spinCanvas.width, spinCanvas.height);

  for (let i = 0; i < num; i++) {
    const angle = angleOffset + i * arc;
    spinCtx.fillStyle = spinColors[i];
    spinCtx.beginPath();
    spinCtx.arc(cx, cy, cx - 10, angle, angle + arc);
    spinCtx.lineTo(cx, cy);
    spinCtx.fill();
    spinCtx.stroke();
    spinCtx.save();
    spinCtx.fillStyle = "#fff";
    spinCtx.font = "bold 11px sans-serif";
    spinCtx.translate(cx + Math.cos(angle + arc / 2) * 90, cy + Math.sin(angle + arc / 2) * 90);
    spinCtx.rotate(angle + arc / 2 + Math.PI / 2);
    spinCtx.fillText(spinPrizes[i], -spinCtx.measureText(spinPrizes[i]).width / 2, 0);
    spinCtx.restore();
  }
}

async function checkSpinStatus() {
  const data = await apiCall('/api/spin_status', 'POST');
  if (!data.error) {
    spinCooldownSeconds = data.wait_seconds || 0;
  }
}

function startSpinTimer() {
  setInterval(() => {
    if (spinCooldownSeconds > 0) {
      spinCooldownSeconds--;
      const h = Math.floor(spinCooldownSeconds / 3600);
      const m = Math.floor((spinCooldownSeconds % 3600) / 60);
      const s = spinCooldownSeconds % 60;
      document.getElementById('spin-timer').innerText = `${h}t ${m}d ${s}s`;
      document.getElementById('spin-cooldown-text').innerHTML = `Keyingi bepul spin: <strong id="spin-timer">${h}t ${m}d ${s}s</strong>`;
    } else {
      document.getElementById('spin-cooldown-text').innerHTML = `<strong id="spin-timer">TAYYOR!</strong>`;
    }
  }, 1000);
}

async function spinWheel() {
  if (isSpinning) return;
  if (spinCooldownSeconds > 0) {
    alert(`Spin hali tayyor emas! Qolgan vaqt: ${Math.ceil(spinCooldownSeconds / 3600)} soat`);
    return;
  }

  isSpinning = true;
  document.getElementById('spin-btn').disabled = true;

  // Serverga so'rov
  const data = await apiCall('/api/spin', 'POST');

  if (data.error) {
    isSpinning = false;
    document.getElementById('spin-btn').disabled = false;
    if (data.wait_seconds) {
      spinCooldownSeconds = data.wait_seconds;
      alert(`Spin limit oshdi! Keyingi spin: ${Math.ceil(data.wait_seconds / 3600)} soatdan keyin`);
    }
    return;
  }

  // Animatsiya — serverdan kelgan natija indeksiga qarab aylantirish
  const prizeIndex = spinPrizes.findIndex(p => p === data.prize_name.replace(',', '').replace(' Quasar', ' QSR').replace(' To\'liq Energiya', ' ENERGIYA').replace('+500 XP', '+500 XP').replace(' PLSR', '').replace('100,000 PLSR', '100k'));
  const arc = (2 * Math.PI) / spinPrizes.length;
  const targetRotation = Math.PI * 6 + (2 * Math.PI - (prizeIndex * arc + arc / 2));

  let currentAngle = 0;
  let speed = 0.3;

  function animate() {
    currentAngle += speed;
    drawWheel(currentAngle);
    if (currentAngle < targetRotation) {
      requestAnimationFrame(animate);
    } else {
      isSpinning = false;
      document.getElementById('spin-btn').disabled = false;

      // Balansni yangilash
      state.balance = data.balance;
      state.gems = data.gems;
      updateUI();

      playSynthSound('win');
      spinCooldownSeconds = 4 * 3600; // 4 soat

      alert(`🎉 Tabriklaymiz! Siz ${data.prize_name} yutib oldingiz!`);
    }
  }
  animate();
}

// ============ MINING — REAL BACKEND ============

let miningBuildings = [];

async function loadMiningBuildings() {
  const data = await apiCall('/api/mining', 'POST', { action: 'get' });
  if (data.buildings) {
    miningBuildings = data.buildings;
    renderMiningCards();
  }
}

function renderMiningCards() {
  const container = document.getElementById('mining-cards-container');
  container.innerHTML = '';
  miningBuildings.forEach(c => {
    container.innerHTML += `
      <div class="card-item">
        <div class="card-top">
          <i class="fa-solid ${c.icon} card-icon"></i>
          <div>
            <div class="card-name">${c.name}</div>
            <div class="card-desc">Lvl ${c.level} • +${(c.rate * c.level).toLocaleString()}/soat</div>
          </div>
        </div>
        <div class="card-price">⚡ ${c.cost.toLocaleString()} $PLSR</div>
        <button class="btn-buy" onclick="buyMining(${c.id})">${c.level > 0 ? 'Yangilash' : 'Sotib olish'}</button>
      </div>
    `;
  });
}

async function buyMining(buildingId) {
  const result = await apiCall('/api/mining', 'POST', { action: 'buy', building_id: buildingId });
  if (result.error) {
    alert(result.error);
    return;
  }
  state.balance = result.balance;
  updateUI();
  playSynthSound('win');
  await loadMiningBuildings();
}

// ============ SKINS (client-side cosmetic) ============

const skins = [
  { id: 'standard', name: 'STANDART', bonus: 1.0, cost: 0, icon: 'fa-circle' },
  { id: 'gold', name: 'Oltin Imperium', bonus: 1.5, cost: 50000, icon: 'fa-crown' },
  { id: 'cyber', name: 'Kiber Platinum', bonus: 2.2, cost: 150000, icon: 'fa-shield-halved' },
  { id: 'nova', name: 'Kamalakli Nova', bonus: 2.0, cost: 100000, icon: 'fa-meteor' }
];

function renderSkins() {
  const container = document.getElementById('skins-cards-container');
  container.innerHTML = '';
  skins.forEach(s => {
    const isActive = state.activeSkin.name === s.name;
    container.innerHTML += `
      <div class="card-item ${isActive ? 'active-skin' : ''}">
        <div class="card-top">
          <i class="fa-solid ${s.icon} card-icon"></i>
          <div>
            <div class="card-name">${s.name}</div>
            <div class="card-desc">Tap kuchi: x${s.bonus}</div>
          </div>
        </div>
        <div class="card-price">${s.cost === 0 ? 'Bepul' : '⚡ ' + s.cost.toLocaleString()}</div>
        <button class="btn-buy" onclick="applySkin('${s.name}', ${s.bonus}, ${s.cost})">${isActive ? 'Tanlangan' : 'Kiyish'}</button>
      </div>
    `;
  });
}

function applySkin(name, bonus, cost) {
  state.activeSkin = { name, tapBonus: bonus };
  document.getElementById('active-skin-name').innerText = name;
  renderSkins();
}

// ============ DAILY STREAK — BACKEND ============

const streakRewards = [1000, 2000, 3000, 4000, 5000, 6000, 10000];

function renderStreak() {
  const container = document.getElementById('streak-grid-container');
  container.innerHTML = '';
  streakRewards.forEach((r, i) => {
    const dayNum = i + 1;
    const isCurrent = dayNum === state.dailyStreak + 1;
    const isClaimed = dayNum <= state.dailyStreak;
    container.innerHTML += `
      <div class="streak-card ${isCurrent ? 'current' : ''} ${isClaimed ? 'claimed' : ''}">
        <div>${dayNum}-kun</div>
        <strong>+${r.toLocaleString()}</strong>
      </div>
    `;
  });
}

async function claimDailyStreak() {
  const result = await apiCall('/api/user', 'POST'); // Refresh user data
  // Actual claim API — user endpoint will return updated streak
  // For now we trigger through the user data refresh
  const userData = await apiCall('/api/user', 'POST');
  if (userData.daily_streak >= 7) {
    state.dailyStreak = 0;
  }
  renderStreak();
  updateUI();
}

// ============ SOCIAL MISSIONS ============

const missions = [
  { id: 1, title: "Pulsar Rasmiy Kanaliga a'zo bo'ling", reward: 5000, done: false },
  { id: 2, title: "Pulsar Community guruhiga qo'shiling", reward: 3000, done: false },
  { id: 3, title: "3 ta do'stingizni taklif qiling", reward: 15000, done: false }
];

function renderMissions() {
  const container = document.getElementById('missions-container');
  container.innerHTML = '';
  missions.forEach(m => {
    container.innerHTML += `
      <div class="card-item" style="flex-direction:row; justify-content:space-between; align-items:center;">
        <div>
          <strong>${m.title}</strong>
          <div style="color:var(--accent-gold); font-size:11px;">+${m.reward.toLocaleString()} $PLSR</div>
        </div>
        <button class="btn-sm" onclick="completeMission(${m.id})">${m.done ? 'Bajarildi ✅' : 'Bajarish'}</button>
      </div>
    `;
  });
}

function completeMission(id) {
  const m = missions.find(x => x.id === id);
  if (!m.done) {
    m.done = true;
    state.balance += m.reward;
    playSynthSound('win');
    renderMissions();
    updateUI();
  }
}

// ============ MODAL HANDLERS ============

function openModal(id) { document.getElementById(id).classList.add('active'); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); }

// P2P Transfer — BACKEND
async function handleP2PTransfer() {
  const target = document.getElementById('p2p-target').value.trim();
  const amount = parseInt(document.getElementById('p2p-amount').value);

  if (!target || isNaN(amount) || amount <= 0) {
    alert("Iltimos, to'g'ri ma'lumot kiriting!");
    return;
  }

  const result = await apiCall('/api/p2p', 'POST', { target, amount });
  if (result.error) {
    alert(result.error);
    return;
  }

  // Balansni yangilash
  const userData = await apiCall('/api/user', 'POST');
  if (!userData.error) {
    state.gems = userData.quasar_gems;
    updateUI();
  }

  closeModal('p2p-modal');
  playSynthSound('win');
  alert(`Muvaffaqiyatli! ${amount} Quasar ${target} ga yuborildi!`);
}

// Exchange — BACKEND
function calcExchange() {
  const val = parseInt(document.getElementById('exchange-input').value) || 0;
  document.getElementById('exchange-out').innerText = Math.floor(val / 1000000);
}

async function handleExchange() {
  const val = parseInt(document.getElementById('exchange-input').value) || 0;
  if (val <= 0) {
    alert("Miqdorni kiriting!");
    return;
  }

  const result = await apiCall('/api/exchange', 'POST', { amount: val });
  if (result.error) {
    alert(result.error);
    return;
  }

  state.balance = result.balance;
  state.gems = result.gems;
  updateUI();
  closeModal('exchange-modal');
  playSynthSound('win');
  alert(`Muvaffaqiyatli! ${result.gems_received} ta Quasar olindi!`);
}

// Promo — BACKEND
async function handlePromo() {
  const code = document.getElementById('promo-input').value.toUpperCase().trim();
  if (!code) {
    alert("Promo-kodni kiriting!");
    return;
  }

  const result = await apiCall('/api/promo', 'POST', { code });
  if (result.error) {
    alert(result.error);
    return;
  }

  state.balance += result.reward;
  updateUI();
  closeModal('promo-modal');
  playSynthSound('win');
  alert(`🎉 Tabriklaymiz! +${result.reward.toLocaleString()} $PLSR bonus berildi!`);
}

// ============ CHAT — REAL BACKEND ============

let chatPollTimer = null;

async function loadChatMessages() {
  const data = await apiCall('/api/chat', 'GET');
  if (data.messages) {
    renderChatMessages(data.messages);
  }
}

function renderChatMessages(messages) {
  const stream = document.getElementById('chat-stream');
  stream.innerHTML = '';
  messages.forEach(m => {
    const isMe = m.username === state.username;
    stream.innerHTML += `
      <div class="chat-bubble" style="${isMe ? 'background:rgba(0, 242, 254, 0.1); border:1px solid rgba(0,242,254,0.2);' : ''}">
        <span class="chat-user">${isMe ? '⚡ Siz' : '👤 @' + m.username}:</span>
        <span class="chat-text">${escapeHtml(m.text)}</span>
      </div>
    `;
  });
  stream.scrollTop = stream.scrollHeight;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

async function sendChatMsg() {
  const input = document.getElementById('chat-msg-input');
  const text = input.value.trim();
  if (!text) return;

  const result = await apiCall('/api/chat/send', 'POST', { text });
  if (result.error) {
    alert(result.error);
    return;
  }

  input.value = '';
  await loadChatMessages();
}

// Chat polling — har 10 sekundda yangilanadi
function startChatPolling() {
  chatPollTimer = setInterval(async () => {
    if (document.getElementById('chat-modal')?.classList.contains('active')) {
      await loadChatMessages();
    }
  }, 10000);
}

// ============ AIRDROP TIMER ============

function startAirdropTimer() {
  // Keyingi oyning 1-chi kuniga qolgan vaqt
  const now = new Date();
  const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  const diff = nextMonth - now;

  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
  const seconds = Math.floor((diff % (1000 * 60)) / 1000);

  document.getElementById('days').innerText = String(days).padStart(2, '0');
  document.getElementById('hours').innerText = String(hours).padStart(2, '0');
  document.getElementById('minutes').innerText = String(minutes).padStart(2, '0');
  document.getElementById('seconds').innerText = String(seconds).padStart(2, '0');
}

setInterval(startAirdropTimer, 1000);

// ============ MINES GAME ============

let minesState = { started: false, grid: [], gemsFound: 0, multiplier: 1.0 };

function openMinesGame() {
  openModal('mines-modal');
  renderMinesGrid();
}

function closeMinesGame() {
  closeModal('mines-modal');
}

function renderMinesGrid() {
  const grid = document.getElementById('mines-grid');
  grid.innerHTML = '';
  for (let i = 0; i < 25; i++) {
    const cell = document.createElement('div');
    cell.className = 'mine-cell';
    cell.dataset.index = i;
    cell.onclick = () => revealCell(i);
    grid.appendChild(cell);
  }
}

function startMinesGame() {
  const bet = parseInt(document.getElementById('mines-bet').value) || 500;
  if (state.balance < bet) {
    alert("Balans yetarli emas!");
    return;
  }

  // Serverga yuborish kerak — hozircha client-side
  state.balance -= bet;
  updateUI();

  // Random bomb va gem joylashuvi
  const bombPositions = new Set();
  while (bombPositions.size < 5) {
    bombPositions.add(Math.floor(Math.random() * 25));
  }

  minesState = { started: true, grid: Array(25).fill('gem'), bombs: bombPositions, gemsFound: 0, multiplier: 1.0, bet };

  document.getElementById('btn-start-mines').style.display = 'none';
  document.getElementById('btn-cashout-mines').style.display = 'block';
  document.getElementById('mines-mult').innerText = 'x1.00';
}

function revealCell(index) {
  if (!minesState.started) return;

  const cell = document.querySelectorAll('.mine-cell')[index];
  if (cell.classList.contains('gem') || cell.classList.contains('bomb')) return;

  if (minesState.bombs.has(index)) {
    // Bomba!
    cell.classList.add('bomb');
    cell.innerHTML = '💣';
    // Hamma bombalarni ko'rsatish
    minesState.bombs.forEach(b => {
      const bombCell = document.querySelectorAll('.mine-cell')[b];
      bombCell.classList.add('bomb');
      bombCell.innerHTML = '💣';
    });
    minesState.started = false;
    document.getElementById('btn-start-mines').style.display = 'block';
    document.getElementById('btn-cashout-mines').style.display = 'none';
    alert("💣 Bombaga tekdingiz! Tikish yandi.");
    playSynthSound('tap');
  } else {
    // Gem topildi
    cell.classList.add('gem');
    cell.innerHTML = '💎';
    minesState.gemsFound++;
    minesState.multiplier = 1 + (minesState.gemsFound * 0.5);
    document.getElementById('mines-mult').innerText = `x${minesState.multiplier.toFixed(2)}`;
  }
}

function cashoutMines() {
  if (!minesState.started || minesState.gemsFound === 0) return;

  const winAmount = Math.round(minesState.bet * minesState.multiplier);
  state.balance += winAmount;
  updateUI();
  playSynthSound('win');

  minesState.started = false;
  document.getElementById('btn-start-mines').style.display = 'block';
  document.getElementById('btn-cashout-mines').style.display = 'none';

  alert(`🎉 Yutuq: ${winAmount.toLocaleString()} $PLSR!`);

  // Bombalarni ko'rsatish
  minesState.bombs.forEach(b => {
    const bombCell = document.querySelectorAll('.mine-cell')[b];
    bombCell.classList.add('bomb');
    bombCell.innerHTML = '💣';
  });
}

// ============ REF & SHARE ============

function copyRefLink() {
  const link = document.getElementById('ref-link-val').value;
  navigator.clipboard.writeText(link);
  alert("Havola nusxalandi!");
}

function shareRefLink() {
  const link = document.getElementById('ref-link-val').value;
  const url = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent("Pulsar o'yinida qatnashib $PLSR tokenlarini to'plang!")}`;
  window.open(url, '_blank');
}

// ============ WALLET CONNECT (TON) ============

function connectWallet() {
  alert("TON Connect hozircha tayyorlanmoqda. Tez orada ishga tushadi!");
}

// ============ INITIAL LOAD ============

window.addEventListener('DOMContentLoaded', async () => {
  await initApp();
  renderSkins();
  renderMissions();
  drawWheel();
  startChatPolling();
  startAirdropTimer();
});
