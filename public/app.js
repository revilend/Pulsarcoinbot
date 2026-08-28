// Pulsar Mini App State
const state = {
  balance: 500,
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
  dailyStreak: 1,
  lastDailyClaim: 0,
  canSpin: true
};

const tg = window.Telegram?.WebApp;
if (tg) {
  tg.expand();
  tg.enableClosingConfirmation();
}

// Sound Synthesis (Web Audio API)
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
function playSynthSound(type) {
  if (audioCtx.state === 'suspended') { audioCtx.resume(); }
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.connect(gain);
  gain.connect(audioCtx.destination);

  if (type === 'tap') {
    osc.frequency.setValueAtTime(440, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(880, audioCtx.currentTime + 0.05);
    gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.05);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.05);
  } else if (type === 'win') {
    osc.frequency.setValueAtTime(523.25, audioCtx.currentTime);
    osc.frequency.setValueAtTime(659.25, audioCtx.currentTime + 0.1);
    osc.frequency.setValueAtTime(783.99, audioCtx.currentTime + 0.2);
    gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.35);
  }
}

// DOM Elements
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
const tapZoneEl = document.getElementById('tap-zone');

// Update UI
function updateUI() {
  mainBalEl.innerText = state.balance.toLocaleString();
  headerGemsEl.innerText = state.gems;
  profGemsEl.innerText = state.gems;
  energyCurEl.innerText = state.energy;
  energyBarEl.style.width = (state.energy / state.maxEnergy * 100) + '%';
  xpBarEl.style.width = (state.xp / state.xpNeed * 100) + '%';
  levelLabelEl.innerText = `DARAJA ${state.level}/20`;
  xpLabelEl.innerText = `XP: ${state.xp} / ${state.xpNeed}`;
  document.getElementById('passive-rate').innerText = `+${state.passivePerHour.toLocaleString()}`;
  document.getElementById('my-rank-bal').innerText = state.balance.toLocaleString();
}

// Tap Event
pulsarCoreEl.addEventListener('pointerdown', (e) => {
  if (state.energy <= 0) return;

  state.energy--;
  state.combo++;
  
  if (state.combo > 40) {
    state.comboMult = 3.0;
  } else if (state.combo > 20) {
    state.comboMult = 2.0;
  } else {
    state.comboMult = 1.0;
  }

  const earned = Math.round(1 * state.activeSkin.tapBonus * state.comboMult);
  state.balance += earned;
  state.xp += earned;

  // Level Up Check
  if (state.xp >= state.xpNeed && state.level < 20) {
    state.level++;
    state.xp -= state.xpNeed;
    state.xpNeed = Math.round(state.xpNeed * 1.8);
    playSynthSound('win');
    if (tg?.showPopup) tg.showPopup({ title: 'Level Up!', message: `Tabriklaymiz! Siz ${state.level}-darajaga ko'tarildingiz.` });
  }

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
});

// Energy Regen
setInterval(() => {
  if (state.energy < state.maxEnergy) {
    state.energy++;
    updateUI();
  }
}, 1800);

// Passive Income per second
setInterval(() => {
  if (state.passivePerHour > 0) {
    const incPerSec = Math.max(1, Math.round(state.passivePerHour / 3600));
    state.balance += incPerSec;
    updateUI();
  }
}, 1000);

// Combo Reset if inactive for 3 sec
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

// Tab Switcher
function switchTab(tabId) {
  document.querySelectorAll('.screen-tab').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
  
  const target = document.getElementById(`tab-${tabId}`);
  if (target) target.classList.add('active');

  const btn = Array.from(document.querySelectorAll('.nav-btn')).find(b => b.innerText.toLowerCase().includes(tabId));
  if (btn) btn.classList.add('active');
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

// Mining Generators Data
const miningCards = [
  { id: 1, name: 'Kvant Kollektori', cost: 1000, rate: 250, icon: 'fa-microchip', level: 0 },
  { id: 2, name: 'Stellar Reaktor', cost: 5000, rate: 1200, icon: 'fa-atom', level: 0 },
  { id: 3, name: 'Kosmik Turbina', cost: 20000, rate: 5000, icon: 'fa-fan', level: 0 },
  { id: 4, name: 'Dyson Radiatori', cost: 100000, rate: 25000, icon: 'fa-sun', level: 0 }
];

function renderMiningCards() {
  const container = document.getElementById('mining-cards-container');
  container.innerHTML = '';
  miningCards.forEach(c => {
    container.innerHTML += `
      <div class="card-item">
        <div class="card-top">
          <i class="fa-solid ${c.icon} card-icon"></i>
          <div>
            <div class="card-name">${c.name}</div>
            <div class="card-desc">Lvl ${c.level} • +${c.rate}/soat</div>
          </div>
        </div>
        <div class="card-price">⚡ ${c.cost.toLocaleString()} PLSR</div>
        <button class="btn-buy" onclick="buyMining(${c.id})">Sotib olish</button>
      </div>
    `;
  });
}

function buyMining(id) {
  const item = miningCards.find(c => c.id === id);
  if (state.balance >= item.cost) {
    state.balance -= item.cost;
    item.level++;
    state.passivePerHour += item.rate;
    item.cost = Math.round(item.cost * 1.5);
    playSynthSound('win');
    renderMiningCards();
    updateUI();
  } else {
    alert("Balans yetarli emas!");
  }
}

// Skins Data
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

// Daily Streak
const streakRewards = [1000, 2000, 3000, 4000, 5000, 6000, 10000];
function renderStreak() {
  const container = document.getElementById('streak-grid-container');
  container.innerHTML = '';
  streakRewards.forEach((r, i) => {
    const isCurrent = (i + 1) === state.dailyStreak;
    const isClaimed = (i + 1) < state.dailyStreak;
    container.innerHTML += `
      <div class="streak-card ${isCurrent ? 'current' : ''} ${isClaimed ? 'claimed' : ''}">
        <div>${i + 1}-kun</div>
        <strong>+${r.toLocaleString()}</strong>
      </div>
    `;
  });
}

function claimDailyStreak() {
  const reward = streakRewards[state.dailyStreak - 1] || 1000;
  state.balance += reward;
  state.dailyStreak = state.dailyStreak >= 7 ? 1 : state.dailyStreak + 1;
  playSynthSound('win');
  renderStreak();
  updateUI();
  document.getElementById('btn-claim-streak').disabled = true;
  document.getElementById('btn-claim-streak').innerText = 'BUGUN OLINDI ✅';
}

// Social Missions
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

// Spin Wheel Canvas Implementation
const canvas = document.getElementById('wheel-canvas');
const ctx = canvas.getContext('2d');
const prizes = ["5,000", "15,000", "50,000", "JACKPOT 100k", "5 QUASAR", "FULL ENERGY", "+500 XP", "25,000"];
const colors = ["#1b1035", "#7928ca", "#00f2fe", "#ff007a", "#ffd700", "#100926", "#4facfe", "#ff0055"];

function drawWheel(angleOffset = 0) {
  const num = prizes.length;
  const arc = (2 * Math.PI) / num;
  const cx = canvas.width / 2;
  const cy = canvas.height / 2;

  for (let i = 0; i < num; i++) {
    const angle = angleOffset + i * arc;
    ctx.fillStyle = colors[i];
    ctx.beginPath();
    ctx.arc(cx, cy, cx - 10, angle, angle + arc);
    ctx.lineTo(cx, cy);
    ctx.fill();
    ctx.stroke();

    ctx.save();
    ctx.fillStyle = "#fff";
    ctx.font = "bold 11px sans-serif";
    ctx.translate(cx + Math.cos(angle + arc / 2) * 90, cy + Math.sin(angle + arc / 2) * 90);
    ctx.rotate(angle + arc / 2 + Math.PI / 2);
    ctx.fillText(prizes[i], -ctx.measureText(prizes[i]).width / 2, 0);
    ctx.restore();
  }
}

let isSpinning = false;
function spinWheel() {
  if (isSpinning) return;
  isSpinning = true;

  let currentAngle = 0;
  const targetRotation = Math.PI * 8 + Math.random() * Math.PI * 2;
  let speed = 0.3;

  function animate() {
    currentAngle += speed;
    drawWheel(currentAngle);

    if (currentAngle < targetRotation) {
      requestAnimationFrame(animate);
    } else {
      isSpinning = false;
      state.balance += 15000;
      playSynthSound('win');
      updateUI();
      alert("🎉 Tabriklaymiz! Siz 15,000 $PLSR yutib oldingiz!");
    }
  }
  animate();
}

// Leaderboard Mock
function renderLeaderboard() {
  const container = document.getElementById('leaderboard-container');
  const leaders = [
    { rank: 1, name: 'Dasturchi 👑', bal: '9,486,863' },
    { rank: 2, name: 'Abdulloh Najimov', bal: '2,748,337' },
    { rank: 3, name: 'Umidjon Qosimov', bal: '1,857,514' },
    { rank: 4, name: 'Boburbek Nomonjonov', bal: '357,393' },
    { rank: 5, name: 'Ixlosbek Bozorboev', bal: '326,103' }
  ];

  container.innerHTML = '';
  leaders.forEach(l => {
    container.innerHTML += `
      <div class="rank-item">
        <div class="rank-pos">${l.rank === 1 ? '🥇' : (l.rank === 2 ? '🥈' : (l.rank === 3 ? '🥉' : '#' + l.rank))}</div>
        <div style="flex:1">
          <strong>${l.name}</strong>
        </div>
        <div style="color:var(--primary-cyan); font-weight:bold;">⚡ ${l.bal}</div>
      </div>
    `;
  });
}

// Modal Handlers
function openModal(id) { document.getElementById(id).classList.add('active'); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); }

function handleP2PTransfer() {
  const target = document.getElementById('p2p-target').value;
  const amount = parseInt(document.getElementById('p2p-amount').value);
  if (!target || isNaN(amount) || amount <= 0) {
    alert("Iltimos, to'g'ri ma'lumot kiriting!");
    return;
  }
  if (state.gems >= amount) {
    state.gems -= amount;
    updateUI();
    closeModal('p2p-modal');
    alert(`Muvaffaqiyatli: ${amount} Quasar ${target} ga yuborildi!`);
  } else {
    alert("Quasar kristallari yetarli emas!");
  }
}

function calcExchange() {
  const val = parseInt(document.getElementById('exchange-input').value) || 0;
  document.getElementById('exchange-out').innerText = Math.floor(val / 1000000);
}

function handleExchange() {
  const val = parseInt(document.getElementById('exchange-input').value) || 0;
  if (val >= 1000000 && state.balance >= val) {
    const gems = Math.floor(val / 1000000);
    state.balance -= (gems * 1000000);
    state.gems += gems;
    updateUI();
    closeModal('exchange-modal');
    playSynthSound('win');
    alert(`Muvaffaqiyatli: ${gems} ta Quasar olindi!`);
  } else {
    alert("Yetarli $PLSR tangalari mavjud emas (Kamida 1,000,000 kerak)!");
  }
}

function handlePromo() {
  const code = document.getElementById('promo-input').value.toUpperCase().trim();
  if (code === 'PULSAR2026') {
    state.balance += 50000;
    updateUI();
    closeModal('promo-modal');
    playSynthSound('win');
    alert("🎉 Tabriklaymiz! +50,000 $PLSR bonus berildi!");
  } else {
    alert("Noto'g'ri yoki muddati o'tgan promo-kod!");
  }
}

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

function sendChatMsg() {
  const input = document.getElementById('chat-msg-input');
  const text = input.value.trim();
  if (!text) return;

  const stream = document.getElementById('chat-stream');
  stream.innerHTML += `
    <div class="chat-bubble" style="background:rgba(0, 242, 254, 0.1); border:1px solid rgba(0,242,254,0.2);">
      <span class="chat-user">⚡ Siz:</span>
      <span class="chat-text">${text}</span>
    </div>
  `;
  input.value = '';
  stream.scrollTop = stream.scrollHeight;
}

// Initial Calls
window.addEventListener('DOMContentLoaded', () => {
  updateUI();
  renderMiningCards();
  renderSkins();
  renderStreak();
  renderMissions();
  renderLeaderboard();
  drawWheel();
});
