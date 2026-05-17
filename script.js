/**
 * script.js — NeuralHire AI Interview System v2
 */

'use strict';

/* ══════════════════════════════════════════════════════════════
   CONFIG (Updated for Vercel Deployment!)
══════════════════════════════════════════════════════════════ */
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
  ? 'http://localhost:8000' 
  : '/api';

/* ══════════════════════════════════════════════════════════════
   STATE
══════════════════════════════════════════════════════════════ */
const state = {
  candidateId:    null,
  questionId:     null,
  candidateName:  '',
  role:           '',
  questionNumber: 1,
  totalQuestions: 10,
  questionType:   'text',
  selectedOption: null,
  startTime:      null,
  timerInterval:  null,
  typingInterval: null,
};

/* ══════════════════════════════════════════════════════════════
   DOM REFERENCES
══════════════════════════════════════════════════════════════ */
const $  = id  => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

const screens = {
  welcome:   $('screen-welcome'),
  interview: $('screen-interview'),
  results:   $('screen-results'),
};

const formEl     = $('welcome-form');
const fName      = $('f-name');
const fEmail     = $('f-email');
const fRole      = $('f-role');
const fResume    = $('f-resume');
const btnStart   = $('btn-start');
const formApiErr = $('form-api-error');

const fileDropZone    = $('file-drop-zone');
const fileSelectedPill= $('file-selected-pill');
const filePillName    = $('file-pill-name');
const filePillRemove  = $('file-pill-remove');

const ivName        = $('iv-candidate-name');
const ivRoleBadge   = $('iv-role-badge');
const ivQCounter    = $('iv-q-counter');
const ivProgressBar = $('iv-progress-bar');
const ivTopicTag    = $('iv-topic-tag');
const ivDiffTag     = $('iv-diff-tag');
const ivTypeBadge   = $('iv-type-badge');
const ivQText       = $('iv-question-text');

const answerTextPanel = $('answer-text-panel');
const ivAnswer        = $('iv-answer');
const ivCharCount     = $('iv-char-count');
const btnClear        = $('btn-clear-answer');
const btnSubmit       = $('btn-submit-answer');

const answerMcqPanel  = $('answer-mcq-panel');
const mcqOptionsEl    = $('mcq-options');
const mcqHint         = $('mcq-hint');
const btnSubmitMcq    = $('btn-submit-mcq');

const drawer          = $('feedback-drawer');
const drawerHandle    = $('drawer-handle');
const scoreRingFill   = $('score-ring-fill');
const fbScore         = $('fb-score');
const fbGradeLabel    = $('fb-grade-label');
const fbKwMatched     = $('fb-kw-matched');
const fbKwMissing     = $('fb-kw-missing');
const fbStrengths     = $('fb-strengths');
const fbImprovements  = $('fb-improvements');
const fbIdeal         = $('fb-ideal');
const btnNext         = $('btn-next-question');
const btnNextLabel    = $('btn-next-label');

const resSub           = $('res-subtitle');
const resAvgScore      = $('res-avg-score');
const bigRingFill      = $('big-ring-fill');
const resGradeBadge    = $('res-grade-badge');
const resSummary       = $('res-summary');
const resRoleChip      = $('res-role-chip');
const resQsChip        = $('res-qs-chip');
const resRoleChip2     = $('res-role-chip-2');
const resQsChip2       = $('res-qs-chip-2');
const resBreakdown     = $('res-breakdown');
const btnRestart       = $('btn-restart');

const finalScoreNum    = $('final-score-num');
const finalScoreGrade  = $('final-score-grade');
const finalScoreSummary= $('final-score-summary');
const heroRingFill     = $('hero-ring-fill');

/* ══════════════════════════════════════════════════════════════
   BACKGROUND CANVAS
══════════════════════════════════════════════════════════════ */
(function initCanvas() {
  const canvas = $('bg-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const SPACING = 44;
  let W, H, dots = [];

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
    buildDots();
  }
  function buildDots() {
    dots = [];
    const cols = Math.ceil(W / SPACING) + 1;
    const rows = Math.ceil(H / SPACING) + 1;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        dots.push({ x: c * SPACING, y: r * SPACING, phase: Math.random() * Math.PI * 2, speed: 0.4 + Math.random() * 0.6 });
      }
    }
  }
  function draw(ts) {
    ctx.clearRect(0, 0, W, H);
    const t = ts * 0.001;
    for (const d of dots) {
      const pulse = (Math.sin(t * d.speed + d.phase) + 1) / 2;
      ctx.beginPath();
      ctx.arc(d.x, d.y, 1.2 + pulse * 0.8, 0, Math.PI * 2);
      ctx.fillStyle = pulse > 0.82 ? 'rgba(0,229,255,0.6)' : 'rgba(0,229,255,0.18)';
      ctx.globalAlpha = 0.4 + pulse * 0.5;
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    requestAnimationFrame(draw);
  }
  window.addEventListener('resize', resize);
  resize();
  requestAnimationFrame(draw);
})();

/* ══════════════════════════════════════════════════════════════
   SVG GRADIENTS
══════════════════════════════════════════════════════════════ */
(function injectSvgGradients() {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width',  '0');
  svg.setAttribute('height', '0');
  svg.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden';
  svg.innerHTML = `
    <defs>
      <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%"   stop-color="#3d8bff"/>
        <stop offset="100%" stop-color="#00e5ff"/>
      </linearGradient>
      <linearGradient id="heroRingGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%"   stop-color="#3d8bff"/>
        <stop offset="50%"  stop-color="#00e5ff"/>
        <stop offset="100%" stop-color="#00ffb3"/>
      </linearGradient>
    </defs>`;
  document.body.prepend(svg);
})();

/* ══════════════════════════════════════════════════════════════
   UTILITIES
══════════════════════════════════════════════════════════════ */
function showScreen(name) {
  Object.values(screens).forEach(s => {
    if (s.classList.contains('active')) {
      s.classList.add('exit');
      s.classList.remove('active');
      setTimeout(() => s.classList.remove('exit'), 600);
    }
  });
  setTimeout(() => {
    screens[name].classList.add('active');
    screens[name].scrollTop = 0;
  }, 60);
}

function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  el.getBoundingClientRect();
  el.classList.add('show');
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 500);
  }, 3800);
}

function setLoading(btn, loading) {
  btn.disabled = loading;
  btn.classList.toggle('loading', loading);
}

function animateRing(fillEl, circumference, score) {
  const pct    = Math.max(0, Math.min(score / 10, 1));
  const offset = circumference * (1 - pct);
  requestAnimationFrame(() => { fillEl.style.strokeDashoffset = offset; });
}

function scoreColour(score) {
  if (score >= 7.5) return 'var(--neon-green)';
  if (score >= 5)   return 'var(--neon-amber)';
  return 'var(--neon-red)';
}

function scoreClass(score) {
  if (score >= 7.5) return 'high';
  if (score >= 5)   return 'mid';
  return 'low';
}

function scoreGrade(score) {
  if (score === null || score === undefined) return 'N/A';
  if (score >= 9)   return 'Exceptional (A+)';
  if (score >= 8)   return 'Strong (A)';
  if (score >= 7)   return 'Proficient (B)';
  if (score >= 5.5) return 'Developing (C)';
  if (score >= 4)   return 'Below Expectations (D)';
  return 'Needs Significant Improvement (F)';
}

function scoreGradient(score) {
  if (score >= 7.5) return 'linear-gradient(135deg, #00c87a, #00ffb3)';
  if (score >= 5)   return 'linear-gradient(135deg, #c87900, #ffbe0b)';
  return                    'linear-gradient(135deg, #c0002e, #ff4d6d)';
}

function kwTag(word, type) {
  const span = document.createElement('span');
  span.className   = `kw-tag ${type}`;
  span.textContent = word;
  return span;
}

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,  '&amp;')
    .replace(/</g,  '&lt;')
    .replace(/>/g,  '&gt;')
    .replace(/"/g,  '&quot;')
    .replace(/'/g,  '&#39;');
}

function truncate(str, max) {
  if (!str) return '';
  return str.length > max ? str.slice(0, max) + '…' : str;
}

/* ══════════════════════════════════════════════════════════════
   FILE UPLOAD
══════════════════════════════════════════════════════════════ */
function updateFileUI(file) {
  if (file) {
    fileDropZone.hidden = true;
    fileSelectedPill.hidden = false;
    filePillName.textContent = file.name;
  } else {
    fileDropZone.hidden = false;
    fileSelectedPill.hidden = true;
    filePillName.textContent = '';
    fResume.value = '';
  }
}

fResume.addEventListener('change', () => updateFileUI(fResume.files[0] || null));
filePillRemove.addEventListener('click', () => updateFileUI(null));

fileDropZone.addEventListener('dragover', e => {
  e.preventDefault();
  fileDropZone.classList.add('drag-over');
});
fileDropZone.addEventListener('dragleave', () => fileDropZone.classList.remove('drag-over'));
fileDropZone.addEventListener('drop', e => {
  e.preventDefault();
  fileDropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file && file.type === 'application/pdf') {
    const dt = new DataTransfer();
    dt.items.add(file);
    fResume.files = dt.files;
    updateFileUI(file);
  } else if (file) {
    toast('Only PDF files are accepted.', 'error');
  }
});

/* ══════════════════════════════════════════════════════════════
   TYPEWRITER EFFECT
══════════════════════════════════════════════════════════════ */
function typeQuestion(text) {
  if (state.typingInterval) {
    clearTimeout(state.typingInterval);
    state.typingInterval = null;
  }
  ivQText.textContent = '';
  ivQText.classList.add('typing');
  const chars = [...text];
  let i = 0;
  function charDelay(ch) {
    if ('.!?'.includes(ch)) return 110;
    if (',;:'.includes(ch)) return 55;
    return 16;
  }
  function typeNext() {
    if (i >= chars.length) {
      clearTimeout(state.typingInterval);
      state.typingInterval = null;
      ivQText.classList.remove('typing');
      return;
    }
    ivQText.textContent += chars[i];
    const delay = charDelay(chars[i]);
    i++;
    state.typingInterval = setTimeout(typeNext, delay);
  }
  state.typingInterval = setTimeout(typeNext, 40);
}

/* ══════════════════════════════════════════════════════════════
   ELAPSED TIMER
══════════════════════════════════════════════════════════════ */
function startTimer() {
  stopTimer();
  let timerEl = $('iv-elapsed-timer');
  if (!timerEl) {
    timerEl = document.createElement('span');
    timerEl.id = 'iv-elapsed-timer';
    timerEl.className = 'char-counter';
    timerEl.style.cssText = 'margin-left:auto;opacity:0.6;font-size:0.7rem';
    const footer = document.querySelector('.answer-footer');
    if (footer) footer.prepend(timerEl);
  }
  timerEl.textContent = '0:00';
  state.timerInterval = setInterval(() => {
    if (!state.startTime) return;
    const secs = Math.floor((Date.now() - state.startTime) / 1000);
    const mm = Math.floor(secs / 60);
    const ss = String(secs % 60).padStart(2, '0');
    timerEl.textContent = `${mm}:${ss}`;
  }, 1000);
}
function stopTimer() {
  if (state.timerInterval) {
    clearInterval(state.timerInterval);
    state.timerInterval = null;
  }
}

/* ══════════════════════════════════════════════════════════════
   API HELPERS
══════════════════════════════════════════════════════════════ */
async function apiPost(path, body, isFormData = false) {
  const opts = { method: 'POST' };
  if (isFormData) {
    opts.body = body;
  } else {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  }
  const res  = await fetch(`${API_BASE}${path}`, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail || data?.message || `HTTP ${res.status}`);
  return data;
}

async function apiGet(path) {
  const res  = await fetch(`${API_BASE}${path}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail || data?.message || `HTTP ${res.status}`);
  return data;
}

/* ══════════════════════════════════════════════════════════════
   SCREEN 1 — REGISTER & START
══════════════════════════════════════════════════════════════ */
formEl.addEventListener('submit', async e => {
  e.preventDefault();
  $$('.field-error').forEach(el => (el.textContent = ''));
  formApiErr.textContent = '';
  
  if (!fName.value.trim() || !fEmail.value.trim() || !fRole.value) return;

  setLoading(btnStart, true);

  try {
    const fd = new FormData();
    fd.append('name',  fName.value.trim());
    fd.append('email', fEmail.value.trim().toLowerCase());
    fd.append('role',  fRole.value);
    if (fResume.files[0]) fd.append('resume', fResume.files[0]);

    const data = await apiPost('/start_interview', fd, true);

    state.candidateId   = data.candidate_id;
    state.candidateName = fName.value.trim();
    state.role          = fRole.value;

    ivName.textContent      = state.candidateName;
    ivRoleBadge.textContent = state.role;
    
    renderQuestion(data.first_question);
    showScreen('interview');

  } catch (err) {
    formApiErr.textContent = err.message;
    toast('Could not start interview — is the backend running?', 'error');
  } finally {
    setLoading(btnStart, false);
  }
});

/* ══════════════════════════════════════════════════════════════
   RENDER QUESTION
══════════════════════════════════════════════════════════════ */
function renderQuestion(q) {
  state.questionId     = q.question_id;
  state.questionNumber = q.question_number;
  state.totalQuestions = q.total_questions;
  state.questionType   = q.question_type || 'text';
  state.selectedOption = null;
  state.startTime      = Date.now();

  ivTopicTag.textContent = q.topic;
  ivDiffTag.textContent  = q.difficulty;
  ivTypeBadge.hidden = state.questionType !== 'mcq';

  ivQCounter.textContent = `Q${q.question_number} / ${q.total_questions}`;
  ivProgressBar.style.width = `${((q.question_number - 1) / q.total_questions) * 100}%`;

  typeQuestion(q.body);

  if (state.questionType === 'mcq') {
    answerTextPanel.hidden = true;
    answerMcqPanel.hidden  = false;
    renderMcqOptions(q.options || []);
  } else {
    answerTextPanel.hidden = false;
    answerMcqPanel.hidden  = true;
    ivAnswer.value          = '';
    ivCharCount.textContent = '0';
    btnSubmit.disabled      = false;
    btnSubmit.classList.remove('loading');
    setTimeout(() => ivAnswer.focus(), 350);
  }

  drawer.classList.remove('open');
  startTimer();
}

/* ══════════════════════════════════════════════════════════════
   MCQ OPTIONS
══════════════════════════════════════════════════════════════ */
const LETTERS = ['A', 'B', 'C', 'D'];

function renderMcqOptions(options) {
  mcqOptionsEl.innerHTML = '';
  state.selectedOption = null;
  btnSubmitMcq.disabled = true;
  mcqHint.textContent = 'Select an option to enable submission';

  options.forEach((text, idx) => {
    const card = document.createElement('div');
    card.className = 'mcq-option';
    card.innerHTML = `
      <input type="radio" name="mcq-answer" value="${idx}" id="mcq-opt-${idx}" />
      <span class="mcq-letter">${LETTERS[idx]}</span>
      <span class="mcq-text">${escHtml(text)}</span>
      <span class="mcq-check" aria-hidden="true">✓</span>
    `;
    card.addEventListener('click', () => {
      $$('.mcq-option').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      card.querySelector('input').checked = true;
      state.selectedOption = idx;
      btnSubmitMcq.disabled = false;
      mcqHint.textContent = `Option ${LETTERS[idx]} selected — click Confirm to submit`;
    });
    mcqOptionsEl.appendChild(card);
  });
}

ivAnswer.addEventListener('input', () => { ivCharCount.textContent = ivAnswer.value.length; });
btnClear.addEventListener('click', () => { ivAnswer.value = ''; ivCharCount.textContent = '0'; ivAnswer.focus(); });

/* ══════════════════════════════════════════════════════════════
   SUBMIT ANSWER
══════════════════════════════════════════════════════════════ */
btnSubmit.addEventListener('click', async () => {
  const answerText = ivAnswer.value.trim();
  if (!answerText) return toast('Please write your answer.', 'error');
  
  const duration = state.startTime ? Math.round((Date.now() - state.startTime) / 1000) : 0;
  stopTimer(); setLoading(btnSubmit, true);

  try {
    const data = await apiPost('/submit_answer', { candidate_id: state.candidateId, question_id: state.questionId, answer: answerText, duration_sec: duration });
    renderFeedback(data.feedback); configureNextButton(data);
    ivProgressBar.style.width = `${(state.questionNumber / state.totalQuestions) * 100}%`;
    setTimeout(() => drawer.classList.add('open'), 120);
    btnSubmit.disabled = true;
  } catch (err) { toast(err.message, 'error'); setLoading(btnSubmit, false); }
});

btnSubmitMcq.addEventListener('click', async () => {
  if (state.selectedOption === null) return;
  const duration = state.startTime ? Math.round((Date.now() - state.startTime) / 1000) : 0;
  stopTimer(); setLoading(btnSubmitMcq, true);

  try {
    const data = await apiPost('/submit_answer', { candidate_id: state.candidateId, question_id: state.questionId, answer: LETTERS[state.selectedOption], chosen_option: state.selectedOption, duration_sec: duration });
    
    const isCorrect  = data.feedback.score >= 9.9;
    const correctIdx = isCorrect ? state.selectedOption : (data.feedback.ideal_answer_summary || '').match(/option\s+([A-D])/i) ? LETTERS.indexOf((data.feedback.ideal_answer_summary || '').match(/option\s+([A-D])/i)[1].toUpperCase()) : -1;
    
    $$('.mcq-option').forEach((card, i) => {
      card.classList.remove('selected');
      if (i === correctIdx) { card.classList.add('correct'); card.querySelector('.mcq-check').textContent = '✓'; }
      else if (i === state.selectedOption && state.selectedOption !== correctIdx) { card.classList.add('incorrect'); card.querySelector('.mcq-check').textContent = '✕'; }
      else { card.classList.add('disabled'); }
    });

    renderFeedback(data.feedback); configureNextButton(data);
    ivProgressBar.style.width = `${(state.questionNumber / state.totalQuestions) * 100}%`;
    setTimeout(() => drawer.classList.add('open'), 120);
    btnSubmitMcq.disabled = true;
  } catch (err) { toast(err.message, 'error'); setLoading(btnSubmitMcq, false); }
});

function configureNextButton(data) {
  if (data.interview_complete) {
    btnNextLabel.textContent = 'View My Results  ✦';
    btnNext._nextQ = null; btnNext._done  = true;
  } else {
    btnNextLabel.textContent = `Next Question (${data.next_question.question_number}/${data.next_question.total_questions}) · ${data.next_question.question_type === 'mcq' ? 'MCQ' : 'Open-ended'}`;
    btnNext._nextQ = data.next_question; btnNext._done  = false;
  }
}

function renderFeedback(fb) {
  const score = fb.score ?? 0;
  fbScore.textContent = score.toFixed(1);
  fbScore.style.color = scoreColour(score);
  fbGradeLabel.textContent = scoreGrade(score);
  scoreRingFill.style.stroke = scoreColour(score);
  animateRing(scoreRingFill, 213.628, score);
  
  fbKwMatched.innerHTML = ''; (fb.keywords_matched||[]).forEach(w => fbKwMatched.appendChild(kwTag(w, 'matched')));
  fbKwMissing.innerHTML = ''; (fb.keywords_missing||[]).forEach(w => fbKwMissing.appendChild(kwTag(w, 'missing')));
  fbStrengths.innerHTML = (fb.strengths||[]).length ? fb.strengths.map(s => `<li>${escHtml(s)}</li>`).join('') : '<li>—</li>';
  fbImprovements.innerHTML = (fb.improvements||[]).length ? fb.improvements.map(s => `<li>${escHtml(s)}</li>`).join('') : '<li>—</li>';
  fbIdeal.textContent = fb.ideal_answer_summary || 'No summary provided.';
}

btnNext.addEventListener('click', async () => {
  if (btnNext._done) {
    drawer.classList.remove('open');
    setTimeout(async () => {
      const data = await apiGet(`/results/${state.candidateId}`);
      renderResults(data); showScreen('results');
    }, 400);
  } else {
    drawer.classList.remove('open');
    setTimeout(() => renderQuestion(btnNext._nextQ), 380);
  }
});

drawerHandle.addEventListener('click', () => drawer.classList.toggle('open'));

/* ══════════════════════════════════════════════════════════════
   SCREEN 3 — RESULTS
══════════════════════════════════════════════════════════════ */
function renderResults(data) {
  const avg = data.average_score;
  resSub.textContent = `${escHtml(data.candidate_name)} · ${escHtml(data.candidate_email)}`;

  if (avg !== null) {
    finalScoreNum.textContent = avg.toFixed(1);
    finalScoreNum.style.color = scoreColour(avg);
    finalScoreGrade.textContent = data.grade;
    finalScoreGrade.style.background = scoreGradient(avg);
    finalScoreSummary.textContent = data.summary;
    heroRingFill.style.stroke = 'url(#heroRingGrad)';
    animateRing(heroRingFill, 942.48, avg);
    
    const count = 18, container = $('hero-particles');
    container.innerHTML = '';
    for (let i = 0; i < count; i++) {
      const dot = document.createElement('div');
      dot.className = 'hero-particle';
      dot.style.cssText = `left: ${Math.random() * 100}%; bottom: ${Math.random() * 30}%; background: ${scoreColour(avg)}; width: ${2 + Math.random() * 3}px; height: ${2 + Math.random() * 3}px; animation-duration: ${3 + Math.random() * 5}s; animation-delay: ${Math.random() * 4}s;`;
      container.appendChild(dot);
    }
  }

  resRoleChip.textContent = data.role; resQsChip.textContent = `${data.answers_submitted} / ${data.total_questions} answered`;
  
  resAvgScore.textContent = avg !== null ? avg.toFixed(1) : '—'; resGradeBadge.textContent = data.grade; resSummary.textContent = data.summary;
  resRoleChip2.textContent = data.role; resQsChip2.textContent = `${data.answers_submitted} / ${data.total_questions} answered`;
  if (avg !== null) { bigRingFill.style.stroke = scoreColour(avg); animateRing(bigRingFill, 427.256, avg); resAvgScore.style.color = scoreColour(avg); resGradeBadge.style.background = scoreGradient(avg); resGradeBadge.style.color = '#08090a'; }

  // ── FIX: Cleaned up HTML Layout for Breakdown Cards ──
  resBreakdown.innerHTML = '';
  (data.answers || []).forEach((item, i) => {
    const card = document.createElement('div');
    card.className = 'breakdown-item';
    card.style.animationDelay = `${i * 0.09}s`;

    card.innerHTML = `
      <div class="bi-meta">
        <span class="bi-topic">${escHtml(item.topic)}</span>
        <span class="bi-diff">${escHtml(item.difficulty)}</span>
        ${item.question_type === 'mcq' ? '<span class="bi-type-tag">◈ MCQ</span>' : ''}
      </div>
      <div class="bi-body" style="display:flex; flex-direction:column; gap:16px;">
        <div>
          <span style="font-size:0.68rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:1.5px; display:block; margin-bottom:6px;">Question</span>
          <p class="bi-q" style="font-size:0.9rem; color:var(--text-primary); line-height:1.5; margin:0;">${escHtml(item.question)}</p>
        </div>
        <div>
          <span style="font-size:0.68rem; color:var(--text-muted); text-transform:uppercase; letter-spacing:1.5px; display:block; margin-bottom:6px;">Your Answer</span>
          <p class="bi-ans" style="font-size:0.85rem; color:var(--text-secondary); line-height:1.55; padding-left:12px; border-left:2px solid var(--border); font-style:italic; margin:0;">${escHtml(truncate(item.answer, 220))}</p>
        </div>
        ${item.ideal_answer
          ? `<div style="padding:14px 18px; background:rgba(61,139,255,0.06); border-radius:8px; border-left:3px solid var(--neon-blue);">
              <span style="font-size:0.65rem; color:var(--neon-blue); text-transform:uppercase; letter-spacing:1px; display:block; margin-bottom:6px; font-weight:bold;">Ideal Answer</span>
              <p style="font-size:0.85rem; color:var(--text-primary); line-height:1.5; margin:0;">${escHtml(truncate(item.ideal_answer, 200))}</p>
            </div>`
          : ''}
      </div>
      <div class="bi-score-badge ${scoreClass(item.score ?? 0)}" style="align-self: flex-start;">${item.score !== null ? item.score.toFixed(1) : '—'}</div>
    `;
    resBreakdown.appendChild(card);
  });
}

btnRestart.addEventListener('click', () => location.reload());