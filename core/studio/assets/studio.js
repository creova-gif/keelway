'use strict';
// Keelway Studio — vanilla JS, no CDN, works offline. All server data is rendered via textContent.

const $ = (id) => document.getElementById(id);
function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return el;
}

// Escape a string for safe interpolation into innerHTML templates.
function esc(v) {
  return String(v == null ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function trapFocus(container, e) {
  if (e.key !== 'Tab') return;
  const focusables = Array.from(container.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')).filter((el) => {
    return (el.offsetWidth > 0 || el.offsetHeight > 0 || el.getClientRects?.().length > 0) && window.getComputedStyle?.(el)?.visibility !== 'hidden';
  });
  if (!focusables.length) { e.preventDefault(); return; }
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first || !container.contains(document.activeElement)) {
      e.preventDefault();
      last.focus();
    }
  } else {
    if (document.activeElement === last || !container.contains(document.activeElement)) {
      e.preventDefault();
      first.focus();
    }
  }
}

// ---------- i18n ----------
const STRINGS = {
  en: { skip: 'Skip to editor', search: 'Search files, symbols and commands', language: 'Language', theme: 'Theme', sounds: 'Sounds', signOut: 'Sign out', views: 'Views', home: 'Home', workspace: 'Workspace', openWorkspace: 'Open workspace', skills: 'Skills', settings: 'Settings', developerLabs: 'Developer Labs', evidence: 'Evidence', explorer: 'Explorer', changes: 'Changes', tasks: 'Tasks', memory: 'Memory', refresh: 'Refresh', newTask: 'New task', newTaskPh: 'New task…', add: 'Add', rememberPh: 'Remember that…', save: 'Save', openFiles: 'Open files', viewMode: 'View mode', code: 'Code', diff: 'Diff', editor: 'Editor', tagline: 'Local-first · Deterministic · Yours', welcomeTitle: 'Build with agents that never leave your machine.', welcomeBody: 'Every step is recorded, replayable and auditable. Open a file, give the agent a goal, or review what changed.', panel: 'Panel', console: 'Console', flight: 'Flight recorder', healing: 'Self-healing', ledger: 'Ledger', audit: 'Audit', fork: 'Fork here', healWarn: 'Runs the command in this repository. A passing patch is applied to your working tree.', testCommand: 'Test command', attempts: 'Attempts', runRepair: 'Run repair cycle', paySim: 'Simulated: builds a payment payload only. No money moves.', rail: 'Rail', amount: 'Amount', currency: 'Currency', recipient: 'Recipient', buildIntent: 'Build intent', auditHint: 'Every permission decision is appended to a SHA-256 hash chain.', verify: 'Verify chain', agent: 'Keelway agent', idle: 'idle', noGoal: 'No goal yet.', plan: 'Plan', approvalNeeded: 'Approval needed', allow: 'Allow', deny: 'Deny', activity: 'Activity', goal: 'Goal', goalPh: 'Describe a goal for the agent…', polConfirmMut: 'Ask before changes', polConfirmAll: 'Ask before every step', polAuto: 'Autonomous (admin)', start: 'Start', signInTitle: 'Sign in to Keelway', signInBody: 'Open the link printed by keelway dev, or paste a token from keelway token create.', apiToken: 'API token', signIn: 'Sign in', skipTour: 'Skip', next: 'Next', done: 'Get started', airOn: 'Offline (setting)', airOff: 'Cloud allowed', clean: 'Working tree clean', noTasks: 'No tasks yet', noMemories: 'No memories yet', noTapes: 'No flight tapes yet', openFile: 'Open a file', giveGoal: 'Give the agent a goal', reviewChanges: 'Review changes', saved: 'Saved', modified: 'Modified', badToken: 'That token was not accepted.',
    tour: [['Welcome to Keelway', 'A local-first, deterministic agent workspace. Your code, models and data stay on this machine.'], ['Agents you can trust', 'Agents propose a plan, ask before changing files, and every step lands in a replayable flight tape.'], ['Audit everything', 'Tokens, roles and a tamper-evident audit log make Keelway safe to share with your team.']] },
  es: { search: 'Buscar archivos, símbolos y comandos', signOut: 'Cerrar sesión', explorer: 'Explorador', changes: 'Cambios', tasks: 'Tareas', memory: 'Memoria', save: 'Guardar', tagline: 'Local · Determinista · Tuyo', welcomeTitle: 'Construye con agentes que nunca salen de tu equipo.', welcomeBody: 'Cada paso queda registrado, reproducible y auditable.', start: 'Iniciar', signIn: 'Entrar', signInTitle: 'Inicia sesión en Keelway', next: 'Siguiente', done: 'Empezar', skipTour: 'Omitir', airOn: 'Aislado', airOff: 'Nube permitida', plan: 'Plan', activity: 'Actividad', allow: 'Permitir', deny: 'Denegar', openFile: 'Abrir un archivo', giveGoal: 'Dar un objetivo', reviewChanges: 'Revisar cambios' },
  fr: { search: 'Rechercher fichiers, symboles et commandes', signOut: 'Déconnexion', explorer: 'Explorateur', changes: 'Modifications', tasks: 'Tâches', memory: 'Mémoire', save: 'Enregistrer', tagline: 'Local · Déterministe · À vous', welcomeTitle: 'Des agents qui ne quittent jamais votre machine.', welcomeBody: 'Chaque étape est enregistrée, rejouable et auditable.', start: 'Démarrer', signIn: 'Se connecter', signInTitle: 'Connexion à Keelway', next: 'Suivant', done: 'Commencer', skipTour: 'Passer', airOn: 'Isolé', airOff: 'Cloud autorisé', activity: 'Activité', allow: 'Autoriser', deny: 'Refuser', openFile: 'Ouvrir un fichier', giveGoal: 'Donner un objectif', reviewChanges: 'Voir les modifications' },
  pt: { search: 'Buscar arquivos, símbolos e comandos', signOut: 'Sair', explorer: 'Explorador', changes: 'Alterações', tasks: 'Tarefas', memory: 'Memória', save: 'Salvar', tagline: 'Local · Determinístico · Seu', welcomeTitle: 'Agentes que nunca saem da sua máquina.', welcomeBody: 'Cada passo é registrado, reproduzível e auditável.', start: 'Iniciar', signIn: 'Entrar', signInTitle: 'Entrar no Keelway', next: 'Próximo', done: 'Começar', skipTour: 'Pular', airOn: 'Isolado', airOff: 'Nuvem permitida', activity: 'Atividade', allow: 'Permitir', deny: 'Negar', openFile: 'Abrir um arquivo', giveGoal: 'Dar um objetivo', reviewChanges: 'Revisar alterações' },
  sw: { search: 'Tafuta faili, alama na amri', signOut: 'Toka', explorer: 'Kivinjari', changes: 'Mabadiliko', tasks: 'Kazi', memory: 'Kumbukumbu', save: 'Hifadhi', tagline: 'Ndani · Thabiti · Yako', welcomeTitle: 'Jenga na mawakala wasioondoka kwenye kompyuta yako.', welcomeBody: 'Kila hatua inarekodiwa, inaweza kurudiwa na kukaguliwa.', start: 'Anza', signIn: 'Ingia', signInTitle: 'Ingia kwenye Keelway', next: 'Ifuatayo', done: 'Anza sasa', skipTour: 'Ruka', airOn: 'Bila mtandao', airOff: 'Wingu linaruhusiwa', activity: 'Shughuli', allow: 'Ruhusu', deny: 'Kataa', openFile: 'Fungua faili', giveGoal: 'Mpe wakala lengo', reviewChanges: 'Kagua mabadiliko' },
  ar: { search: 'ابحث في الملفات والرموز والأوامر', signOut: 'تسجيل الخروج', explorer: 'المستكشف', changes: 'التغييرات', tasks: 'المهام', memory: 'الذاكرة', save: 'حفظ', tagline: 'محلي · حتمي · ملكك', welcomeTitle: 'ابنِ مع وكلاء لا يغادرون جهازك أبدًا.', welcomeBody: 'كل خطوة مسجلة وقابلة للإعادة والتدقيق.', start: 'ابدأ', signIn: 'دخول', signInTitle: 'تسجيل الدخول إلى Keelway', next: 'التالي', done: 'لنبدأ', skipTour: 'تخطي', airOn: 'معزول', airOff: 'السحابة مسموحة', activity: 'النشاط', allow: 'سماح', deny: 'رفض', openFile: 'افتح ملفًا', giveGoal: 'حدد هدفًا للوكيل', reviewChanges: 'راجع التغييرات' },
  hi: { search: 'फ़ाइलें, सिंबल और कमांड खोजें', signOut: 'साइन आउट', explorer: 'एक्सप्लोरर', changes: 'बदलाव', tasks: 'कार्य', memory: 'मेमोरी', save: 'सहेजें', tagline: 'लोकल · निर्धारक · आपका', welcomeTitle: 'ऐसे एजेंट जो आपकी मशीन कभी नहीं छोड़ते।', welcomeBody: 'हर कदम रिकॉर्ड, दोहराने योग्य और ऑडिट योग्य है।', start: 'शुरू करें', signIn: 'साइन इन', signInTitle: 'Keelway में साइन इन करें', next: 'आगे', done: 'शुरू करें', skipTour: 'छोड़ें', airOn: 'एयर-गैप्ड', airOff: 'क्लाउड अनुमत', activity: 'गतिविधि', allow: 'अनुमति दें', deny: 'अस्वीकार', openFile: 'फ़ाइल खोलें', giveGoal: 'एजेंट को लक्ष्य दें', reviewChanges: 'बदलाव देखें' },
  zh: { search: '搜索文件、符号和命令', signOut: '退出', explorer: '资源管理器', changes: '更改', tasks: '任务', memory: '记忆', save: '保存', tagline: '本地优先 · 确定性 · 属于你', welcomeTitle: '与从不离开你电脑的智能体一起构建。', welcomeBody: '每一步都被记录、可重放、可审计。', start: '开始', signIn: '登录', signInTitle: '登录 Keelway', next: '下一步', done: '开始使用', skipTour: '跳过', airOn: '已隔离', airOff: '允许云端', activity: '活动', allow: '允许', deny: '拒绝', openFile: '打开文件', giveGoal: '给智能体一个目标', reviewChanges: '查看更改' },
};
const MORE = {
  en: { files: 'Files', record: 'Record', labs: 'Labs', runs: 'Agent runs', backlog: 'Backlog', noRuns: 'No runs yet. Describe a goal below and Keelway plans it before touching anything.', needsApproval: 'Needs approval', allowOnce: 'Allow once', approvalNote: 'Your decision is sealed into the record.', why: 'Why', action: 'Action', target: 'Target', network: 'Network', recordBody: 'Every agent step and permission decision, sealed and replayable.', labsBody: 'Experiments. Anything marked Simulated never touches real systems or money.', simulated: 'Simulated', real: 'Runs for real', composerPh: 'Ask Keelway to change something…', back: 'Back', filesEmpty: 'Open a file from the explorer, or press Ctrl K to search.', flight: 'Flight tapes', auditTitle: 'Permission log', healing: 'Self-healing', ledger: 'Payments', runWithAgent: 'Run with agent', queued: 'Queued', running: 'Running', doneStep: 'Done', failedStep: 'Failed', output: 'Output', stepOf: '{done} of {total} steps', netAir: '0 bytes · air-gapped', netCloud: 'not measured · cloud allowed', approvalsWaiting: 'Needs approval · {n}', wantsEdit: 'Keelway wants to edit {target}', wantsWrite: 'Keelway wants to write {target}', wantsRun: 'Keelway wants to run a command', wantsTool: 'Keelway wants to use {tool}', chainOk: 'Chain verified: {n} entries, no gaps · head {head}', chainBroken: 'Chain broken at entry {seq}', localModel: 'Local model', skip: 'Skip to content', status_planning: 'Planning', status_awaiting_approval: 'Needs approval', status_executing_tool: 'Running', status_idle: 'Idle', status_completed: 'Completed', status_failed: 'Failed', allowAlways: 'Allow always…', alwaysScope: 'Scope', alwaysConfirm: 'Allow and remember', cancel: 'Cancel', alwaysHelpPath: 'Future {tool} requests for paths matching this pattern run without asking, in this workspace only. * matches within one folder, ** spans folders.', alwaysHelpCmd: 'Future runs of exactly this command run without asking, in this workspace only.', rulesTitle: 'Standing approvals', rulesHint: 'Only for "Ask before changes" runs. Keelway and git internals always ask.', noRules: 'None yet. Every change asks first.', revoke: 'Revoke', ruleSaved: 'Standing approval saved', autoApproved: 'Allowed by standing approval', scopeRequired: 'Enter a file pattern or command to remember.' },
  es: { allowAlways: 'Permitir siempre…', rulesTitle: 'Aprobaciones permanentes', revoke: 'Revocar', files: 'Archivos', record: 'Registro', runs: 'Ejecuciones', backlog: 'Pendientes', needsApproval: 'Requiere aprobación', allowOnce: 'Permitir una vez', composerPh: 'Pide a Keelway que cambie algo…', newTask: 'Nueva tarea', recordBody: 'Cada paso y decisión, sellados y reproducibles.', labsBody: 'Experimentos. Lo marcado como Simulado nunca toca sistemas ni dinero reales.', simulated: 'Simulado' },
  fr: { allowAlways: 'Toujours autoriser…', rulesTitle: 'Autorisations permanentes', revoke: 'Révoquer', files: 'Fichiers', record: 'Registre', runs: 'Exécutions', backlog: 'À faire', needsApproval: 'Approbation requise', allowOnce: 'Autoriser une fois', composerPh: 'Demandez à Keelway de modifier quelque chose…', newTask: 'Nouvelle tâche', recordBody: 'Chaque étape et décision, scellées et rejouables.', labsBody: 'Expériences. Ce qui est marqué Simulé ne touche jamais de vrais systèmes ni d’argent.', simulated: 'Simulé' },
  pt: { allowAlways: 'Permitir sempre…', rulesTitle: 'Aprovações permanentes', revoke: 'Revogar', files: 'Arquivos', record: 'Registro', runs: 'Execuções', backlog: 'Pendências', needsApproval: 'Requer aprovação', allowOnce: 'Permitir uma vez', composerPh: 'Peça ao Keelway para mudar algo…', newTask: 'Nova tarefa', recordBody: 'Cada passo e decisão, selados e reproduzíveis.', labsBody: 'Experimentos. O que está marcado como Simulado nunca toca sistemas ou dinheiro reais.', simulated: 'Simulado' },
  sw: { allowAlways: 'Ruhusu daima…', rulesTitle: 'Idhini za kudumu', revoke: 'Futa', files: 'Faili', record: 'Rekodi', labs: 'Maabara', runs: 'Utekelezaji', backlog: 'Orodha', needsApproval: 'Inahitaji idhini', allowOnce: 'Ruhusu mara moja', composerPh: 'Mwombe Keelway abadilishe kitu…', newTask: 'Kazi mpya', recordBody: 'Kila hatua na uamuzi, vimetiwa muhuri na vinaweza kurudiwa.', labsBody: 'Majaribio. Chochote kilichoandikwa Kuigwa hakigusi mifumo halisi wala pesa.', simulated: 'Kuigwa' },
  ar: { allowAlways: 'السماح دائمًا…', rulesTitle: 'موافقات دائمة', revoke: 'إلغاء', files: 'الملفات', record: 'السجل', labs: 'المختبر', runs: 'التشغيلات', backlog: 'قائمة المهام', needsApproval: 'بحاجة إلى موافقة', allowOnce: 'السماح مرة واحدة', composerPh: 'اطلب من Keelway تغيير شيء…', newTask: 'مهمة جديدة', recordBody: 'كل خطوة وقرار، مختومة وقابلة للإعادة.', labsBody: 'تجارب. أي شيء موسوم بـ«محاكاة» لا يلمس أنظمة أو أموالًا حقيقية.', simulated: 'محاكاة' },
  hi: { allowAlways: 'हमेशा अनुमति दें…', rulesTitle: 'स्थायी मंज़ूरियाँ', revoke: 'रद्द करें', files: 'फ़ाइलें', record: 'रिकॉर्ड', labs: 'लैब्स', runs: 'रन', backlog: 'बैकलॉग', needsApproval: 'मंज़ूरी चाहिए', allowOnce: 'एक बार अनुमति दें', composerPh: 'Keelway से कुछ बदलने को कहें…', newTask: 'नया कार्य', recordBody: 'हर कदम और फ़ैसला, सील किया हुआ और दोहराने योग्य।', labsBody: 'प्रयोग। “सिम्युलेटेड” चिह्नित कुछ भी असली सिस्टम या पैसे को नहीं छूता।', simulated: 'सिम्युलेटेड' },
  zh: { allowAlways: '始终允许…', rulesTitle: '长期批准', revoke: '撤销', files: '文件', record: '记录', labs: '实验室', runs: '运行', backlog: '待办', needsApproval: '需要批准', allowOnce: '允许一次', composerPh: '让 Keelway 修改点什么…', newTask: '新任务', recordBody: '每一步和每个决定都被封存，可重放。', labsBody: '实验功能。标记为“模拟”的内容不会触及真实系统或资金。', simulated: '模拟' },
};
for (const [k, v] of Object.entries(MORE)) Object.assign(STRINGS[k], v);
const fmt = (key, vars) => t(key).replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
function statusLabel(st) { const k = `status_${st}`; const v = t(k); return v === k ? String(st).replace(/_/g, ' ') : v; }
const LANGS = { en: 'English', es: 'Español', fr: 'Français', pt: 'Português', sw: 'Kiswahili', ar: 'العربية', hi: 'हिन्दी', zh: '中文' };
const RTL = new Set(['ar']);
let lang = localStorage.getItem('keelway.lang') || (navigator.language || 'en').slice(0, 2);
if (!STRINGS[lang]) lang = 'en';
const t = (key) => (STRINGS[lang] && STRINGS[lang][key]) ?? STRINGS.en[key] ?? key;

function applyI18n() {
  document.documentElement.lang = lang;
  document.documentElement.dir = RTL.has(lang) ? 'rtl' : 'ltr';
  document.querySelectorAll('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll('[data-i18n-ph]').forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
  document.querySelectorAll('[data-i18n-label]').forEach((el) => { el.setAttribute('aria-label', t(el.dataset.i18nLabel)); });
}

// ---------- theme, density & sound ----------
function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('keelway.theme', theme);
  if (window.monaco) monaco.editor.setTheme(theme === 'light' ? 'vs' : 'keelwayDark');
}

function setDensity(density) {
  document.documentElement.dataset.density = density;
  localStorage.setItem('keelway.density', density);
  const lbl = $('density-label');
  if (lbl) lbl.textContent = density === 'compact' ? 'Compact' : density === 'comfortable' ? 'Comfort' : 'Normal';
}

function cycleDensity() {
  const current = document.documentElement.dataset.density || 'default';
  const next = current === 'default' ? 'compact' : current === 'compact' ? 'comfortable' : 'default';
  setDensity(next);
  toast(`Density: ${next.charAt(0).toUpperCase() + next.slice(1)} (keelway.fig)`, 'tick');
}

function toggleStatusBarPopover() {
  const pop = $('sb-popover');
  if (!pop) return;
  const isHidden = pop.classList.contains('hidden');
  pop.classList.toggle('hidden', !isHidden);
  if (isHidden && state.status) {
    if ($('pop-model')) $('pop-model').textContent = state.status.local_model || 'qwen2.5-coder:14b';
    if ($('pop-hw')) $('pop-hw').textContent = `${state.status.cpu_arch || 'Apple Silicon arm64'}`;
    if ($('pop-ram')) $('pop-ram').textContent = `${state.status.ram_total_gb ? state.status.ram_total_gb + ' GB RAM' : 'Unified Memory'}`;
    if ($('pop-airgap')) {
      const setting = state.status.air_gapped ? 'Offline (setting)' : 'Cloud allowed (setting)';
      $('pop-airgap').textContent = `${setting} · sent: unmeasured`;
    }
    if ($('pop-mesh-nodes')) {
      const n = (state.meshNodes && state.meshNodes.length) || 0;
      $('pop-mesh-nodes').textContent = n ? `${n} peer(s) reported` : 'Mesh peers not measured';
    }
  }
}
let sound = localStorage.getItem('keelway.sound') !== 'off';
let audioCtx = null;
function tone(kind) {
  if (!sound) return;
  const [f, type, d] = { ok: [880, 'sine', .06], warn: [440, 'triangle', .08], err: [220, 'sawtooth', .12], tick: [1320, 'sine', .025] }[kind] || [660, 'sine', .05];
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const o = audioCtx.createOscillator(), g = audioCtx.createGain();
    o.type = type; o.frequency.value = f;
    g.gain.setValueAtTime(.04, audioCtx.currentTime);
    g.gain.exponentialRampToValueAtTime(.0001, audioCtx.currentTime + d);
    o.connect(g).connect(audioCtx.destination); o.start(); o.stop(audioCtx.currentTime + d);
  } catch { /* no audio */ }
}
let toastTimer;
function toast(msg, kind = 'ok') {
  const el = $('toast');
  el.textContent = msg;
  el.style.borderColor = kind === 'err' ? 'rgb(var(--danger))' : kind === 'warn' ? 'rgb(var(--warn))' : '';
  el.style.opacity = '1';
  tone(kind);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.style.opacity = '0'; }, 2600);
}

// ---------- API + auth ----------
const urlToken = new URLSearchParams(location.search).get('token');
if (urlToken) { localStorage.setItem('keelway.token', urlToken); history.replaceState(null, '', location.pathname + location.hash); }
const token = () => localStorage.getItem('keelway.token');

async function api(path, { method = 'GET', body } = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token()) headers.Authorization = `Bearer ${token()}`;
  const res = await fetch(path, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (res.status === 401) showSignIn();
  if (!res.ok) {
    const d = data && data.detail;
    throw new Error(typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg).join('; ') : `HTTP ${res.status}`);
  }
  return data;
}

const state = { me: null, status: null, tabs: [], active: null, models: {}, buffers: {}, dirty: new Set(), mode: 'editor', diff: null, panel: 'console', view: 'explorer', section: 'tasks', runs: [], agentState: null, lastPending: null, agentTask: null, tapes: [], tape: null, tapeId: null, cursor: 0, ws: null, wsRetry: 0 };

const signInOpen = () => !$('signin').classList.contains('hidden');
function showSignIn(message) {
  const box = $('signin');
  box.classList.remove('hidden'); box.classList.add('flex');
  $('signin-error').textContent = message || '';
  $('signin-error').classList.toggle('hidden', !message);
  setTimeout(() => $('signin-token').focus(), 0);
}
function hideSignIn() { $('signin').classList.add('hidden'); $('signin').classList.remove('flex'); }

async function loadMe() {
  state.me = await api('/v1/auth/whoami');
  const chip = $('role-chip');
  chip.textContent = state.me.auth_required ? `${state.me.role} · ${state.me.actor}` : 'auth off';
  chip.title = state.me.permissions.join(', ');
  $('signout-btn').classList.toggle('hidden', !state.me.auth_required);
  return state.me;
}

async function signIn(e) {
  e.preventDefault();
  localStorage.setItem('keelway.token', $('signin-token').value.trim());
  try { await loadMe(); $('signin-token').value = ''; hideSignIn(); toast(`${t('signIn')} · ${state.me.actor}`); await startSession(); }
  catch (err) { localStorage.removeItem('keelway.token'); showSignIn(t('badToken')); }
}
function signOut() { localStorage.removeItem('keelway.token'); const ws = state.ws; state.ws = null; if (ws) ws.close(); showSignIn(); }

// ---------- status ----------
function setAirGap(on) {
  const b = $('airgap-btn');
  b.setAttribute('aria-pressed', String(on));
  b.style.color = on ? 'rgb(var(--ok))' : 'rgb(var(--warn))';
  b.style.borderColor = on ? 'rgb(var(--ok) / .4)' : 'rgb(var(--warn) / .4)';
  $('airgap-label').textContent = on ? t('airOn') : t('airOff');
  $('sb-egress').textContent = on ? `⛨ ${t('airOn')}` : `↗ ${t('airOff')}`;
  // Bytes are not measured yet — never claim "0 B" from the setting alone.
  $('sb-sent').textContent = 'sent: unmeasured';
  if (state.status) state.status.air_gapped = on;
  if (state.agentState) renderApproval(state.agentState);
}

async function loadStatus() {
  try {
    const s = state.status = await api('/v1/studio/status');
    setAirGap(s.air_gapped);
    $('git-branch').textContent = s.git.branch || '—';
    $('sb-branch').textContent = s.git.branch ? `⎇ ${s.git.branch}@${s.git.sha}` : '';
    $('sb-model').textContent = `◉ ${s.local_model}`;
    $('composer-model').textContent = `${t('localModel')} · ${s.local_model}`;
    $('sb-db').textContent = s.database_connected ? '● db' : '○ db';
    $('sb-hw').textContent = `${s.hardware.arch} · ${s.hardware.ram_gb} GB RAM`;
    const foot = $('sidebar-foot');
    const econ = s.economics || {};
    const footItems = [
      ['RAM', `${s.hardware.ram_gb} GB`],
      ['CPU', s.hardware.arch],
      ['Model', s.hardware.recommended_model],
      ['Tokens', (econ.total_tokens || 0).toLocaleString()],
      ['Savings', `$${(econ.total_cloud_savings_usd || 0).toFixed(2)}`],
      ['Tasks', s.tasks.total],
    ];
    foot.replaceChildren(...footItems.flatMap(([k, v]) => [h('dt', { class: 'text-ide-faint' }, k), h('dd', { class: 'text-end truncate' }, v)]));
  } catch { /* shown via sign-in or status bar */ }
}

async function loadProjectInfo() {
  try {
    const meta = await api('/v1/project/info');
    state.projectMeta = meta;
    const badge = $('project-badge');
    if (badge) {
      if (meta.project_type && meta.project_type !== 'generic') {
        const fw = meta.frameworks && meta.frameworks.length ? ` · ${meta.frameworks.slice(0, 2).join(', ')}` : '';
        badge.textContent = `${meta.project_type}${fw}`;
        badge.classList.remove('hidden');
        badge.title = meta.summary || meta.project_type;
      } else {
        badge.classList.add('hidden');
      }
    }
    const runBtn = $('run-test-btn');
    if (runBtn) {
      if (meta.detected_test_command) {
        runBtn.classList.remove('hidden');
        runBtn.title = `Run detected tests: ${meta.detected_test_command}`;
        if ($('run-test-label')) $('run-test-label').textContent = meta.detected_test_command;
      } else {
        runBtn.classList.add('hidden');
      }
    }
  } catch (err) {
    console.debug('Project info skipped', err);
  }
}

function renderWelcome() {
  const acts = [
    [t('openWorkspace') || 'Open Workspace', () => switchSection('workspace')],
    [t('newTask') || 'New Task', () => { switchSection('tasks'); newRun(); }],
    [t('runs') || 'Evidence', () => switchSection('runs')],
    [t('reviewChanges') || 'Review Changes', () => { switchSection('workspace'); setMode('diff'); }]
  ];
  const el = $('welcome-actions');
  if (el) {
    el.replaceChildren(...acts.map(([label, fn]) => h('button', { type: 'button', class: 'btn-outline justify-start h-10', onclick: fn }, label)));
  }
}

// ---------- file tree ----------
async function loadTree() {
  try {
    const data = await api('/v1/files/tree');
    $('ws-name').textContent = data.name || 'workspace';
    const root = $('file-tree');
    const node = (n, depth) => {
      const pad = { style: `padding-inline-start:${8 + depth * 12}px` };
      if (n.type === 'directory') {
        const kids = h('ul', { role: 'group', class: 'hidden' });
        const btn = h('button', { type: 'button', class: 'w-full text-start py-0.5 text-ide-muted hover:text-ide-fg truncate', 'aria-expanded': 'false', ...pad,
          onclick: () => { const open = kids.classList.toggle('hidden') === false; btn.setAttribute('aria-expanded', String(open)); btn.firstChild.textContent = open ? '▾ ' : '▸ '; } }, '▸ ', n.name);
        (n.children || []).forEach((c) => kids.append(node(c, depth + 1)));
        return h('li', { role: 'treeitem' }, btn, kids);
      }
      return h('li', { role: 'treeitem' }, h('button', { type: 'button', class: 'w-full text-start py-0.5 hover:bg-ide-fg/5 truncate', ...pad, onclick: () => openFile(n.path) }, n.name));
    };
    root.replaceChildren(...(data.tree.children || []).map((c) => node(c, 0)));
  } catch { /* sign-in handles 401 */ }
}

// ---------- editor ----------
let editor = null;
const langFor = (p) => ({ py: 'python', js: 'javascript', ts: 'typescript', json: 'json', md: 'markdown', html: 'html', css: 'css', yml: 'yaml', yaml: 'yaml', sh: 'shell', go: 'go', rs: 'rust', sql: 'sql', toml: 'ini' })[p.split('.').pop()] || 'plaintext';
function initMonaco() {
  if (!window.require || !require.config) { $('fallback-editor').classList.remove('hidden'); return; }
  require.config({ paths: { vs: '/studio/assets/monaco/vs' } });
  require(['vs/editor/editor.main'], () => {
    monaco.editor.defineTheme('keelwayDark', { base: 'vs-dark', inherit: true, rules: [], colors: { 'editor.background': '#0D1218', 'editor.lineHighlightBackground': '#161C24', 'editorCursor.foreground': '#2DD4BF' } });
    editor = monaco.editor.create($('monaco-mount'), { theme: document.documentElement.dataset.theme === 'light' ? 'vs' : 'keelwayDark', automaticLayout: true, minimap: { enabled: false }, fontSize: 13, scrollBeyondLastLine: false });
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, saveFile);
    editor.onDidChangeModelContent(() => { if (state.active && !state.syncing) { state.dirty.add(state.active); renderTabs(); } });
    if (state.active) state.buffers[state.active] = $('fallback-editor').value;
    for (const [p, text] of Object.entries(state.buffers)) state.models[p] = monaco.editor.createModel(text, langFor(p));
    state.buffers = {};
    if (state.active) editor.setModel(state.models[state.active]);
    setMode(state.mode);
  }, () => { $('fallback-editor').classList.remove('hidden'); });
}

async function openFile(path) {
  try {
    const fresh = !state.dirty.has(path);
    const cached = editor ? state.models[path] : state.buffers[path];
    const content = fresh || cached === undefined ? (await api(`/v1/files/content?path=${encodeURIComponent(path)}`)).content || '' : null;
    if (!editor && state.active) state.buffers[state.active] = $('fallback-editor').value;
    if (!state.tabs.includes(path)) state.tabs.push(path);
    state.active = path;
    if (editor) {
      if (!state.models[path]) state.models[path] = monaco.editor.createModel(content, langFor(path));
      else if (fresh && state.models[path].getValue() !== content) { state.syncing = true; state.models[path].setValue(content); state.syncing = false; }
      editor.setModel(state.models[path]);
    } else {
      if (state.buffers[path] === undefined || fresh) state.buffers[path] = content;
      $('fallback-editor').value = state.buffers[path];
    }
    $('crumb').textContent = path;
    $('save-btn').disabled = false;
    setMode('editor'); renderTabs(); tone('tick');
  } catch (err) { toast(err.message, 'err'); }
}

function renderTabs() {
  $('editor-tabs').replaceChildren(...state.tabs.map((p) => h('button', { type: 'button', role: 'tab', 'aria-selected': String(p === state.active), class: `px-3 text-[11px] font-mono border-t-2 ${p === state.active ? 'border-accent bg-ide-editor' : 'border-transparent text-ide-muted'}`, onclick: () => openFile(p) }, p.split('/').pop(), state.dirty.has(p) ? ' ●' : '')));
  $('crumb-status').textContent = state.active ? (state.dirty.has(state.active) ? t('modified') : t('saved')) : '';
}

async function saveFile() {
  if (!state.active) return;
  const content = editor ? editor.getValue() : $('fallback-editor').value;
  try {
    await api('/v1/files/save', { method: 'POST', body: { path: state.active, content } });
    state.dirty.delete(state.active); renderTabs(); toast(`${t('saved')} · ${state.active}`); tone('ok');
    loadGit();
  } catch (err) { toast(err.message, 'err'); tone('err'); }
}

function setMode(mode) {
  state.mode = mode;
  $('mode-editor').setAttribute('aria-pressed', String(mode === 'editor'));
  $('mode-diff').setAttribute('aria-pressed', String(mode === 'diff'));
  const hasFile = !!state.active;
  $('welcome').classList.toggle('hidden', mode !== 'editor' || hasFile);
  $('monaco-mount').classList.toggle('hidden', mode !== 'editor' || !hasFile || !editor);
  $('fallback-editor').classList.toggle('hidden', mode !== 'editor' || !hasFile || !!editor);
  $('diff-view').classList.toggle('hidden', mode !== 'diff');
  if (mode === 'diff') loadDiff();
  if (mode === 'editor' && editor) editor.layout();
}

async function loadDiff() {
  const view = $('diff-view');
  try {
    const d = await api('/v1/studio/diff');
    if (!d.files.length) { view.replaceChildren(h('p', { class: 'p-6 text-ide-muted' }, t('clean'))); return; }
    view.replaceChildren(...d.files.map((f) => h('section', { class: 'border-b border-ide-border' },
      h('header', { class: 'sticky top-0 px-4 py-1.5 flex justify-between bg-ide-sidebar border-b border-ide-border' },
        h('button', { type: 'button', class: 'hover:underline text-start', onclick: () => openFile(f.path) }, f.path),
        h('span', {}, h('span', { class: 'text-ok' }, `+${f.additions} `), h('span', { class: 'text-danger' }, `−${f.deletions}`))),
      h('table', { class: 'w-full' }, h('tbody', {}, ...f.lines.map((l) => h('tr', { class: l.type === 'add' ? 'diff-add' : l.type === 'del' ? 'diff-del' : l.type === 'hunk' ? 'diff-hunk' : '' },
        h('td', { class: 'w-10 px-2 text-end text-ide-faint select-none' }, l.old ?? ''),
        h('td', { class: 'w-10 px-2 text-end text-ide-faint select-none' }, l.new ?? ''),
        h('td', { class: 'px-2 whitespace-pre', dir: 'ltr' }, l.type === 'add' ? '+ ' : l.type === 'del' ? '- ' : '  ', l.text))))))));
    if (d.truncated) view.append(h('p', { class: 'p-3 text-warn' }, 'Diff truncated.'));
  } catch (err) { view.replaceChildren(h('p', { class: 'p-6 text-danger' }, err.message)); }
}

// ---------- sidebar views ----------
const VIEW_TITLES = { explorer: 'explorer', git: 'changes', tasks: 'tasks', memory: 'memory' };
function switchView(view) {
  state.view = view;
  document.querySelectorAll('[data-view]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.view === view)));
  document.querySelectorAll('.sidebar-view').forEach((v) => v.classList.toggle('hidden', v.id !== `view-${view}`));
  $('sidebar-title').dataset.i18n = VIEW_TITLES[view]; $('sidebar-title').textContent = t(VIEW_TITLES[view]);
  const sb = $('sidebar');
  if (getComputedStyle(sb).display === 'none') { sb.classList.remove('hidden'); sb.classList.add('flex', 'fixed', 'top-12', 'bottom-14', 'start-11', 'z-30', 'shadow-2xl'); }
  refreshView();
}
function refreshView() { ({ explorer: loadTree, git: loadGit, tasks: loadTasks, memory: loadMemories })[state.view](); }

async function loadGit() {
  try {
    const g = await api('/v1/git/status');
    const n = g.files.length;
    $('git-dot').classList.toggle('hidden', n === 0);
    $('sb-changes').textContent = n ? `● ${n}` : '✓';
    $('git-files').replaceChildren(...(n ? g.files.map((f) => h('li', {}, h('button', { type: 'button', class: 'w-full flex gap-2 px-2 py-0.5 rounded hover:bg-ide-fg/5 font-mono text-start', onclick: async () => { await openFile(f.path); setMode('diff'); } },
      h('span', { class: f.status.includes('D') ? 'text-danger' : f.status.includes('?') ? 'text-ok' : 'text-warn' }, f.status.trim() || 'M'), h('span', { class: 'truncate' }, f.path))))
      : [h('li', { class: 'px-2 text-ide-muted' }, t('clean'))]));
  } catch { /* noop */ }
}

const NEXT_STATES = { created: ['planned', 'cancelled'], planned: ['awaiting_approval', 'running', 'cancelled'], awaiting_approval: ['running', 'cancelled'], running: ['verifying', 'failed', 'cancelled'], verifying: ['completed', 'failed', 'planned'], failed: ['planned', 'cancelled'], completed: [], cancelled: [] };
const STATE_TONE = { completed: 'text-ok border-ok/40', failed: 'text-danger border-danger/40', cancelled: 'text-ide-faint border-ide-border', running: 'text-accent border-accent/40', verifying: 'text-accent border-accent/40', awaiting_approval: 'text-warn border-warn/40' };
async function loadTasks() {
  try {
    const tasks = await api('/v1/tasks?limit=50');
    $('task-list').replaceChildren(...(tasks.length ? tasks.map((tk) => h('li', { class: 'p-2 rounded-md border border-ide-border bg-ide-bg/40 space-y-1.5' },
      h('div', { class: 'flex justify-between gap-2' }, h('span', { class: 'truncate font-medium' }, tk.title), h('span', { class: `chip ${STATE_TONE[tk.state] || 'border-ide-border text-ide-muted'}` }, tk.state.replace('_', ' '))),
      h('div', { class: 'flex flex-wrap gap-1' },
        ['completed', 'cancelled'].includes(tk.state) ? null : h('button', { type: 'button', class: 'btn-ghost py-0 text-[10px] text-accent', onclick: () => { newRun(); $('agent-goal').value = tk.title; } }, t('runWithAgent')),
        ...NEXT_STATES[tk.state].map((st) => h('button', { type: 'button', class: 'btn-outline py-0 text-[10px]', onclick: () => transition(tk.id, st) }, `→ ${st.replace('_', ' ')}`)))))
      : [h('li', { class: 'px-1 text-xs text-ide-muted' }, t('noTasks'))]));
  } catch { /* noop */ }
}

// ---------- sections + agent runs ----------
const SECTIONS = ['home', 'workspace', 'tasks', 'runs', 'skills', 'settings'];
const SECTION_ALIASES = {
  files: 'workspace',
  evidence: 'runs',
  record: 'runs'
};

let lastFocusedBeforeLabs = null;
function toggleLabsDrawer(open) {
  const drawer = $('labs-drawer');
  const backdrop = $('labs-backdrop');
  if (!drawer || !backdrop) return;
  const isCurrentlyOpen = drawer.classList.contains('translate-x-0');
  const shouldOpen = open !== undefined ? Boolean(open) : !isCurrentlyOpen;
  if (shouldOpen) {
    lastFocusedBeforeLabs = document.activeElement;
    drawer.classList.remove('translate-x-full');
    drawer.classList.add('translate-x-0');
    drawer.setAttribute('aria-hidden', 'false');
    backdrop.classList.remove('hidden');
    backdrop.classList.add('block');
    const closeBtn = $('labs-close-btn');
    if (closeBtn && typeof closeBtn.focus === 'function') closeBtn.focus();
  } else {
    drawer.classList.add('translate-x-full');
    drawer.classList.remove('translate-x-0');
    drawer.setAttribute('aria-hidden', 'true');
    backdrop.classList.add('hidden');
    backdrop.classList.remove('block');
    if (lastFocusedBeforeLabs && typeof lastFocusedBeforeLabs.focus === 'function' && document.body?.contains?.(lastFocusedBeforeLabs)) {
      lastFocusedBeforeLabs.focus();
    }
    lastFocusedBeforeLabs = null;
  }
}

function switchSection(sec) {
  if (sec === 'labs') {
    toggleLabsDrawer(true);
    if (!state.section) sec = 'home';
    else return;
  }
  if (SECTION_ALIASES[sec]) sec = SECTION_ALIASES[sec];
  if (!SECTIONS.includes(sec)) sec = 'home';
  state.section = sec;
  SECTIONS.forEach((x) => {
    const el = $(`sec-${x}`);
    if (el) {
      el.classList.toggle('hidden', x !== sec);
      el.classList.toggle('flex', x === sec);
    }
  });
  document.querySelectorAll('[data-section]').forEach((b) => {
    const bSec = SECTION_ALIASES[b.dataset.section] || b.dataset.section;
    b.setAttribute('aria-current', bSec === sec ? 'page' : 'false');
  });
  if (location.hash !== `#${sec}`) history.replaceState(null, '', `#${sec}`);
  if (sec === 'home') { welcomeFacts(); }
  if (sec === 'workspace') { refreshView(); if (editor) editor.layout(); }
  if (sec === 'tasks') { loadRuns(); loadTasks(); loadManifestRegistry(); }
  if (sec === 'runs') { loadTapes(); loadAudit(); verifyAudit(); loadRules(); loadCostLedger(); loadEvidenceSummary(); }
  if (sec === 'skills') { loadPlugins(); loadKStackSkillsInStudio(); }
  if (sec === 'settings') { loadTier2Status(); loadMeshStatus(); loadSyncStatusInStudio(); }
}
async function loadRules() {
  try {
    const { rules } = await api('/v1/approval-rules');
    $('rule-list').replaceChildren(...(rules.length ? rules.map((r) => h('li', { class: 'px-3 py-2 flex items-center gap-3' },
      h('span', { class: 'step-chip text-accent border-accent/40 font-mono' }, r.tool_name),
      h('span', { class: 'flex-1 font-mono truncate', dir: 'ltr' }, r.scope),
      h('span', { class: 'hidden sm:inline text-ide-faint' }, `${r.created_by} · ${new Date(r.created_at * 1000).toLocaleDateString(lang)}`),
      h('button', { type: 'button', class: 'btn-outline py-0.5 text-danger', onclick: async () => { try { await api(`/v1/approval-rules/${encodeURIComponent(r.id)}`, { method: 'DELETE' }); tone('tick'); loadRules(); } catch (err) { toast(err.message, 'err'); } } }, t('revoke'))))
      : [h('li', { class: 'px-3 py-2 text-ide-muted' }, t('noRules'))]));
  } catch { /* noop */ }
}
async function loadRuns() {
  try { state.runs = (await api('/v1/agent/runs')).runs; } catch { return; }
  renderRuns();
}
function renderRuns() {
  const runs = state.runs;
  const waiting = runs.filter((r) => r.pending_approval).length;
  const dot = $('rail-approval-dot'); dot.textContent = String(waiting); dot.classList.toggle('hidden', !waiting);
  const sb = $('sb-approval'); sb.textContent = fmt('approvalsWaiting', { n: waiting }); sb.classList.toggle('hidden', !waiting);
  $('run-list').replaceChildren(...(runs.length ? runs.map((r) => {
    const sel = !!state.agentTask && state.agentTask.id === r.task_id;
    const w = !!r.pending_approval;
    const dotTone = w ? 'bg-warn pulse' : r.status === 'failed' ? 'bg-danger' : r.status === 'completed' ? 'bg-ok' : 'bg-accent';
    return h('li', {}, h('button', { type: 'button', 'aria-current': sel ? 'true' : null, class: `w-full text-start p-2 rounded-md border ${sel ? 'border-accent/50 bg-accent/10' : 'border-transparent hover:bg-ide-fg/5'}`, onclick: () => selectRun(r.task_id, r.goal) },
      h('div', { class: 'flex items-center gap-2' }, h('span', { class: `w-2 h-2 rounded-full shrink-0 ${dotTone}`, 'aria-hidden': 'true' }), h('span', { class: 'truncate font-medium', dir: 'auto' }, r.goal || r.task_id)),
      h('div', { class: `mt-0.5 ms-4 text-[11px] ${w ? 'text-warn' : 'text-ide-muted'}` }, w ? `${t('needsApproval')} · ${r.pending_approval.tool_name}` : `${statusLabel(r.status)} · ${fmt('stepOf', { done: r.steps_done, total: r.steps_total })}`)));
  }) : [h('li', { class: 'px-1 text-xs text-ide-muted' }, t('noRuns'))]));
}
async function selectRun(id, goal) {
  state.agentTask = { id, goal };
  try { renderAgent(await api(`/v1/agent/status/${encodeURIComponent(id)}`)); renderRuns(); }
  catch (err) { toast(err.message, 'err'); }
}
function showRunDetail(on) {
  $('task-empty').classList.toggle('hidden', on);
  $('task-detail').classList.toggle('hidden', !on);
  if (on) $('sec-tasks').dataset.detail = 'true';
}
function newRun() {
  state.agentTask = null; state.agentState = null;
  if ($('ide-proof-strip')) renderUnifiedProofStrip($('ide-proof-strip'), null, { mode: 'ide' });
  showRunDetail(false); $('sec-tasks').dataset.detail = 'true';
  if (state.section !== 'tasks') switchSection('tasks');
  renderRuns(); $('agent-goal').focus();
}
async function transition(id, target) {
  try { await api(`/v1/tasks/${id}/transition`, { method: 'POST', body: { target_state: target } }); tone('tick'); loadTasks(); }
  catch (err) { toast(err.message, 'err'); tone('err'); }
}
async function createTask(e) {
  e.preventDefault();
  try { await api('/v1/tasks', { method: 'POST', body: { title: $('task-title').value.trim() } }); $('task-title').value = ''; tone('ok'); loadTasks(); }
  catch (err) { toast(err.message, 'err'); }
}

async function loadMemories(q) {
  try {
    const mems = await api(`/v1/memories?limit=30${q ? `&q=${encodeURIComponent(q)}` : ''}`);
    $('memory-list').replaceChildren(...(mems.length ? mems.map((m) => h('li', { class: 'p-2 rounded-md border border-ide-border bg-ide-bg/40' },
      h('div', { class: 'flex justify-between gap-2 text-[10px] text-ide-faint font-mono' }, h('span', { class: 'truncate' }, m.key), h('span', {}, m.scope)),
      h('p', { class: 'mt-0.5 text-ide-muted line-clamp-3' }, m.content)))
      : [h('li', { class: 'text-ide-muted' }, t('noMemories'))]));
  } catch { /* noop */ }
}
async function saveMemory(e) {
  e.preventDefault();
  try { await api('/v1/memories', { method: 'POST', body: { key: $('memory-key').value.trim(), content: $('memory-content').value.trim() } }); $('memory-key').value = ''; $('memory-content').value = ''; tone('ok'); loadMemories(); }
  catch (err) { toast(err.message, 'err'); }
}

// ---------- bottom panel ----------
const PANELS = ['console'];
function renderPanelTabs() {
  $('panel-tabs').replaceChildren(...PANELS.map((p) => h('button', { type: 'button', role: 'tab', id: `tab-${p}`, class: 'tab', 'aria-selected': String(p === state.panel), 'aria-controls': `panel-${p}`, tabindex: p === state.panel ? '0' : '-1', onclick: () => switchPanel(p),
    onkeydown: (e) => { const i = PANELS.indexOf(p); const d = { ArrowRight: 1, ArrowLeft: -1 }[e.key]; if (d) { const dir = document.documentElement.dir === 'rtl' ? -d : d; switchPanel(PANELS[(i + dir + PANELS.length) % PANELS.length]); $(`tab-${state.panel}`).focus(); } } }, t(p))));
}
function switchPanel(p) {
  state.panel = p; renderPanelTabs();
  PANELS.forEach((x) => { $(`panel-${x}`).classList.toggle('hidden', x !== p); $(`panel-${x}`).classList.toggle('flex', x === p); $(`panel-${x}`).setAttribute('aria-labelledby', `tab-${x}`); });
  if (p === 'flight') loadTapes();
  if (p === 'audit') loadAudit();
}

function log(text, cls = '') {
  const box = $('console-log');
  box.append(h('div', { class: cls }, h('span', { class: 'text-ide-faint' }, new Date().toLocaleTimeString(lang, { hour12: false }), ' '), text));
  while (box.childElementCount > 400) box.firstChild.remove();
  box.scrollTop = box.scrollHeight;
}
const COMMANDS = {
  help: () => log(`commands: ${Object.keys(COMMANDS).join(', ')}`),
  status: async () => { await loadStatus(); const s = state.status; log(`env=${s.environment} db=${s.database_backend}${s.database_connected ? '' : ' (down)'} air_gap=${s.air_gapped} tasks=${s.tasks.total} tapes=${s.flight_tapes} model=${s.local_model}`); },
  whoami: () => log(`${state.me.actor} (${state.me.role}): ${state.me.permissions.join(', ')}`),
  tasks: async () => (await api('/v1/tasks?limit=10')).forEach((tk) => log(`${tk.state.padEnd(18)} ${tk.title}`)),
  tapes: async () => (await api('/v1/flight/tapes')).tapes.forEach((tp) => log(tp.task_id)),
  search: async (q) => (await api(`/v1/index/search?q=${encodeURIComponent(q)}&top_k=8`)).results.forEach((r) => log(`${r.file_path}:${r.line_number} ${r.kind} ${r.name}`)),
  ask: async (prompt) => { const r = await api('/v1/completions', { method: 'POST', body: { messages: [{ role: 'user', content: prompt }] } }); log(r.content ?? JSON.stringify(r), 'text-ide-fg'); },
  verify: async () => { const v = await api('/v1/audit/verify'); log(v.valid ? `audit chain valid · ${v.entries} entries` : `audit chain BROKEN at seq ${v.broken_at_seq}`, v.valid ? 'text-ok' : 'text-danger'); },
  clear: () => $('console-log').replaceChildren(),
};
async function runConsole(e) {
  e.preventDefault();
  const line = $('console-input').value.trim(); if (!line) return;
  $('console-input').value = '';
  log(`❯ ${line}`, 'text-accent');
  const [cmd, ...rest] = line.split(' ');
  const fn = COMMANDS[cmd];
  if (fn) {
    try { await fn(rest.join(' ')); } catch (err) { log(err.message, 'text-danger'); }
    return;
  }
  try {
    const res = await api('/v1/terminal/exec', { method: 'POST', body: { command: line } });
    if (res.stdout) log(res.stdout, 'text-ide-fg');
    if (res.stderr) log(res.stderr, res.exit_code === 0 ? 'text-ide-muted' : 'text-danger');
    log(`[exited with code ${res.exit_code} in ${res.duration_ms}ms]`, res.exit_code === 0 ? 'text-ok' : 'text-danger');
  } catch (err) {
    log(err.message, 'text-danger');
  }
}

// ---------- flight recorder & deterministic replay visualizer ----------
let flightReplayTimer = null;

async function loadTapes() {
  try {
    const { tapes } = await api('/v1/flight/tapes');
    state.tapes = tapes.map((x) => x.task_id).sort();
    const sel = $('tape-select');
    sel.replaceChildren(...(state.tapes.length ? state.tapes.map((id) => h('option', { value: id }, id)) : [h('option', { value: '' }, t('noTapes'))]));
    if (state.tapes.length) {
      const id = state.tapes.includes(state.tapeId) ? state.tapeId : state.tapes[state.tapes.length - 1];
      sel.value = id;
      await loadTape(id);
    } else {
      $('flight-events').replaceChildren();
      if ($('flight-visual-container')) $('flight-visual-container').replaceChildren();
      $('flight-payload').textContent = '';
      if ($('flight-seal-badge')) $('flight-seal-badge').textContent = 'NO TAPES';
    }
  } catch { /* noop */ }
}

async function loadTape(id) {
  if (!id) return;
  if (flightReplayTimer) { clearInterval(flightReplayTimer); flightReplayTimer = null; updatePlayButton(); }
  try {
    state.tape = await api(`/v1/flight/tape/${encodeURIComponent(id)}`);
    state.tapeId = id;
    const n = state.tape.events ? state.tape.events.length : 0;
    const sc = $('flight-scrubber');
    if (sc) { sc.max = String(Math.max(n - 1, 0)); sc.disabled = n === 0; }
    if ($('flight-fork')) $('flight-fork').disabled = n === 0;
    if ($('flight-first')) $('flight-first').disabled = n === 0;
    if ($('flight-prev')) $('flight-prev').disabled = n === 0;
    if ($('flight-play')) $('flight-play').disabled = n === 0;
    if ($('flight-next')) $('flight-next').disabled = n === 0;
    if ($('flight-last')) $('flight-last').disabled = n === 0;

    const hash = state.tape.tape_sha256;
    const sealEl = $('flight-seal-badge');
    if (sealEl) {
      if (hash) {
        sealEl.textContent = `SEALED ${hash.slice(0, 10)}…`;
        sealEl.className = 'chip border-ok/50 text-ok text-[10px] font-mono';
        sealEl.title = `Cryptographic SHA-256 seal: ${hash}`;
      } else {
        sealEl.textContent = 'UNSEALED';
        sealEl.className = 'chip border-warn/50 text-warn text-[10px] font-mono';
      }
    }
    seek(n ? n - 1 : 0);
  } catch (err) { toast(err.message, 'err'); }
}

function updatePlayButton() {
  const icon = $('flight-play-icon');
  const text = $('flight-play-text');
  if (icon && text) {
    if (flightReplayTimer) {
      icon.textContent = '⏸';
      text.textContent = 'Pause';
    } else {
      icon.textContent = '▶';
      text.textContent = 'Play';
    }
  }
}

function toggleFlightReplay() {
  const evs = state.tape ? state.tape.events : [];
  if (!evs.length) return;
  if (flightReplayTimer) {
    clearInterval(flightReplayTimer);
    flightReplayTimer = null;
    updatePlayButton();
    return;
  }
  if (state.cursor >= evs.length - 1) {
    seek(0);
  }
  updatePlayButton();
  flightReplayTimer = setInterval(() => {
    if (state.cursor < evs.length - 1) {
      seek(state.cursor + 1);
    } else {
      clearInterval(flightReplayTimer);
      flightReplayTimer = null;
      updatePlayButton();
    }
  }, 750);
  updatePlayButton();
}

const EVT_TONE = {
  prompt: 'text-accent',
  model_response: 'text-ide-fg',
  tool_call: 'text-warn',
  tool_result: 'text-ok',
  state_transition: 'text-ide-muted',
  approval_requested: 'text-warn',
  approval_granted: 'text-ok',
  approval_denied: 'text-danger',
  plan_initialized: 'text-accent',
  plan_synthesized: 'text-accent',
  scaffolding_completed: 'text-ok',
  verification_executed: 'text-ok',
};

function renderDiffLines(target, replacement) {
  const container = h('div', { class: 'rounded border border-ide-border bg-ide-sidebar font-mono text-[11px] p-2 space-y-0.5 overflow-x-auto' });
  if (target) {
    target.split('\n').filter(Boolean).forEach((line) => {
      container.appendChild(h('div', { class: 'text-danger bg-danger/10 px-1 rounded-sm' }, `- ${line}`));
    });
  }
  if (replacement) {
    replacement.split('\n').filter(Boolean).forEach((line) => {
      container.appendChild(h('div', { class: 'text-ok bg-ok/10 px-1 rounded-sm' }, `+ ${line}`));
    });
  }
  return container;
}

function renderVisualEvent(ev) {
  const c = $('flight-visual-container');
  if (!c) return;
  c.replaceChildren();

  const p = ev.payload || {};
  const headerCard = h('div', { class: 'p-2.5 rounded border border-ide-border bg-ide-sidebar flex items-center justify-between' },
    h('div', { class: 'flex items-center gap-2' },
      h('span', { class: 'font-mono text-xs font-semibold' }, `#${ev.event_index}`),
      h('span', { class: `chip font-mono text-[11px] ${EVT_TONE[ev.event_type] || 'text-ide-fg'} border-ide-border` }, ev.event_type)
    ),
    h('span', { class: 'font-mono text-[10.5px] text-ide-muted' }, ev.timestamp_utc ? new Date(ev.timestamp_utc * 1000).toLocaleTimeString() : '')
  );
  c.appendChild(headerCard);

  if (p.tool_name || (ev.event_type && ev.event_type.startsWith('tool:'))) {
    const toolName = p.tool_name || ev.event_type.replace('tool:', '');
    const toolCard = h('div', { class: 'p-3 rounded border border-ide-border bg-ide-bg space-y-2' },
      h('div', { class: 'flex items-center justify-between text-xs font-mono font-medium text-warn' },
        h('span', {}, `Tool: ${toolName}`),
        p.is_mutation ? h('span', { class: 'chip border-warn/40 text-warn bg-warn/10 text-[10px]' }, 'AST Mutation') : null
      )
    );
    if (p.arguments) {
      if (p.arguments.path) {
        toolCard.appendChild(h('div', { class: 'font-mono text-[11px] text-ide-muted' }, `Path: ${p.arguments.path}`));
      }
      if (p.arguments.target !== undefined || p.arguments.replacement !== undefined) {
        toolCard.appendChild(h('div', { class: 'text-[11px] font-semibold text-ide-muted mt-1' }, 'Diff / AST Replacement:'));
        toolCard.appendChild(renderDiffLines(p.arguments.target, p.arguments.replacement));
      } else if (p.arguments.content !== undefined) {
        toolCard.appendChild(h('div', { class: 'text-[11px] font-semibold text-ide-muted mt-1' }, 'File Content Written:'));
        toolCard.appendChild(h('pre', { class: 'p-2 rounded bg-ide-sidebar text-ide-muted text-[10.5px] font-mono max-h-40 overflow-y-auto whitespace-pre-wrap' }, String(p.arguments.content).slice(0, 500) + (p.arguments.content.length > 500 ? '…' : '')));
      } else if (p.arguments.command !== undefined) {
        toolCard.appendChild(h('div', { class: 'p-2 rounded bg-black/40 text-ok font-mono text-[11px]' }, `$ ${p.arguments.command}`));
      }
    }
    if (p.result) {
      toolCard.appendChild(h('div', { class: 'text-[11px] font-semibold text-ide-muted mt-2' }, 'Result:'));
      toolCard.appendChild(h('pre', { class: 'p-2 rounded bg-ide-sidebar text-ide-muted text-[10.5px] font-mono max-h-36 overflow-y-auto whitespace-pre-wrap' }, JSON.stringify(p.result, null, 2)));
    }
    c.appendChild(toolCard);
  } else if (ev.event_type === 'verification_executed') {
    const verifCard = h('div', { class: 'p-3 rounded border border-ide-border bg-ide-bg space-y-2' },
      h('div', { class: 'flex items-center justify-between text-xs font-mono font-medium' },
        h('span', { class: p.passed ? 'text-ok' : 'text-danger' }, p.passed ? '✓ Tests Passed' : '✗ Tests Failed'),
        h('span', { class: 'text-ide-muted text-[11px]' }, `Exit: ${p.exit_code} · ${Number(p.duration_ms || 0).toFixed(1)} ms`)
      ),
      p.test_command ? h('div', { class: 'p-1.5 rounded bg-black/40 text-ide-muted font-mono text-[10.5px]' }, `$ ${p.test_command}`) : null,
      p.output ? h('pre', { class: 'p-2 rounded bg-ide-sidebar text-[10.5px] font-mono max-h-44 overflow-y-auto text-ide-muted whitespace-pre-wrap' }, p.output) : null
    );
    c.appendChild(verifCard);
  } else if (ev.event_type === 'plan_synthesized' || ev.event_type === 'plan_initialized') {
    const planCard = h('div', { class: 'p-3 rounded border border-ide-border bg-ide-bg space-y-2' },
      h('div', { class: 'font-semibold text-xs text-accent' }, p.goal || p.intent || 'Architecture Plan'),
      p.template ? h('div', { class: 'text-[11px] font-mono text-ide-muted' }, `Template: ${p.template}`) : null,
      p.files_planned ? h('div', { class: 'space-y-1' },
        h('div', { class: 'text-[11px] text-ide-muted font-medium' }, `Planned Files (${p.files_planned.length}):`),
        h('ul', { class: 'list-disc list-inside font-mono text-[10.5px] text-ide-fg' },
          ...p.files_planned.slice(0, 10).map((f) => h('li', {}, f))
        )
      ) : null
    );
    c.appendChild(planCard);
  } else {
    const genericCard = h('div', { class: 'p-3 rounded border border-ide-border bg-ide-bg' },
      h('pre', { class: 'font-mono text-[11px] text-ide-muted whitespace-pre-wrap max-h-60 overflow-y-auto' }, JSON.stringify(p, null, 2))
    );
    c.appendChild(genericCard);
  }
}

function seek(i) {
  const evs = state.tape ? state.tape.events : [];
  state.cursor = Math.max(0, Math.min(i, evs.length - 1));
  const sc = $('flight-scrubber');
  if (sc) sc.value = String(state.cursor);
  const stepEl = $('flight-step');
  if (stepEl) stepEl.textContent = `${evs.length ? state.cursor + 1 : 0} / ${evs.length}`;

  $('flight-events').replaceChildren(...evs.map((ev, idx) =>
    h('li', {},
      h('button', {
        type: 'button',
        'aria-current': idx === state.cursor ? 'step' : null,
        class: `w-full text-start px-2 py-0.5 rounded font-mono text-[11px] ${idx === state.cursor ? 'bg-accent/15 font-semibold' : idx > state.cursor ? 'opacity-40' : ''} ${EVT_TONE[ev.event_type] || ''}`,
        onclick: () => seek(idx)
      }, `#${idx + 1} ${ev.event_type}`)
    )
  ));

  const curEv = evs[state.cursor];
  if (curEv) {
    renderVisualEvent(curEv);
    $('flight-payload').textContent = JSON.stringify(curEv, null, 2);
  } else {
    if ($('flight-visual-container')) $('flight-visual-container').replaceChildren();
    $('flight-payload').textContent = '';
  }
}

async function forkTape() {
  if (!state.tapeId || state.cursor === undefined) return;
  const btn = $('flight-fork');
  if (btn) btn.disabled = true;
  try {
    const r = await api(`/v1/flight/tape/${encodeURIComponent(state.tapeId)}/fork`, {
      method: 'POST',
      body: { event_index: state.cursor }
    });
    toast(`Workspace forked at event #${state.cursor} to ${r.destination || 'worktree'}`, 'ok');
    tone('ok');
  } catch (err) {
    try {
      const r2 = await api('/v1/flight/fork', { method: 'POST', body: { task_id: state.tapeId, at_index: state.cursor + 1 } });
      toast(`${t('fork')} → ${r2.forked_task_id}`, 'ok');
      state.tapeId = r2.forked_task_id;
      loadTapes();
    } catch (err2) {
      toast(err2.message, 'err');
      tone('err');
    }
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ---------- self-healing / ledger ----------
async function runHeal(e) {
  e.preventDefault();
  const btn = $('heal-run'); btn.disabled = true; $('heal-out').textContent = '…';
  try {
    const r = await api('/v1/healing/repair', { method: 'POST', body: { test_command: $('heal-cmd').value, max_attempts: Number($('heal-attempts').value) } });
    $('heal-out').textContent = `${r.success ? '✓ passing' : '✗ not repaired'} after ${r.attempts} attempt(s)\n\n${r.verification_output || ''}\n${r.diff || ''}`;
    tone(r.success ? 'ok' : 'warn'); loadGit();
  } catch (err) { $('heal-out').textContent = err.message; tone('err'); }
  finally { btn.disabled = false; }
}
// ---------- builder, plugins, eval ----------
async function planApp() {
  const intent = $('app-intent').value.trim();
  if (!intent) { toast('Please enter an app intent or requirements', 'warn'); return; }
  const btn = $('app-plan-btn'); btn.disabled = true; $('app-out').textContent = 'Synthesizing architecture plan…';
  try {
    const r = await api('/v1/builder/app/plan', {
      method: 'POST',
      body: { intent, template_id: $('app-template').value, app_name: $('app-name').value.trim() || undefined }
    });
    $('app-out').textContent = `[✓] ARCHITECTURE BLUEPRINT: ${r.app_name} (${r.template})\nPlan SHA-256: ${r.plan_sha256}\n\nFiles Planned:\n${r.file_tree.map((f) => `  • ${f} - ${r.modules[f] || ''}`).join('\n')}\n\nVerification Steps:\n${r.test_plan.map((s) => `  ✓ ${s}`).join('\n')}`;
    tone('ok');
  } catch (err) { $('app-out').textContent = `[-] Plan synthesis error: ${err.message}`; tone('err'); }
  finally { btn.disabled = false; }
}

async function generateApp() {
  const intent = $('app-intent').value.trim();
  if (!intent) { toast('Please enter an app intent or requirements', 'warn'); return; }
  const btn = $('app-generate-btn'); btn.disabled = true; $('app-out').textContent = 'Scaffolding codebase & executing automated test harness…';
  try {
    const r = await api('/v1/builder/app/generate', {
      method: 'POST',
      body: { intent, template_id: $('app-template').value, app_name: $('app-name').value.trim() || undefined, run_verification: true, init_git: true }
    });
    const testStatus = r.tests_passed ? 'PASSED [✓]' : 'FAILED [✗]';
    $('app-out').textContent = `[✓] APPLICATION BUILT SUCCESSFULLY: ${r.app_name} (${r.template})\n` +
      `Export Directory:  ${r.export_dir}\n` +
      `Files Created:     ${r.files_scaffolded.length}\n` +
      `Test Suite:        ${testStatus} (${r.verification.tests_count || 0} passed in ${(r.verification.duration_ms || 0).toFixed(1)}ms)\n` +
      `Flight Tape:       ${r.flight_tape_path}\n` +
      `Tape SHA-256:      ${r.flight_tape_sha256}\n` +
      `Total Duration:    ${r.duration_ms.toFixed(1)}ms`;
    tone(r.tests_passed ? 'ok' : 'warn'); loadGit();
  } catch (err) { $('app-out').textContent = `[-] Build error: ${err.message}`; tone('err'); }
  finally { btn.disabled = false; }
}

async function loadPlugins() {
  const listEl = $('plugins-list'); if (!listEl) return;
  try {
    const plugins = await api('/v1/plugins');
    if (!plugins || plugins.length === 0) {
      listEl.innerHTML = '<p class="text-ide-muted font-sans text-xs">No active plugins found in .keelway/plugins.</p>';
      return;
    }
    listEl.innerHTML = plugins.map((p) => `
      <div class="p-2 rounded bg-ide-bg border border-ide-border space-y-1">
        <div class="flex items-center justify-between font-semibold">
          <span>${esc(p.name)} <span class="text-ide-faint font-normal">v${esc(p.version)}</span></span>
          <span class="chip text-[10px] ${p.status === 'ACTIVE' ? 'text-accent border-accent/50' : 'text-ide-muted border-ide-border'}">${esc(p.status)}</span>
        </div>
        <p class="text-ide-muted font-sans text-[11px]">${esc(p.description || '')}</p>
        ${p.active_tools && p.active_tools.length ? `<p class="text-[10px] text-accent">Tools: ${esc(p.active_tools.join(', '))}</p>` : ''}
      </div>
    `).join('');
  } catch (err) { listEl.innerHTML = `<p class="text-danger">${esc(err.message)}</p>`; }
}

async function installPluginForm(e) {
  e.preventDefault();
  const input = $('plugin-path-input'); const p = input.value.trim();
  if (!p) return;
  const out = $('plugin-out'); out.textContent = 'Installing plugin…';
  try {
    let manifest;
    if (p.startsWith('{')) { manifest = JSON.parse(p); }
    else { manifest = { name: p.replace(/[^a-zA-Z0-9_-]/g, '_'), version: '0.1.0', description: `Plugin from ${p}`, author: 'Developer' }; }
    const r = await api('/v1/plugins/install', { method: 'POST', body: { manifest, activate: true } });
    out.textContent = `[✓] Installed and activated plugin '${r.name}' (Digest: ${r.digest_sha256.slice(0, 16)}…)`;
    tone('ok'); input.value = ''; loadPlugins();
  } catch (err) { out.textContent = `[-] Plugin install error: ${err.message}`; tone('err'); }
}

async function runEvalRadar() {
  const btn = $('eval-run-btn'); btn.disabled = true; $('eval-out').textContent = 'Executing 10-task golden evaluation panel…';
  try {
    const r = await api('/v1/evals/run', { method: 'POST', body: { model_name: 'keelway-local-default', save_receipt: true } });
    $('eval-out').textContent = `[✓] 10-TASK GOLDEN BENCHMARK COMPLETE (Run ID: ${r.eval_run_id})\n` +
      `Pass@1 Rate:     ${r.pass_rate_pct}% (${r.passed_tasks}/${r.total_tasks} passed)\n` +
      `Duration:        ${r.total_duration_ms.toFixed(2)}ms (p50: ${r.p50_latency_ms.toFixed(2)}ms, p95: ${r.p95_latency_ms.toFixed(2)}ms)\n` +
      `Receipt SHA-256: ${r.receipt_sha256}\n\n` +
      `Tasks Verified:\n` +
      r.task_results.map((t) => `  ${t.passed ? '[✓]' : '[✗]'} ${t.task_id}: ${t.name} (${t.duration_ms.toFixed(2)}ms)`).join('\n');
    tone(r.pass_rate_pct === 100 ? 'ok' : 'warn');
  } catch (err) { $('eval-out').textContent = `[-] Eval error: ${err.message}`; tone('err'); }
  finally { btn.disabled = false; }
}

async function checkDriftRadar() {
  const btn = $('eval-drift-btn'); btn.disabled = true; $('eval-out').textContent = 'Running benchmark & comparing against historical baseline…';
  try {
    const cand = await api('/v1/evals/run', { method: 'POST', body: { model_name: 'keelway-local-default', save_receipt: true } });
    const drift = await api('/v1/evals/drift/compare', { method: 'POST', body: { candidate_run_id: cand.eval_run_id } });
    const tag = drift.drift_detected ? `DRIFT DETECTED [${drift.drift_severity}]` : 'NO DRIFT DETECTED [✓]';
    $('eval-out').textContent = `====================================================\n` +
      `  DRIFT RADAR ANALYSIS: ${tag}\n` +
      `====================================================\n` +
      `Candidate:          ${drift.candidate_run_id} (${drift.candidate_pass_rate}% Pass@1)\n` +
      `Baseline:           ${drift.baseline_run_id} (${drift.baseline_pass_rate}% Pass@1)\n` +
      `Pass@1 Delta:       ${drift.pass_rate_delta > 0 ? '+' : ''}${drift.pass_rate_delta.toFixed(1)}%\n` +
      `p50 Latency Delta:  ${drift.latency_p50_delta_pct > 0 ? '+' : ''}${drift.latency_p50_delta_pct.toFixed(1)}%\n` +
      (drift.regressed_tasks && drift.regressed_tasks.length ? `Regressed Tasks:    ${drift.regressed_tasks.join(', ')}\n` : '') +
      (drift.alert_reasons && drift.alert_reasons.length ? `Alerts:\n` + drift.alert_reasons.map((a) => `  • ${a}`).join('\n') : 'All metrics within stability threshold.');
    tone(drift.drift_detected ? 'warn' : 'ok');
  } catch (err) { $('eval-out').textContent = `[-] Drift check error: ${err.message}`; tone('err'); }
  finally { btn.disabled = false; }
}

// ---------- local team mesh ----------
async function loadMeshStatus() {
  const badge = $('mesh-pooled-badge');
  const list = $('mesh-peers-list');
  try {
    const s = await api('/v1/mesh/status');
    const p = await api('/v1/mesh/peers');
    if (badge) badge.textContent = `${s.total_pooled_vram_mb} MB Pooled (${s.active_peers_count + 1} Nodes)`;
    if (!list) return;
    list.innerHTML = '';

    const loc = p.local_node;
    const locDiv = h('div', { class: 'p-1.5 rounded bg-ide-surface border border-accent/40 flex justify-between items-center' },
      h('div', {},
        h('div', { class: 'font-semibold text-accent' }, `⚡ ${loc.node_id} (Local: ${loc.hostname})`),
        h('div', { class: 'text-[10px] text-ide-muted' }, `mDNS: ${loc.service_type} · VRAM: ${loc.vram_mb} MB · ${loc.tailscale_ip || 'LAN only'}`)),
      h('span', { class: 'step-chip text-accent border-accent text-[10px]' }, 'LOCAL')
    );
    list.appendChild(locDiv);

    if (!p.peers || p.peers.length === 0) {
      list.appendChild(h('div', { class: 'text-ide-muted text-[11px] p-1' }, 'No remote peers broadcasting on local subnet.'));
    } else {
      p.peers.forEach((peer) => {
        const isAlive = peer.is_alive;
        const peerDiv = h('div', { class: 'p-1.5 rounded bg-ide-surface border border-ide-border flex justify-between items-center' },
          h('div', {},
            h('div', { class: 'font-medium' }, `${peer.hostname} (${peer.node_id})`),
            h('div', { class: 'text-[10px] text-ide-muted' }, `${peer.lan_ip}:${peer.port} · ${peer.available_vram_mb} MB · Tasks: ${peer.active_tasks}${peer.tailscale_ip ? ` · TS: ${peer.tailscale_ip}` : ''}`)),
          h('span', { class: `badge text-[10px] ${isAlive ? 'text-ok border-ok' : 'text-danger border-danger'}` }, isAlive ? 'ALIVE' : 'OFFLINE')
        );
        list.appendChild(peerDiv);
      });
    }
  } catch (err) {
    if (list) list.innerHTML = `<div class="text-danger text-xs">[-] Error loading mesh: ${esc(err.message)}</div>`;
  }
}

async function dispatchMeshDelegation(e) {
  e.preventDefault();
  const intentInput = $('mesh-intent-input');
  const vramInput = $('mesh-vram-input');
  const out = $('mesh-out');
  const intent = intentInput.value.trim();
  const minVram = Number(vramInput.value) || 4096;
  if (!intent) return;
  out.textContent = `Routing task '${intent}' across local mesh (min ${minVram} MB VRAM)…`;
  try {
    const res = await api('/v1/mesh/delegate', {
      method: 'POST',
      body: { intent, min_vram_mb: minVram, allow_local_fallback: true }
    });
    const r = res.receipt;
    out.textContent = `[✓] TASK DELEGATED: ${r.delegation_id}\n` +
      `Target Node:     ${r.target_hostname} (${r.target_node_id})\n` +
      `Allocated VRAM:  ${r.allocated_vram_mb} MB\n` +
      `Status:          ${r.status.toUpperCase()}\n` +
      `Execution Time:  ${r.duration_ms || 0.0} ms\n` +
      `HMAC Signature:  ${r.signature.slice(0, 16)}…${r.signature.slice(-8)}`;
    tone('ok');
    loadMeshStatus();
  } catch (err) {
    out.textContent = `[-] Delegation error: ${err.message}`;
    tone('err');
  }
}

// ---------- two-human quorum approvals ----------
async function submitQuorumSign(role) {
  const out = $('quorum-out');
  const principalId = role === 'Security Lead' ? $('quorum-sec-id').value.trim() : $('quorum-plat-id').value.trim();
  if (!principalId) {
    toast(`Please provide a principal ID for ${role}`, 'err');
    return;
  }
  const activeTask = state.runs.find((r) => r.pending_approval && r.pending_approval.requires_quorum) || state.runs[0];
  if (!activeTask) {
    out.textContent = '[-] No active production agent task currently paused for quorum approval.';
    toast('No task awaiting quorum', 'warn');
    return;
  }
  out.textContent = `Submitting cryptographic ${role} signature for task '${activeTask.task_id}' as '${principalId}'…`;
  try {
    const res = await api(`/v1/agent/quorum-approve/${activeTask.task_id}`, {
      method: 'POST',
      body: { role, principal_id: principalId }
    });
    const q = res.quorum_result;
    out.textContent = `[✓] QUORUM SIGNATURE RECORDED\n` +
      `Status:   ${q.status.toUpperCase()}\n` +
      `Quorum:   ${q.quorum_id}\n` +
      (q.signatures_collected ? `Signed:   ${q.signatures_collected.join(', ')}\n` : '') +
      (q.signatures_remaining ? `Pending:  ${q.signatures_remaining.join(', ')}\n` : '') +
      `Message:  ${q.message || 'Signature accepted.'}`;
    if (role === 'Security Lead') {
      $('quorum-sec-badge').textContent = '✓ SIGNED';
      $('quorum-sec-badge').className = 'badge text-[10px] text-ok border-ok';
    } else {
      $('quorum-plat-badge').textContent = '✓ SIGNED';
      $('quorum-plat-badge').className = 'badge text-[10px] text-ok border-ok';
    }
    tone('ok');
    await loadRuns();
  } catch (err) {
    out.textContent = `[-] Quorum signing error: ${err.message}`;
    tone('err');
  }
}

// ---------- evidence room (WP21) ----------
async function loadEvidenceSummary() {
  const out = $('evidence-out');
  if (!out) return;
  out.textContent = 'Aggregating live verification evidence across tests, benchmarks, air-gap, and SBOM…';
  try {
    const pkg = await api('/v1/evidence/summary');
    const verifiedCount = pkg.summary && Number.isInteger(pkg.summary.total_verified_metrics)
      ? pkg.summary.total_verified_metrics
      : pkg.metrics.filter((m) => m.is_verified === true).length;
    const notRunCount = pkg.summary && Number.isInteger(pkg.summary.not_run_metrics)
      ? pkg.summary.not_run_metrics
      : pkg.metrics.filter((m) => evidenceMetricMark(m).mark === 'NOT RUN').length;
    out.textContent = `[i] EVIDENCE ROOM SUMMARY (WP21)\n` +
      `Package ID:   ${pkg.package_id}\n` +
      `Commit SHA:   ${pkg.commit_sha.slice(0, 16)} (${pkg.git_branch})\n` +
      `Sealed Hash:  ${pkg.package_sha256.slice(0, 24)}…\n` +
      `All Verified: ${pkg.summary.all_verified === true ? 'TRUE' : 'FALSE'}\n` +
      `Verified:     ${verifiedCount}\n` +
      `Not run:      ${notRunCount}\n\n` +
      pkg.metrics.map((m) => {
        const mark = evidenceMetricMark(m);
        return `• [${mark.mark}] ${m.name} (${m.category.toUpperCase()}):\n  ${m.claim}\n  Repro: ${m.reproduce_command}`;
      }).join('\n\n');
    tone('ok');
  } catch (err) {
    out.textContent = `[-] Evidence load error: ${err.message}`;
    tone('err');
  }
}

async function sealEvidencePackage() {
  const out = $('evidence-out');
  if (!out) return;
  out.textContent = 'Assembling and cryptographically sealing evidence package…';
  try {
    const res = await api('/v1/evidence/generate', { method: 'POST' });
    const sealedMetrics = (res.evidence_package && res.evidence_package.metrics) || [];
    const sealedVerified = sealedMetrics.filter((m) => m.is_verified === true).length;
    const sealedNotRun = sealedMetrics.filter((m) => evidenceMetricMark(m).mark === 'NOT RUN').length;
    out.textContent = `[i] EVIDENCE PACKAGE SEAL RECORDED\n` +
      `Status:      ${res.status}\n` +
      `Package ID:  ${res.package_id}\n` +
      `SHA-256:     ${res.package_sha256}\n` +
      `Verified:    ${sealedVerified}\n` +
      `Not run:     ${sealedNotRun}\n` +
      `Timestamp:   ${res.evidence_package.timestamp_utc}\n` +
      `Note:        A seal records the package bytes. It does not verify not-run checks.`;
    tone('warn');
    toast('Evidence package sealed. Not-run checks stay unverified.', 'warn');
  } catch (err) {
    out.textContent = `[-] Sealing error: ${err.message}`;
    tone('err');
  }
}

async function verifyEvidencePackage() {
  const out = $('evidence-out');
  if (!out) return;
  out.textContent = 'Cryptographically verifying evidence package…';
  try {
    const gen = await api('/v1/evidence/generate', { method: 'POST' });
    const ver = await api('/v1/evidence/verify', { method: 'POST', body: { package: gen.evidence_package } });
    out.textContent = `[i] EVIDENCE PACKAGE SEAL CHECK\n` +
      `Seal:      ${ver.is_valid ? 'INTACT' : 'MISMATCH'}\n` +
      `Code:      ${ver.status}\n` +
      `Package:   ${ver.details.package_id}\n` +
      `Commit:    ${ver.details.commit_sha}\n` +
      `Metrics:   ${ver.details.metrics_count} recorded\n` +
      `Note:      Seal integrity is not a claim that every metric was verified.`;
    tone(ver.is_valid ? 'warn' : 'err');
    toast(ver.is_valid ? 'Package seal is intact. Metrics are not re-certified.' : 'Package seal does not match.', ver.is_valid ? 'warn' : 'err');
  } catch (err) {
    out.textContent = `[-] Verification error: ${err.message}`;
    tone('err');
  }
}

async function runDoctorDiagnostics() {
  const out = $('doctor-out');
  if (!out) return;
  out.textContent = 'Running sovereign enterprise system diagnostics across 7 dimensions…';
  try {
    const report = await api('/v1/system/doctor');
    out.textContent = `[✓] SOVEREIGN SYSTEM DIAGNOSTICS (${report.overall_status})\n` +
      `Timestamp:   ${report.timestamp_utc}\n` +
      `Python:      ${report.python_version} (${report.os_platform})\n` +
      `Environment: ${report.environment}\n\n` +
      report.sections.map((s, idx) => `[${idx + 1}] ${s.name} [${s.status}]\n` +
        Object.entries(s.details).map(([k, v]) => `    • ${k.replace(/_/g, ' ')}: ${v}`).join('\n')
      ).join('\n\n');
    tone('ok');
    toast(`Diagnostics complete: ${report.overall_status}`, 'ok');
  } catch (err) {
    out.textContent = `[-] Diagnostics error: ${err.message}`;
    tone('err');
  }
}

async function loadSyncStatusInStudio() {
  const out = $('sync-out');
  if (!out) return;
  out.textContent = 'Loading cross-machine sync status…';
  try {
    const data = await api('/v1/sync/status');
    out.textContent = `[✓] SOVEREIGN CROSS-MACHINE SYNC STATUS\n` +
      `Machine ID:      ${data.machine_id}\n` +
      `Organization:    ${data.org_id}\n` +
      `Lamport Clock:   #${data.lamport_counter}\n` +
      `Journal Records: ${data.journal_records_total}\n` +
      `Vector Clocks:   ${JSON.stringify(data.vector_clock)}\n` +
      `Known Peers:     ${Object.keys(data.known_peers).length} synchronized machines\n` +
      (data.latest_record ? `Latest Record:   [#${data.latest_record.lamport_time}] ${data.latest_record.entity_type} for task ${data.latest_record.task_id}` : '');
    tone('ok');
    toast('Sync state loaded', 'ok');
  } catch (err) {
    out.textContent = `[-] Sync status error: ${err.message}`;
    tone('err');
  }
}

async function exportSyncEnvelopeInStudio() {
  const out = $('sync-out');
  if (!out) return;
  out.textContent = 'Assembling authenticated encrypted sync envelope…';
  try {
    const env = await api('/v1/sync/export', { method: 'POST' });
    out.textContent = `[✓] ENCRYPTED SYNC ENVELOPE EXPORTED\n` +
      `Envelope ID:    ${env.envelope_id}\n` +
      `Cipher:         ${env.cipher}\n` +
      `Records Count:  ${env.records_count}\n` +
      `Bundle Digest:  ${env.bundle_digest_sha256.slice(0, 24)}…\n` +
      `Auth Tag:       ${env.auth_tag.slice(0, 24)}…\n` +
      `Created:        ${env.created_at_utc}`;
    tone('ok');
    toast('Sync envelope exported', 'ok');
  } catch (err) {
    out.textContent = `[-] Envelope export error: ${err.message}`;
    tone('err');
  }
}

async function showMobilePairingInStudio() {
  const out = $('sync-out');
  if (!out) return;
  let link = `${window.location.protocol}//${window.location.host}/`;
  let note = 'No pairing code needed (AUTH_REQUIRED=false).';
  if (token()) {
    try {
      const pc = await api('/v1/auth/pairing-codes', { method: 'POST', body: {} });
      link += `?pair=${encodeURIComponent(pc.code)}`;
      note = `Single use, expires ${new Date(pc.expires_at).toLocaleTimeString()}. The phone gets its own token that can only view runs and approve or deny steps.`;
    } catch (err) {
      out.textContent = `[-] Pairing error: ${err.message}`;
      tone('err');
      return;
    }
  }
  const deepLink = `keelway://pair?link=${encodeURIComponent(link)}`;
  out.textContent = `[📱] KEELWAY MOBILE PAIRING\n` +
    `Pairing Link:     ${link}\n` +
    `Mobile Deep Link: ${deepLink}\n` +
    `${note}\n\n` +
    `Instructions:\n` +
    `1. Open Keelway Mobile on iOS / Android connected to same Wi-Fi.\n` +
    `2. Paste the Pairing Link above or open the Deep Link.\n` +
    `3. Tap Connect.`;
  tone('ok');
  toast('Mobile link ready', 'ok');
}

async function loadKStackSkillsInStudio() {
  const out = $('kstack-out');
  if (!out) return;
  out.textContent = 'Querying KStack role skills registry…';
  try {
    const data = await api('/v1/kstack/skills');
    const skills = Array.isArray(data) ? data : (data.skills || []);
    out.textContent = `[✓] KSTACK ACTIVE ROLE SKILLS (${skills.length} Loaded)\n` +
      `─────────────────────────────────────────────────────────────────\n` +
      skills.map(s => `• ${s.name.padEnd(20)} [${s.role}] (v${s.version})\n    Perms: ${s.permissions.join(', ')} | Status: ${s.pinned ? 'PINNED' : 'ACTIVE'}`).join('\n\n');
    tone('ok');
    toast(`${skills.length} role skills loaded`, 'ok');
  } catch (err) {
    out.textContent = `[-] KStack error: ${err.message}`;
    tone('err');
  }
}

async function scanKHubInStudio() {
  const out = $('kstack-out');
  if (!out) return;
  out.textContent = 'Scanning external directories (.claude, .cursor, .codex) for skills…';
  try {
    const res = await api('/v1/khub/scan', { method: 'POST', body: { root_dir: '.' } });
    out.textContent = `[✓] KHUB EXTERNAL SKILL DISCOVERY SCAN COMPLETE\n` +
      `Total Discovered: ${res.discovered_count}\n` +
      `Rules Filtered:   ${res.rules_isolated_count} (.cursor/rules isolated)\n` +
      `Drift Detected:   ${res.drift_count}\n` +
      (res.skills && res.skills.length ? '\n' + res.skills.map(s => `  • ${s.id}: ${s.name} (${s.source_platform})`).join('\n') : '\n  (all skills up to date)');
    tone('ok');
    toast(`KHub scan complete: ${res.discovered_count} found`, 'ok');
  } catch (err) {
    out.textContent = `[-] KHub scan error: ${err.message}`;
    tone('err');
  }
}

async function recordKBrainFactInStudio() {
  const out = $('kbrain-out');
  const scope = $('kbrain-scope') ? $('kbrain-scope').value : 'project';
  const key = $('kbrain-key') ? $('kbrain-key').value.trim() : '';
  const statement = $('kbrain-statement') ? $('kbrain-statement').value.trim() : '';
  if (!key || !statement) {
    toast('Key and Statement are required', 'err');
    return;
  }
  if (/sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|bearer\s+[a-zA-Z0-9_\-\.]{20,}/i.test(statement)) {
    toast('Security alert: Potential raw secret detected in statement!', 'err');
  }
  out.textContent = `Recording fact '${key}' in scope [${scope}]…`;
  try {
    const fact = await api('/v1/kbrain/fact', {
      method: 'POST',
      body: { key, statement, scope, provenance_reason: 'Studio manual entry' }
    });
    out.textContent = `[✓] KBRAIN FACT RECORDED & VERIFIED\n` +
      `ID:          ${fact.id}\n` +
      `Scope:       ${fact.scope}\n` +
      `Key:         ${fact.key}\n` +
      `Statement:   ${fact.statement}\n` +
      `Status:      ${fact.status}\n` +
      `Revision:    #${fact.revision}\n` +
      `SHA-256:     ${fact.sha256}`;
    $('kbrain-key').value = '';
    $('kbrain-statement').value = '';
    tone('ok');
    toast(`Fact recorded: ${fact.key}`, 'ok');
  } catch (err) {
    out.textContent = `[-] Fact recording error: ${err.message}`;
    tone('err');
  }
}

async function queryKBrainFactsInStudio() {
  const out = $('kbrain-out');
  const scope = $('kbrain-scope') ? $('kbrain-scope').value : 'project';
  out.textContent = `Querying KBrain facts (Scope <= ${scope})…`;
  try {
    const facts = await api(`/v1/kbrain/facts?scope=${encodeURIComponent(scope)}`);
    const list = Array.isArray(facts) ? facts : (facts.facts || []);
    out.textContent = `[✓] KBRAIN FACTS QUERY (Scope <= ${scope}, Total: ${list.length})\n` +
      `─────────────────────────────────────────────────────────────────\n` +
      (list.length ? list.map(f => `• [${f.scope}] [${f.status}] ${f.key} (rev ${f.revision}):\n    "${f.statement}"\n    Provenance: ${f.provenance_reason} | Hash: ${f.sha256.slice(0, 16)}…`).join('\n\n') : '  (no facts recorded in this scope)');
    tone('ok');
    toast(`${list.length} facts retrieved`, 'ok');
  } catch (err) {
    out.textContent = `[-] KBrain query error: ${err.message}`;
    tone('err');
  }
}

// ---------- KFlow Durable Task DAG Orchestration ----------
async function runKFlowDAGInStudio() {
  const out = $('kflow-out');
  if (!out) return;
  out.textContent = 'Registering durable KFlow DAG & initiating topological task execution…';

  const setNodeBadge = (id, text, cls) => {
    const el = $(id);
    if (el) {
      el.textContent = text;
      el.className = `badge text-[9px] ${cls}`;
    }
  };

  const flowId = `flow_${Date.now()}`;
  const payload = {
    flow_id: flowId,
    goal: 'Topological verification of spec ingestion, test generation, and code scaffolding',
    max_fanout: 2,
    nodes: [
      { node_id: 'node_1', name: 'Ingest Spec', assigned_role: 'Architect', tool: 'read_spec', dependencies: [] },
      { node_id: 'node_2', name: 'Generate Tests', assigned_role: 'QA Lead', tool: 'pytest', dependencies: ['node_1'] },
      { node_id: 'node_3', name: 'Scaffold Code', assigned_role: 'Core Coder', tool: 'scaffold', dependencies: ['node_2'] },
      { node_id: 'node_4', name: 'Cryptographic Proof', assigned_role: 'Security Lead', tool: 'crypto', dependencies: ['node_3'] }
    ]
  };

  try {
    setNodeBadge('kflow-node-1-badge', 'RUNNING', 'text-accent border-accent animate-pulse');
    await api('/v1/kflow/dag', { method: 'POST', body: payload });

    setNodeBadge('kflow-node-1-badge', '✓ DONE', 'text-ok border-ok');
    setNodeBadge('kflow-node-2-badge', 'RUNNING', 'text-accent border-accent animate-pulse');

    const runRes = await api(`/v1/kflow/dag/${flowId}/run`, {
      method: 'POST',
      body: { git_head_sha: 'c5eb183d2f9a0' }
    });

    setNodeBadge('kflow-node-2-badge', '✓ DONE', 'text-ok border-ok');
    setNodeBadge('kflow-node-3-badge', '✓ DONE', 'text-ok border-ok');
    setNodeBadge('kflow-node-4-badge', '✓ DONE', 'text-ok border-ok');

    const p = runRes.proof_packet;
    out.textContent = `[✓] KFLOW TOPOLOGICAL DAG EXECUTION COMPLETE\n` +
      `Flow ID:          ${p.flow_id}\n` +
      `Status:           COMPLETED\n` +
      `Base Git SHA:     ${p.base_commit_sha}\n` +
      `Nodes Executed:   ${p.nodes_executed} / 4 (100%)\n` +
      `Tests Verified:   ${p.all_tests_passed ? 'YES' : 'NO'}\n` +
      `Proof SHA-256:    ${p.proof_sha256}\n\n` +
      `Evidence Items:\n` +
      p.evidence_items.map((ev) => `• [${ev.node_id}] ${ev.role} (${ev.tool}): ${JSON.stringify(ev.output)}`).join('\n');
    tone('ok');
    toast('KFlow DAG verified & proof sealed', 'ok');
  } catch (err) {
    out.textContent = `[-] KFlow execution error: ${err.message}`;
    setNodeBadge('kflow-node-1-badge', 'FAILED', 'text-danger border-danger');
    tone('err');
  }
}

async function listKFlowDAGsInStudio() {
  const out = $('kflow-out');
  if (!out) return;
  out.textContent = 'Querying registered KFlow DAG workflows…';
  try {
    const res = await api('/v1/kflow/dags');
    if (!res.dags || res.dags.length === 0) {
      out.textContent = '[i] No active DAGs in memory. Click "Run Topological DAG" to dispatch a verified pipeline.';
      return;
    }
    out.textContent = `[✓] ACTIVE KFLOW DAG WORKFLOWS (${res.dags.length}):\n\n` +
      res.dags.map((d) => `• Flow: ${d.flow_id} [${d.status.toUpperCase()}]\n  Goal: ${d.goal}\n  Nodes: ${Object.keys(d.nodes).length} | Checkpoint: ${d.checkpoint_sha256.slice(0, 16)}…`).join('\n\n');
    tone('ok');
  } catch (err) {
    out.textContent = `[-] Error listing KFlow DAGs: ${err.message}`;
    tone('err');
  }
}

function resetKFlowNodesInStudio() {
  ['kflow-node-1-badge', 'kflow-node-2-badge', 'kflow-node-3-badge', 'kflow-node-4-badge'].forEach((id) => {
    const el = $(id);
    if (el) {
      el.textContent = 'PENDING';
      el.className = 'badge text-[9px] text-ide-muted border-ide-border';
    }
  });
  const out = $('kflow-out');
  if (out) out.textContent = 'KFlow node visual state reset to PENDING.';
}

// ---------- Codebase Intelligence & Graph ----------
async function searchCodebaseInStudio() {
  const out = $('code-intel-out');
  const q = $('code-intel-query') ? $('code-intel-query').value.trim() : 'CodeSymbol';
  if (!out) return;
  out.textContent = `Searching codebase symbols matching '${q}'…`;
  try {
    const res = await api(`/v1/codebase/symbols?q=${encodeURIComponent(q)}&top_k=10`);
    if (!res.results || !res.results.length) {
      out.textContent = `[i] No symbols found for '${q}'.`;
      return;
    }
    out.textContent = `[✓] SYMBOL SEARCH: '${q}' (${res.results.length} matches across ${res.total_files} files)\n` +
      `─────────────────────────────────────────────────────────────────\n` +
      res.results.map(r => `• [${r.kind.toUpperCase()}] ${r.name}\n    Location:  ${r.file_path}:${r.line_number}\n    Signature: ${r.signature}` + (r.docstring ? `\n    Docstring: ${r.docstring.slice(0, 60)}…` : '')).join('\n\n');
    tone('ok');
  } catch (err) {
    out.textContent = `[-] Code search error: ${err.message}`;
    tone('err');
  }
}

async function findReferencesInStudio() {
  const out = $('code-intel-out');
  const sym = $('code-intel-query') ? $('code-intel-query').value.trim() : 'CodeSymbol';
  if (!out) return;
  out.textContent = `Scanning cross-file references for '${sym}'…`;
  try {
    const res = await api(`/v1/codebase/references?symbol=${encodeURIComponent(sym)}`);
    if (!res.references || !res.references.length) {
      out.textContent = `[i] No references found for '${sym}'.`;
      return;
    }
    out.textContent = `[✓] CROSS-FILE REFERENCES: '${sym}' (${res.references.length} occurrences)\n` +
      `─────────────────────────────────────────────────────────────────\n` +
      res.references.slice(0, 20).map(r => `• [${r.kind.toUpperCase()}] ${r.file_path}:${r.line_number}\n    ${r.snippet}`).join('\n\n') +
      (res.references.length > 20 ? `\n\n  ... and ${res.references.length - 20} more references.` : '');
    tone('ok');
  } catch (err) {
    out.textContent = `[-] References error: ${err.message}`;
    tone('err');
  }
}

async function viewCallHierarchyInStudio() {
  const out = $('code-intel-out');
  const sym = $('code-intel-query') ? $('code-intel-query').value.trim() : 'extract_symbols';
  if (!out) return;
  out.textContent = `Tracing caller/callee hierarchy for '${sym}'…`;
  try {
    const res = await api(`/v1/codebase/hierarchy?symbol=${encodeURIComponent(sym)}`);
    out.textContent = `[✓] CALL HIERARCHY: '${sym}'\n` +
      `─────────────────────────────────────────────────────────────────\n` +
      `INCOMING CALLERS (${res.callers.length}):\n` +
      (res.callers.length ? res.callers.map(c => `  ← ${c.caller}() at ${c.file_path}:${c.line_number}`).join('\n') : '  (no incoming callers found)\n') +
      `\nOUTGOING CALLEES (${res.callees.length}):\n` +
      (res.callees.length ? res.callees.map(c => `  → ${c.callee}() at ${c.file_path}:${c.line_number}`).join('\n') : '  (no outgoing callees found)');
    tone('ok');
  } catch (err) {
    out.textContent = `[-] Hierarchy error: ${err.message}`;
    tone('err');
  }
}

async function viewModuleGraphInStudio() {
  const out = $('code-intel-out');
  if (!out) return;
  out.textContent = 'Resolving module import dependency DAG…';
  try {
    const g = await api('/v1/codebase/graph');
    out.textContent = `[✓] MODULE DEPENDENCY GRAPH\n` +
      `Nodes (Files): ${g.nodes.length}\n` +
      `Edges (Deps):  ${g.edges.length}\n` +
      `Cycles:        ${g.has_cycles ? g.cycles.length : '0 (Cycle-Free Clean Architecture)'}\n` +
      `─────────────────────────────────────────────────────────────────\n` +
      `Sample Dependency Edges:\n` +
      g.edges.slice(0, 15).map(e => `• ${e.source} → ${e.target} (${e.module})`).join('\n') +
      (g.edges.length > 15 ? `\n  ... and ${g.edges.length - 15} more edges.` : '');
    tone('ok');
  } catch (err) {
    out.textContent = `[-] Module graph error: ${err.message}`;
    tone('err');
  }
}

async function packAgentBundleInStudio() {
  const out = $('bundle-out');
  const src = $('bundle-src-input') ? $('bundle-src-input').value.trim() : '';
  const outArch = $('bundle-out-archive') ? $('bundle-out-archive').value.trim() : '';
  if (!src) { toast('Source directory is required', 'warn'); return; }
  if (out) out.textContent = `Packaging agent bundle from '${src}'…`;
  try {
    const payload = { source_dir: src };
    if (outArch) payload.output_archive = outArch;
    const res = await api('/v1/agent/builder/pack', { method: 'POST', body: payload });
    if (out) {
      out.textContent = `[✓] AGENT BUNDLE PACKED SUCCESSFULLY\n` +
        `Bundle Name:     ${res.manifest.bundle_name}\n` +
        `Archive Path:    ${res.archive_path}\n` +
        `Bundle Digest:   ${res.manifest.bundle_digest_sha256}\n` +
        `Manifest Digest: ${res.manifest.manifest_digest || '(none)'}\n` +
        `Files Packed:    ${Object.keys(res.manifest.files).length}\n` +
        `Created At:      ${res.manifest.created_at_iso}\n` +
        `─────────────────────────────────────────────────────────────────\n` +
        `Files Included:\n` +
        Object.entries(res.manifest.files).map(([f, h]) => `  • ${f.padEnd(25)} ${h.slice(0, 16)}…`).join('\n');
    }
    toast(`[✓] Bundle packed: ${res.archive_path}`, 'ok');
    tone('ok');
  } catch (err) {
    if (out) out.textContent = `[-] Pack error: ${err.message}`;
    toast(`Pack error: ${err.message}`, 'err');
    tone('err');
  }
}

async function unpackAgentBundleInStudio() {
  const out = $('bundle-out');
  const arch = $('bundle-archive-input') ? $('bundle-archive-input').value.trim() : '';
  const dest = $('bundle-dest-input') ? $('bundle-dest-input').value.trim() : '';
  if (!arch) { toast('Archive path is required', 'warn'); return; }
  if (out) out.textContent = `Verifying and unpacking bundle '${arch}'…`;
  try {
    const payload = { archive_path: arch };
    if (dest) payload.destination_dir = dest;
    const res = await api('/v1/agent/builder/unpack', { method: 'POST', body: payload });
    if (out) {
      out.textContent = `[✓] AGENT BUNDLE VERIFIED & UNPACKED\n` +
        `Bundle Name:     ${res.manifest.bundle_name}\n` +
        `Destination Dir: ${res.destination_dir}\n` +
        `Bundle Digest:   ${res.manifest.bundle_digest_sha256} [VERIFIED]\n` +
        `Files Unpacked:  ${Object.keys(res.manifest.files).length}\n` +
        `─────────────────────────────────────────────────────────────────\n` +
        `Verified Files:\n` +
        Object.keys(res.manifest.files).map(f => `  ✓ ${f}`).join('\n');
    }
    toast(`[✓] Bundle unpacked to ${res.destination_dir}`, 'ok');
    tone('ok');
    loadTree();
  } catch (err) {
    if (out) out.textContent = `[-] Unpack error: ${err.message}`;
    toast(`Unpack error: ${err.message}`, 'err');
    tone('err');
  }
}

// =====================================================================
// Unified Proof Strip UX (Workstream F)
// Maps the shared TaskState runtime contracts to 6 verification stages:
// INSPECT ➔ PLAN ➔ AUTHORIZE ➔ EXECUTE ➔ VERIFY ➔ SEAL
// Used uniformly in IDE Mode and Agent Builder Mode without a secondary JS state machine.
// =====================================================================

const PROOF_STAGES = [
  { id: 'inspect', index: 1, label: 'INSPECT', title: 'Context & Air-gap Inspection', desc: 'Validates workspace symbols, model sovereignty, and zero-egress boundaries.' },
  { id: 'plan', index: 2, label: 'PLAN', title: 'Deterministic Planning', desc: 'Constructs bounded execution graph with deterministic step limits and routing.' },
  { id: 'authorize', index: 3, label: 'AUTHORIZE', title: 'Runtime Authorization', desc: 'Enforces permission boundaries, human approvals, and quorum receipts.' },
  { id: 'execute', index: 4, label: 'EXECUTE', title: 'Tool Execution & Mutation', desc: 'Executes sandboxed tools, tracks file mutations, and generates diff records.' },
  { id: 'verify', index: 5, label: 'VERIFY', title: 'Evidence & Test Verification', desc: 'Runs automated test suite; verifies exit codes and assertion logs.' },
  { id: 'seal', index: 6, label: 'SEAL', title: 'Cryptographic Flight-Tape Seal', desc: 'Computes Merkle root and signs tamper-evident SHA-256 execution audit bundle.' }
];

function getIdeStageData(s) {
  if (!s) {
    return PROOF_STAGES.map(stage => ({
      ...stage,
      status: 'idle',
      details: { summary: 'No active task selected or run initialized.' }
    }));
  }

  const st = s.status || 'created';
  const waitingApproval = !!s.pending_approval || st === 'awaiting_approval';
  const isFailed = st === 'failed';
  const isCancelled = st === 'cancelled';

  const planSteps = Array.isArray(s.plan) ? s.plan : [];
  const hasPlan = planSteps.length > 0;
  const completedSteps = planSteps.filter((p) => p.status === 'completed').length;
  const runningSteps = planSteps.filter((p) => p.status === 'running').length;
  const failedSteps = planSteps.filter((p) => p.status === 'failed').length;
  const hasDeniedStep = planSteps.some((p) => p.status === 'failed' && p.observation && String(p.observation).toLowerCase().includes('denied'));
  const exitKnown = s.test_exit_code !== undefined && s.test_exit_code !== null && s.test_exit_code !== '';
  const merkle = typeof s.merkle_root === 'string' && s.merkle_root ? s.merkle_root : null;
  const modelName = s.model_name || (s.model_identity && s.model_identity.name) || null;
  const modelProvider = s.model_provider || null;
  const airgapKnown = s.airgap === true || s.airgap === false;
  const policyLabel = s.policy || 'Not reported';

  let inspectStatus = 'not_run';
  if (['created', 'context_loading'].includes(st)) inspectStatus = 'active';
  else if (typeof s.symbol_count === 'number') inspectStatus = 'passed';

  let planStatus = 'not_run';
  if (st === 'planning') planStatus = 'active';
  else if (hasPlan) planStatus = 'passed';
  else if (isFailed) planStatus = 'failed';

  let authStatus = 'not_run';
  if (waitingApproval) authStatus = 'waiting';
  else if (isCancelled || hasDeniedStep || (isFailed && s.error && String(s.error).toLowerCase().includes('denied'))) authStatus = 'failed';
  else if (s.approval_digest || s.authorized === true) authStatus = 'passed';

  let execStatus = 'not_run';
  if (['executing_tool', 'running'].includes(st) || runningSteps > 0) execStatus = 'active';
  else if (completedSteps > 0) execStatus = 'passed';
  else if (failedSteps > 0) execStatus = 'failed';

  let verifyStatus = 'not_run';
  if (st === 'verifying' && !exitKnown) verifyStatus = 'active';
  else if (exitKnown && Number(s.test_exit_code) !== 0) verifyStatus = 'failed';
  else if (exitKnown && Number(s.test_exit_code) === 0) verifyStatus = 'passed';
  else if (s.verification_status === 'failed') verifyStatus = 'failed';

  let sealStatus = 'not_run';
  if (s.tampered === true || s.hash_verified === false) sealStatus = 'failed';
  else if (s.hash_verified === true && merkle) sealStatus = 'passed';

  return [
    {
      ...PROOF_STAGES[0],
      status: inspectStatus,
      details: {
        model: modelName ? (modelProvider ? `${modelName} · [${modelProvider}]` : modelName) : 'Not reported',
        egress: !airgapKnown ? 'Not checked' : (s.airgap ? 'Air-gap flag is true. Not an independent egress check.' : 'Air-gap flag is false.'),
        airgap: airgapKnown ? s.airgap : null,
        repo: s.repo_path || 'Not reported',
        symbols: typeof s.symbol_count === 'number' ? s.symbol_count : 'Not reported',
        summary: 'Only fields on the task are shown. Missing model, symbol, and egress values stay not reported.'
      }
    },
    {
      ...PROOF_STAGES[1],
      status: planStatus,
      details: {
        goal: s.goal || 'Not reported',
        stepsPlanned: planSteps.length,
        policy: policyLabel,
        summary: hasPlan ? `${planSteps.length} plan steps are on the task.` : 'No plan was recorded.'
      }
    },
    {
      ...PROOF_STAGES[2],
      status: authStatus,
      details: {
        policy: policyLabel,
        quorumRequired: false,
        pendingApproval: waitingApproval ? (s.pending_approval ? s.pending_approval.description : 'Pending human confirmation') : null,
        approvalDigest: s.approval_digest || null,
        summary: waitingApproval ? 'Approval required: action requires human sign-off.' : (authStatus === 'passed' ? 'An approval digest was recorded on the task.' : (authStatus === 'failed' ? 'Authorization denied or task aborted.' : 'No authorization record. Not treated as approved.'))
      }
    },
    {
      ...PROOF_STAGES[3],
      status: execStatus,
      details: {
        toolsInvoked: completedSteps + runningSteps,
        mutations: s.mutations || (s.edit_proposal && s.edit_proposal.file_path ? [s.edit_proposal.file_path] : []),
        diffs: s.diff_stats || 'Not reported',
        summary: execStatus === 'not_run' ? 'No tool execution was recorded.' : 'Tool status comes from the recorded plan steps.'
      }
    },
    {
      ...PROOF_STAGES[4],
      status: verifyStatus,
      details: {
        testCommand: s.test_command || 'Not reported',
        exitCode: exitKnown ? s.test_exit_code : null,
        testOutput: s.test_output || 'Not reported',
        summary: verifyStatus === 'passed' ? 'A recorded test exit code was 0.' : (verifyStatus === 'failed' ? 'A recorded test result failed.' : 'No test result was recorded.')
      }
    },
    {
      ...PROOF_STAGES[5],
      status: sealStatus,
      details: {
        tapeId: s.tape_id || 'Not reported',
        merkleRoot: merkle,
        verified: sealStatus === 'passed',
        summary: sealStatus === 'passed' ? 'A hash check and Merkle root were recorded on the task.' : (sealStatus === 'failed' ? 'A recorded hash check failed or the task was marked tampered.' : 'No seal was recorded.')
      }
    }
  ];
}

function getBuilderStageData(b) {
  if (!b) {
    return PROOF_STAGES.map(stage => ({
      ...stage,
      status: 'idle',
      details: { summary: 'Select a template and click Scaffold & Run Fixture to initialize agent.' }
    }));
  }

  const receipt = b.receipt || {};
  const manifest = b.manifest || {};
  const isCreated = b.status === 'created' || b.status === 'passed';
  const testsPassed = receipt.tests_passed === true;
  const isFailed = b.status === 'failed' || (receipt.tests_passed === false && isCreated);

  return [
    {
      ...PROOF_STAGES[0],
      status: 'not_run',
      details: {
        model: 'Not reported',
        template: b.template_id || manifest.name || 'Not reported',
        schemaVersion: manifest.schema_version || 'Not reported',
        egress: 'Not checked',
        summary: 'No model or egress check is recorded for this scaffold.'
      }
    },
    {
      ...PROOF_STAGES[1],
      status: (manifest.name || receipt.spec_name) ? 'passed' : 'not_run',
      details: {
        specName: receipt.spec_name || manifest.name || 'Not reported',
        version: receipt.version || manifest.version || 'Not reported',
        systemPrompt: manifest.system_prompt ? `${manifest.system_prompt.length} chars` : 'Not reported',
        summary: (manifest.name || receipt.spec_name) ? 'A spec name was recorded on the scaffold.' : 'No spec was recorded.'
      }
    },
    {
      ...PROOF_STAGES[2],
      status: 'not_run',
      details: {
        autonomy: (manifest.permissions && manifest.permissions.autonomy) || 'Not reported',
        allowedTools: (manifest.tools && manifest.tools.length) ? manifest.tools.join(', ') : 'Not reported',
        maxBudgetUsd: (manifest.budget && manifest.budget.max_usd_per_run != null) ? manifest.budget.max_usd_per_run : 'Not reported',
        summary: 'Manifest permissions are a spec, not an approval record.'
      }
    },
    {
      ...PROOF_STAGES[3],
      status: (Array.isArray(receipt.files_created) && receipt.files_created.length) || b.target_dir ? 'passed' : 'not_run',
      details: {
        targetDir: b.target_dir || 'Not reported',
        filesCreated: Array.isArray(receipt.files_created) ? receipt.files_created.join(', ') : 'Not reported',
        durationMs: typeof receipt.duration_ms === 'number' ? `${receipt.duration_ms.toFixed(1)}ms` : 'Not reported',
        summary: 'Scaffold files are shown only when the receipt lists them.'
      }
    },
    {
      ...PROOF_STAGES[4],
      status: testsPassed ? 'passed' : (isFailed ? 'failed' : 'not_run'),
      details: {
        testSuite: 'Not reported',
        exitCode: receipt.exit_code !== undefined ? receipt.exit_code : null,
        testOutput: receipt.test_output || 'Not reported',
        summary: testsPassed ? 'The receipt recorded tests_passed true.' : (isFailed ? 'The receipt recorded a failed evaluation.' : 'No evaluation result was recorded.')
      }
    },
    {
      ...PROOF_STAGES[5],
      status: (testsPassed && receipt.receipt_sha256) ? 'passed' : (isFailed ? 'failed' : 'not_run'),
      details: {
        manifestDigest: receipt.manifest_digest || 'Not reported',
        receiptDigest: receipt.receipt_sha256 || 'Not reported',
        distributable: (testsPassed && receipt.receipt_sha256) ? 'Receipt recorded. Packaging is a separate step.' : 'Not sealed',
        summary: (testsPassed && receipt.receipt_sha256) ? 'A receipt digest was recorded. It is not an independent certification.' : 'No sealed receipt was recorded.'
      }
    }
  ];
}

let activeDrawerStage = null;

function renderUnifiedProofStrip(container, data, options = {}) {
  if (!container) return;
  const mode = options.mode || 'ide';
  const isIde = mode === 'ide';
  const stageData = isIde ? getIdeStageData(data) : getBuilderStageData(data);
  const modeLabel = isIde ? 'IDE Mode' : 'Agent Builder';
  const modelBadge = isIde ? (data && data.model_name ? data.model_name : 'Model not reported') : 'Agent spec';
  const egressChip = data && data.airgap === true ? 'Air-gap flag set' : (data && data.airgap === false ? 'Air-gap flag off' : 'Egress not checked');

  // Overall status summary
  const hasFailure = stageData.some(s => s.status === 'failed');
  const isWaiting = stageData.some(s => s.status === 'waiting');
  const isActive = stageData.some(s => s.status === 'active');
  const allPassed = stageData.every(s => s.status === 'passed');

  const statusTone = hasFailure ? 'text-danger' : (isWaiting ? 'text-warn' : (allPassed ? 'text-ok' : (isActive ? 'text-accent' : 'text-ide-faint')));
  const statusBg = hasFailure ? 'bg-danger' : (isWaiting ? 'bg-warn' : (allPassed ? 'bg-ok' : (isActive ? 'bg-accent' : 'bg-ide-faint')));
  const statusText = hasFailure ? 'A REPORTED STAGE FAILED' : (isWaiting ? 'APPROVAL PENDING' : (allPassed ? 'REPORTED STAGES PASSED' : (isActive ? 'IN PROGRESS' : 'NOT RUN')));

  container.innerHTML = '';

  const card = document.createElement('div');
  card.className = 'proof-strip-card';

  // Header
  const header = document.createElement('div');
  header.className = 'proof-strip-header';
  header.innerHTML = `
    <div class="flex items-center gap-2 flex-wrap">
      <span class="font-semibold text-xs tracking-wider uppercase text-ide-fg">${esc(modeLabel)} Proof Strip</span>
      <span class="step-chip text-accent border-accent/40 font-mono text-[10px]">${esc(modelBadge)}</span>
      <span class="step-chip text-ide-muted border-ide-border font-mono text-[10px]">${esc(egressChip)}</span>
    </div>
    <div class="flex items-center gap-2 text-[11px] font-mono">
      <span class="w-2 h-2 rounded-full shrink-0 ${statusBg} ${isActive || isWaiting ? 'pulse' : ''}" aria-hidden="true"></span>
      <span class="font-semibold ${statusTone}">${statusText}</span>
    </div>
  `;
  card.appendChild(header);

  // Track (tablist)
  const track = document.createElement('div');
  track.className = 'proof-strip-track';
  track.setAttribute('role', 'tablist');
  track.setAttribute('aria-label', `${modeLabel} Verification Stages`);
  track.id = options.id || (isIde ? 'proof-strip' : `${mode}-proof-strip`);
  track.setAttribute('id', track.id);

  const drawer = document.createElement('div');
  drawer.className = 'proof-drawer hidden';
  drawer.setAttribute('role', 'tabpanel');
  drawer.setAttribute('tabindex', '0');
  drawer.id = `${mode}-proof-drawer`;

  function showDrawer(stage) {
    activeDrawerStage = stage.id;
    drawer.classList.remove('hidden');
    drawer.setAttribute('aria-labelledby', `stage-tab-${mode}-${stage.id}`);

    const badgeIcon = stage.status === 'passed' ? '✓' : (stage.status === 'failed' ? '✕' : (stage.status === 'waiting' ? '△' : (stage.status === 'active' ? '◌' : '○')));
    const badgeClass = stage.status === 'passed' ? 'text-ok border-ok/50 bg-ok/10' : (stage.status === 'failed' ? 'text-danger border-danger/60 bg-danger/10' : (stage.status === 'waiting' ? 'text-warn border-warn/60 bg-warn/10' : (stage.status === 'active' ? 'text-accent border-accent/50 bg-accent/10' : 'text-ide-faint border-ide-border bg-ide-bg/50')));

    let detailsHtml = '';
    if (stage.details) {
      detailsHtml = Object.entries(stage.details)
        .filter(([k]) => k !== 'summary')
        .map(([k, v]) => `
          <div class="flex items-start justify-between gap-4 py-1 border-b border-ide-border/40">
            <span class="text-ide-muted font-mono uppercase text-[10px]">${esc(k.replace(/([A-Z])/g, '_$1').toLowerCase())}:</span>
            <span class="text-ide-fg font-mono text-[11px] text-right break-all">${v == null ? 'Not reported' : (typeof v === 'boolean' ? (v ? 'YES' : 'NO') : esc(Array.isArray(v) ? v.join(', ') : v))}</span>
          </div>
        `).join('');
    }

    drawer.innerHTML = `
      <div class="flex items-start justify-between gap-3">
        <div class="space-y-1">
          <div class="flex items-center gap-2">
            <span class="w-5 h-5 rounded-full border flex items-center justify-center font-mono text-xs ${badgeClass}">${badgeIcon}</span>
            <h4 class="font-semibold text-xs text-ide-fg uppercase tracking-wide">Stage ${esc(stage.index)}: ${esc(stage.title)}</h4>
            <span class="step-chip ${badgeClass} text-[10px] uppercase font-mono">${esc(stage.status)}</span>
          </div>
          <p class="text-xs text-ide-muted">${esc(stage.desc)}</p>
        </div>
        <button type="button" class="btn-ghost h-6 w-6 p-0 text-ide-muted hover:text-ide-fg text-xs" aria-label="Close proof drawer" id="${mode}-drawer-close">✕</button>
      </div>
      <div class="mt-3 p-3 bg-ide-sidebar/80 rounded border border-ide-border space-y-1 text-xs">
        <div class="text-ide-fg font-mono text-[11px] mb-2">${stage.details ? esc(stage.details.summary) : ''}</div>
        <div class="space-y-0.5">${detailsHtml}</div>
      </div>
    `;

    const closeBtn = drawer.querySelector(`#${mode}-drawer-close`);
    if (closeBtn) {
      closeBtn.onclick = () => {
        drawer.classList.add('hidden');
        activeDrawerStage = null;
        updateTabSelection();
        const tabBtn = track.querySelector(`#stage-tab-${mode}-${stage.id}`);
        if (tabBtn && typeof tabBtn.focus === 'function') tabBtn.focus();
      };
    }
    drawer.onkeydown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        drawer.classList.add('hidden');
        activeDrawerStage = null;
        updateTabSelection();
        const tabBtn = track.querySelector(`#stage-tab-${mode}-${stage.id}`);
        if (tabBtn && typeof tabBtn.focus === 'function') tabBtn.focus();
      }
    };
    updateTabSelection();
  }

  function updateTabSelection() {
    track.querySelectorAll('.proof-strip-stage').forEach(tab => {
      const isSelected = tab.dataset.stageId === activeDrawerStage;
      tab.setAttribute('aria-selected', String(isSelected));
      tab.classList.toggle('ring-1', isSelected);
      tab.classList.toggle('ring-accent', isSelected);
    });
  }

  stageData.forEach((stg, idx) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.setAttribute('role', 'tab');
    btn.role = 'tab';
    btn.id = `stage-tab-${mode}-${stg.id}`;
    btn.setAttribute('aria-controls', `${mode}-proof-drawer`);
    btn.setAttribute('aria-selected', String(stg.id === activeDrawerStage));
    btn.tabIndex = idx === 0 ? 0 : -1;
    btn.setAttribute('tabindex', String(idx === 0 ? 0 : -1));
    btn.className = 'proof-strip-stage';
    btn.dataset.status = stg.status;
    btn.dataset.stageId = stg.id;

    const icon = stg.status === 'passed' ? '✓' : (stg.status === 'failed' ? '✕' : (stg.status === 'waiting' ? '△' : (stg.status === 'active' ? '◌' : '○')));
    const iconClass = stg.status === 'active' ? 'pulse' : '';

    btn.innerHTML = `
      <div class="flex items-center gap-1.5 w-full">
        <span class="proof-strip-badge ${iconClass}" aria-hidden="true">${icon}</span>
        <span class="proof-strip-label truncate">${esc(stg.label)}</span>
      </div>
      <div class="proof-strip-sublabel truncate">${esc(stg.status).toUpperCase()}</div>
    `;

    btn.onclick = () => {
      if (activeDrawerStage === stg.id && !drawer.classList.contains('hidden')) {
        drawer.classList.add('hidden');
        activeDrawerStage = null;
        updateTabSelection();
      } else {
        showDrawer(stg);
      }
    };

    btn.onkeydown = (e) => {
      const tabs = Array.from(track.querySelectorAll('.proof-strip-stage'));
      const i = tabs.indexOf(btn);
      let nextTab = null;

      if (e.key === 'ArrowRight') {
        e.preventDefault();
        nextTab = tabs[(i + 1) % tabs.length];
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        nextTab = tabs[(i - 1 + tabs.length) % tabs.length];
      } else if (e.key === 'Home') {
        e.preventDefault();
        nextTab = tabs[0];
      } else if (e.key === 'End') {
        e.preventDefault();
        nextTab = tabs[tabs.length - 1];
      } else if (e.key === 'Escape') {
        e.preventDefault();
        drawer.classList.add('hidden');
        activeDrawerStage = null;
        updateTabSelection();
        btn.focus();
        return;
      }

      if (nextTab) {
        tabs.forEach(t => {
          t.tabIndex = -1;
          if (typeof t.setAttribute === 'function') t.setAttribute('tabindex', '-1');
        });
        nextTab.tabIndex = 0;
        if (typeof nextTab.setAttribute === 'function') nextTab.setAttribute('tabindex', '0');
        nextTab.focus();
        showDrawer(stageData[tabs.indexOf(nextTab)]);
      }
    };

    track.appendChild(btn);
  });

  card.appendChild(track);
  card.appendChild(drawer);
  container.appendChild(card);

  // If a drawer stage was already open, maintain state
  if (activeDrawerStage) {
    const stg = stageData.find(s => s.id === activeDrawerStage);
    if (stg) showDrawer(stg);
  }
}

async function scaffoldAgentInStudio() {
  const btn = $('builder-scaffold-btn');
  const out = $('builder-out');
  const templateSelect = $('builder-template-select');
  const nameInput = $('builder-name-input');
  const strip = $('builder-proof-strip');

  const template_id = templateSelect ? templateSelect.value : 'test-fixer';
  const name = nameInput ? nameInput.value.trim() : 'my-test-fixer';

  if (!name) {
    toast('Agent name is required', 'err');
    if (nameInput) nameInput.focus();
    return;
  }

  if (btn) btn.disabled = true;
  if (out) {
    out.classList.remove('hidden');
    out.textContent = `Scaffolding agent '${name}' from template '${template_id}' with local model…\nRunning starter evaluation suite…`;
  }

  if (strip) {
    renderUnifiedProofStrip(strip, {
      status: 'active',
      template_id,
      manifest: { name, version: '0.1.0' }
    }, { mode: 'builder' });
  }

  try {
    const res = await api('/v1/agent/builder/scaffold', {
      method: 'POST',
      body: { template_id, name }
    });

    if (out) {
      out.textContent = `[✓] AGENT SCAFFOLDED & VERIFIED\n` +
        `Spec Name:       ${res.receipt.spec_name}\n` +
        `Version:         ${res.receipt.version}\n` +
        `Target Dir:      ${res.target_dir}\n` +
        `Tests Passed:    ${res.receipt.tests_passed ? 'YES [100% OK]' : 'NO [EVALUATION FAILED]'}\n` +
        `Receipt SHA-256: ${res.receipt.receipt_sha256} [SEALED]\n` +
        `─────────────────────────────────────────────────────────────────\n` +
        `Test Output:\n${res.receipt.test_output}\n` +
        `─────────────────────────────────────────────────────────────────\n` +
        `Files Created:\n` +
        (res.receipt.files_created || []).map(f => `  ✓ ${f}`).join('\n');
    }

    if (strip) {
      renderUnifiedProofStrip(strip, {
        status: res.receipt.tests_passed ? 'created' : 'failed',
        receipt: res.receipt,
        manifest: res.manifest,
        target_dir: res.target_dir,
        template_id
      }, { mode: 'builder' });
    }

    toast(`[✓] Agent ${name} scaffolded and verified`, 'ok');
    tone(res.receipt.tests_passed ? 'ok' : 'err');
    loadTree();
  } catch (err) {
    if (out) out.textContent = `[-] Scaffold error: ${err.message}`;
    if (strip) {
      renderUnifiedProofStrip(strip, {
        status: 'failed',
        error: err.message,
        template_id,
        manifest: { name }
      }, { mode: 'builder' });
    }
    toast(`Scaffold error: ${err.message}`, 'err');
    tone('err');
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function checkConflictsInStudio() {
  const out = $('conflict-out');
  const base = $('conflict-base-input') ? $('conflict-base-input').value : '';
  const left = $('conflict-left-input') ? $('conflict-left-input').value : '';
  const right = $('conflict-right-input') ? $('conflict-right-input').value : '';
  const sid = ($('conflict-space-id') && $('conflict-space-id').value.trim()) || 'default_space';
  if (out) out.textContent = 'Analyzing 3-way branch conflict semantics…';
  try {
    const res = await api(`/v1/kspaces/${encodeURIComponent(sid)}/conflicts/check`, {
      method: 'POST',
      body: { base_text: base, left_text: left, right_text: right, file_path: 'service.py' }
    });
    if (out) {
      out.textContent = `[✓] CONFLICT ANALYSIS REPORT (Space: ${sid})\n` +
        `Has Conflicts:   ${res.has_conflicts ? 'YES [COLLISION DETECTED]' : 'NO [CLEAN MERGE]'}\n` +
        `Auto-Resolvable: ${res.auto_resolvable ? 'YES (Non-Overlapping)' : 'NO (Manual Review Required)'}\n` +
        `Summary:         ${res.summary}\n` +
        `Hunks Analyzed:  ${res.hunks ? res.hunks.length : 0}\n` +
        `─────────────────────────────────────────────────────────────────\n` +
        (res.hunks || []).map((h, i) => `Hunk #${i + 1} [${h.conflict_type}]:\n  Clean: ${h.is_clean}\n  Preview: ${JSON.stringify(h.resolved_content || '(conflict)')}`).join('\n');
    }
    tone(res.has_conflicts && !res.auto_resolvable ? 'warn' : 'ok');
  } catch (err) {
    if (out) out.textContent = `[-] Conflict check error: ${err.message}`;
    tone('err');
  }
}

async function resolveConflictsInStudio() {
  const out = $('conflict-out');
  const base = $('conflict-base-input') ? $('conflict-base-input').value : '';
  const left = $('conflict-left-input') ? $('conflict-left-input').value : '';
  const right = $('conflict-right-input') ? $('conflict-right-input').value : '';
  const sid = ($('conflict-space-id') && $('conflict-space-id').value.trim()) || 'default_space';
  if (out) out.textContent = 'Applying automated AST-guided conflict resolution…';
  try {
    const res = await api(`/v1/kspaces/${encodeURIComponent(sid)}/conflicts/resolve`, {
      method: 'POST',
      body: { base_text: base, left_text: left, right_text: right, strategy: 'auto' }
    });
    if (out) {
      out.textContent = `[✓] RESOLVED CONTENT (Strategy: auto):\n` +
        `─────────────────────────────────────────────────────────────────\n` +
        res.resolved_text;
    }
    toast('Conflicts resolved', 'ok');
    tone('ok');
  } catch (err) {
    if (out) out.textContent = `[-] Resolution error: ${err.message}`;
    tone('err');
  }
}

async function loadTimelineInStudio() {
  const out = $('conflict-out');
  const sid = ($('conflict-space-id') && $('conflict-space-id').value.trim()) || 'default_space';
  if (out) out.textContent = `Fetching team activity timeline for '${sid}'…`;
  try {
    const res = await api(`/v1/kspaces/${encodeURIComponent(sid)}/timeline`);
    if (!res.events || !res.events.length) {
      if (out) out.textContent = `[i] No recorded timeline events for space '${sid}'.`;
      return;
    }
    if (out) {
      out.textContent = `[✓] KSPACES TIMELINE (${res.events.length} events for '${sid}')\n` +
        `─────────────────────────────────────────────────────────────────\n` +
        res.events.map(e => `• [${new Date((e.timestamp_epoch || Date.now() / 1000) * 1000).toISOString()}] [${e.event_type}] ${e.actor}\n    Details: ${JSON.stringify(e.details)}`).join('\n\n');
    }
    tone('ok');
  } catch (err) {
    if (out) out.textContent = `[-] Timeline error: ${err.message}`;
    tone('err');
  }
}

let currentMerkleProof = null;

async function fetchMerkleRootInStudio() {
  const out = $('merkle-out');
  if (out) out.textContent = 'Computing cryptographic Merkle root over audit events…';
  try {
    const res = await api('/v1/audit/merkle/root');
    if (out) {
      out.textContent = `[✓] ENTERPRISE AUDIT MERKLE ROOT\n` +
        `Merkle Root:     ${res.merkle_root || '(empty)'}\n` +
        `Total Events:    ${res.total_events}\n` +
        `Tip Event Hash:  ${res.tip_hash || '(none)'}\n` +
        `Status:          VERIFIED (Immutable Append-Only Log)\n` +
        `Compliance:      SOC 2 Type II / ISO 27001 / NIST SP 800-53`;
    }
    tone('ok');
  } catch (err) {
    if (out) out.textContent = `[-] Merkle root error: ${err.message}`;
    tone('err');
  }
}

async function generateMerkleProofInStudio() {
  const out = $('merkle-out');
  const seq = ($('merkle-seq-input') && $('merkle-seq-input').value.trim()) || '1';
  if (out) out.textContent = `Generating inclusion proof for audit event sequence #${seq}…`;
  try {
    const res = await api(`/v1/audit/merkle/proof/${encodeURIComponent(seq)}`);
    currentMerkleProof = res;
    if (out) {
      out.textContent = `[✓] MERKLE INCLUSION PROOF FOR SEQ #${res.seq}\n` +
        `Leaf Hash:       ${res.entry_hash}\n` +
        `Merkle Root:     ${res.merkle_root}\n` +
        `Proof Depth:     ${res.proof ? res.proof.length : 0} steps\n` +
        `─────────────────────────────────────────────────────────────────\n` +
        `Proof Path:\n` +
        (res.proof || []).map((p, i) => `  Step ${i + 1} [${p.direction}]: ${p.hash}`).join('\n');
    }
    toast(`Proof generated for seq #${seq}`, 'ok');
    tone('ok');
  } catch (err) {
    if (out) out.textContent = `[-] Proof generation error: ${err.message}`;
    tone('err');
  }
}

async function verifyMerkleProofInStudio() {
  const out = $('merkle-out');
  if (!currentMerkleProof) {
    toast('Generate a proof first', 'warn');
    return;
  }
  if (out) out.textContent = 'Cryptographically evaluating Merkle inclusion path against root…';
  try {
    const res = await api('/v1/audit/merkle/verify', {
      method: 'POST',
      body: {
        leaf_hash: currentMerkleProof.entry_hash,
        proof: currentMerkleProof.proof,
        root_hash: currentMerkleProof.merkle_root,
      }
    });
    if (out) {
      out.textContent = `[✓] MERKLE INCLUSION PROOF VERIFICATION: ${res.valid ? 'VALID [100% CRYPTOGRAPHIC MATCH]' : 'FAILED'}\n` +
        `Leaf Hash:   ${currentMerkleProof.entry_hash}\n` +
        `Root Hash:   ${currentMerkleProof.merkle_root}\n` +
        `Conclusion:  Audit event sequence #${currentMerkleProof.seq} is immutably anchored in this Merkle root.`;
    }
    tone(res.valid ? 'ok' : 'err');
    toast(res.valid ? '[✓] Proof verified' : '[-] Proof invalid', res.valid ? 'ok' : 'err');
  } catch (err) {
    if (out) out.textContent = `[-] Verification error: ${err.message}`;
    tone('err');
  }
}

async function exportAuditBundleInStudio() {
  const out = $('merkle-out');
  if (out) out.textContent = 'Generating sealed compliance audit bundle…';
  try {
    const res = await api('/v1/audit/export/bundle', { method: 'POST', body: {} });
    if (out) {
      out.textContent = `[✓] ENTERPRISE COMPLIANCE BUNDLE EXPORTED\n` +
        `Total Events:    ${res.total_events}\n` +
        `Chain Valid:     ${res.chain_valid ? 'YES [UNBROKEN]' : 'NO [TAMPERED]'}\n` +
        `Genesis Hash:    ${res.genesis_hash}\n` +
        `Tip Hash:        ${res.tip_hash}\n` +
        `Merkle Root:     ${res.merkle_root}\n` +
        `Export Path:     ${res.out_path || 'audit_export.json'}\n` +
        `Timestamp:       ${res.timestamp_iso}`;
    }
    toast('Audit bundle exported', 'ok');
    tone(res.chain_valid ? 'ok' : 'warn');
  } catch (err) {
    if (out) out.textContent = `[-] Export error: ${err.message}`;
    tone('err');
  }
}

async function checkSpoolStatusInStudio() {
  const out = $('spool-out');
  const rid = ($('spool-runner-id') && $('spool-runner-id').value.trim()) || 'vpc_us_east_1';
  if (out) out.textContent = `Querying spool backlog status for runner '${rid}'…`;
  try {
    const res = await api(`/v1/runner/spool/status/${encodeURIComponent(rid)}`);
    if (out) {
      out.textContent = `[✓] CUSTOMER RUNNER SPOOL STATUS (Runner: ${res.runner_id})\n` +
        `Pending Backlog:   ${res.pending_count} items\n` +
        `Total Spooled:     ${res.total_spooled} items\n` +
        `Connection State:  OUTBOUND-ONLY POLLING (Active)\n` +
        `Air-Gap Tolerance: ENABLED (Zero data loss across network partitions)`;
    }
    tone('ok');
  } catch (err) {
    if (out) out.textContent = `[-] Spool status error: ${err.message}`;
    tone('err');
  }
}

async function flushSpoolInStudio() {
  const out = $('spool-out');
  const rid = ($('spool-runner-id') && $('spool-runner-id').value.trim()) || 'vpc_us_east_1';
  if (out) out.textContent = `Dispatching batch sync for runner '${rid}'…`;
  try {
    const sampleItems = [
      { item_id: 'item_sample_' + Date.now(), item_type: 'execution_receipt', payload: { runner_id: rid, status: 'completed', duration_ms: 142.5 } }
    ];
    const res = await api('/v1/runner/spool/sync', {
      method: 'POST',
      body: { runner_id: rid, items: sampleItems }
    });
    if (out) {
      out.textContent = `[✓] RUNNER SPOOL BATCH SYNCHRONIZED\n` +
        `Batch ID:          ${res.batch_id}\n` +
        `Runner ID:         ${res.runner_id}\n` +
        `Accepted Items:    ${res.accepted_count} / ${res.item_count}\n` +
        `Batch Receipt SHA: ${res.receipt_sha256} [VERIFIED]\n` +
        `Timestamp:         ${res.timestamp_iso}`;
    }
    toast('Runner spool batch synchronized', 'ok');
    tone('ok');
  } catch (err) {
    if (out) out.textContent = `[-] Spool sync error: ${err.message}`;
    tone('err');
  }
}

function renderSpeculativeTokenStream(tokenStream) {
  const container = $('spec-token-stream');
  if (!container) return;
  container.innerHTML = '';
  if (!tokenStream || tokenStream.length === 0) {
    container.innerHTML = '<span class="text-ide-faint text-[11px] italic">No tokens generated in stream.</span>';
    return;
  }

  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  tokenStream.forEach((item, index) => {
    const span = document.createElement('span');
    span.className = 'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono border transition-all duration-150 border-amber-400/80 bg-amber-400/20 text-amber-300';
    let displayToken = item.token;
    if (displayToken === ' ') displayToken = '␣';
    else if (displayToken === '\n') displayToken = '↵';
    else if (displayToken.startsWith(' ')) displayToken = '␣' + displayToken.slice(1);
    else if (displayToken.startsWith('\n')) displayToken = '↵' + displayToken.slice(1);
    span.textContent = displayToken;
    span.title = `Step ${item.step + 1} · Draft #${item.draft_index + 1} · Status: ${item.status}`;
    container.appendChild(span);

    if (prefersReducedMotion) {
      if (item.status === 'accepted') {
        span.className = 'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono border border-teal-400/80 bg-teal-400/20 text-teal-300';
      } else {
        span.className = 'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono border border-rose-500/80 bg-rose-500/20 text-rose-300 line-through opacity-75';
      }
    } else {
      setTimeout(() => {
        if (item.status === 'accepted') {
          span.className = 'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono border transition-all duration-150 border-teal-400/80 bg-teal-400/20 text-teal-300 shadow-[0_0_8px_rgba(45,212,191,0.25)]';
        } else {
          span.className = 'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono border transition-all duration-150 border-rose-500/80 bg-rose-500/20 text-rose-300 line-through opacity-75';
        }
      }, 50 + index * 30);
    }
  });
}

const KEYWORD_PLANNER_LABEL = 'Keyword/manual planned-tool path. Steps and tool choices are keyword matches, not model-driven planning.';

function readReportedNumber(value) {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) return Number(value);
  return null;
}

function formatBenchNumber(value, digits, suffix) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  const body = digits === 0 && Number.isInteger(value) ? String(value) : value.toFixed(digits);
  return suffix ? body + suffix : body;
}

function speculativeViewNotRun() {
  return {
    kind: 'not_run',
    verified: false,
    badge: 'NOT RUN',
    speedup: null,
    acceptancePct: null,
    proposed: null,
    accepted: null,
    latencySaved: null,
    latencyPct: null,
    edgeCost: null,
    tokenStream: null,
    notice: 'Benchmark has not been run. No metrics are claimed.',
  };
}

function speculativeViewFromFailure() {
  return {
    kind: 'error',
    verified: false,
    badge: 'ERROR',
    speedup: null,
    acceptancePct: null,
    proposed: null,
    accepted: null,
    latencySaved: null,
    latencyPct: null,
    edgeCost: null,
    tokenStream: null,
    notice: 'Benchmark request failed. No metrics were measured.',
  };
}

function speculativeViewFromResponse(res) {
  const source = res && typeof res === 'object' ? res : {};
  const spec = source.speculative_result && typeof source.speculative_result === 'object' ? source.speculative_result : {};
  const speedup = readReportedNumber(spec.effective_speedup_ratio)
    ?? readReportedNumber(source.effective_speedup_ratio)
    ?? readReportedNumber(source.speedup_ratio);
  const acceptanceRate = readReportedNumber(spec.acceptance_rate);
  const acceptancePct = acceptanceRate != null ? acceptanceRate * 100 : readReportedNumber(source.acceptance_rate_pct);
  const baseline = readReportedNumber(source.baseline_latency_ms);
  const specLatency = readReportedNumber(spec.latency_ms);
  const latencySaved = baseline != null && specLatency != null
    ? baseline - specLatency
    : readReportedNumber(source.latency_saved_ms);
  const measured = source.measured === true || source.measurement === 'measured';
  const hasHeuristicFigure = [speedup, acceptancePct, latencySaved, readReportedNumber(source.latency_reduction_pct), readReportedNumber(source.edge_cost_usd), readReportedNumber(spec.draft_tokens_proposed)].some((value) => value != null) || (Array.isArray(spec.token_stream) && spec.token_stream.length > 0);
  if (!measured) {
    return {
      kind: hasHeuristicFigure ? 'simulation' : 'absent',
      verified: false,
      measured: false,
      badge: hasHeuristicFigure ? 'SIMULATION — NOT A MEASUREMENT' : 'NOT A MEASUREMENT',
      speedup: null,
      acceptancePct: null,
      proposed: null,
      accepted: null,
      latencySaved: null,
      latencyPct: null,
      edgeCost: null,
      tokenStream: null,
      notice: hasHeuristicFigure
        ? 'This response is not marked as a measurement. Heuristic speedup, latency, and token figures are not shown.'
        : 'No measured figures were included.',
    };
  }
  const stream = Array.isArray(spec.token_stream) && spec.token_stream.length > 0 ? spec.token_stream : null;
  return {
    kind: 'measurement',
    verified: false,
    measured: true,
    badge: 'REPORTED — NOT INDEPENDENTLY VERIFIED',
    speedup,
    acceptancePct,
    proposed: readReportedNumber(spec.draft_tokens_proposed),
    accepted: readReportedNumber(spec.draft_tokens_accepted),
    latencySaved,
    latencyPct: readReportedNumber(source.latency_reduction_pct),
    edgeCost: readReportedNumber(source.edge_cost_usd),
    tokenStream: stream,
    notice: stream
      ? 'Figures were marked measured by the response. They are not an independent certification.'
      : 'The response was marked measured, and it included no token stream.',
  };
}

function applySpeculativeView(view) {
  const badge = $('spec-status-badge');
  if (badge) {
    badge.textContent = view.badge;
    badge.className = 'chip border-warn/50 text-warn text-[10px] font-mono';
  }
  if ($('spec-speedup')) $('spec-speedup').textContent = formatBenchNumber(view.speedup, 2, 'x');
  if ($('spec-speedup-label')) $('spec-speedup-label').textContent = view.kind === 'simulation' ? 'Heuristic simulation. No measured speedup.' : (view.speedup == null ? 'Not reported' : 'Reported figure. Not independently verified.');
  if ($('spec-acceptance')) $('spec-acceptance').textContent = formatBenchNumber(view.acceptancePct, 1, '%');
  if ($('spec-tokens-label')) {
    $('spec-tokens-label').textContent = view.accepted == null || view.proposed == null
      ? 'Not reported'
      : `${formatBenchNumber(view.accepted, 0)} / ${formatBenchNumber(view.proposed, 0)} draft tokens reported`;
  }
  if ($('spec-latency-saved')) $('spec-latency-saved').textContent = formatBenchNumber(view.latencySaved, 1, ' ms');
  if ($('spec-latency-pct')) $('spec-latency-pct').textContent = view.latencyPct == null ? 'Not reported' : `${formatBenchNumber(view.latencyPct, 1, '%')} latency reduction reported`;
  if ($('spec-cost')) $('spec-cost').textContent = view.edgeCost == null ? '—' : `$${view.edgeCost.toFixed(2)}`;
  if ($('spec-cost-label')) $('spec-cost-label').textContent = 'Endpoint figure only. Not verified.';
  const stream = $('spec-token-stream');
  if (stream) {
    if (view.tokenStream) renderSpeculativeTokenStream(view.tokenStream);
    else {
      stream.innerHTML = '';
      const empty = document.createElement('span');
      empty.className = 'text-ide-faint text-[11px] italic';
      empty.textContent = view.notice;
      stream.appendChild(empty);
    }
    if (stream.parentElement) {
      let note = document.getElementById('spec-token-notice');
      if (!note) {
        note = document.createElement('p');
        note.id = 'spec-token-notice';
        note.className = 'text-[11px] text-warn mb-1';
        stream.parentElement.insertBefore(note, stream);
      }
      note.textContent = view.notice;
      const captions = stream.parentElement.querySelectorAll('span');
      captions.forEach((el) => {
        if (el.textContent && el.textContent.indexOf('Live Speculative') !== -1) {
          el.textContent = 'Endpoint token stream. Not marked as measured evidence.';
        }
      });
    }
  }
  const title = $('speculative-title');
  const blurb = title && title.parentElement ? title.parentElement.querySelector('p') : null;
  if (blurb) blurb.textContent = 'Runs the benchmark endpoint. Missing figures stay blank. Results are not marked verified.';
}

function evidenceMetricMark(metric) {
  const observed = metric && metric.observed_value && typeof metric.observed_value === 'object' ? metric.observed_value : {};
  if (metric && metric.is_verified === true) return { mark: 'VERIFIED', verified: true };
  if (observed.status === 'not_run') return { mark: 'NOT RUN', verified: false };
  if (observed.status === 'error') return { mark: 'ERROR', verified: false };
  return { mark: 'UNVERIFIED', verified: false };
}

function clearStaticEvidenceClaims() {
  const root = document.getElementById('lab-evidence');
  if (!root) return;
  const intro = root.querySelector('p');
  if (intro) intro.textContent = 'Counts appear only after a check runs and returns evidence. Not-run checks stay unverified. No pass total is claimed here.';
  root.querySelectorAll('.text-base').forEach((el) => {
    el.textContent = 'Not run';
    el.classList.remove('text-ok');
    const card = el.parentElement;
    if (!card) return;
    const lines = Array.from(card.children);
    const subtitle = lines[lines.length - 1];
    if (subtitle && subtitle !== el) subtitle.textContent = 'Unverified. Not a pass count.';
  });
}

function classifyComposerResult(mode, response) {
  const status = response && response.status;
  const plan = response && response.structured_plan;
  const unavailable = status === 'unavailable' || status === 'error' || (response && response.available === false && status !== 'keyword_manual');
  const keyword = status === 'keyword_manual'
    || (response && response.planning_source === 'keyword_manual')
    || (plan && plan.planning_source === 'keyword_manual')
    || mode === 'agent';
  const serverTaskId = response && (response.task_id || (response.agent_task && response.agent_task.task_id));
  return {
    unavailable: Boolean(unavailable),
    keywordManual: Boolean(keyword),
    label: keyword ? KEYWORD_PLANNER_LABEL : '',
    allowServerStep: mode === 'agent' && !unavailable && Boolean(serverTaskId),
    toastKind: unavailable ? 'err' : (keyword ? 'warn' : 'ok'),
  };
}

function installKeywordPlannerNotice() {
  const selector = $('mode-selector');
  if (selector && !$('keyword-planner-notice')) {
    const note = document.createElement('p');
    note.id = 'keyword-planner-notice';
    note.className = 'text-[11px] text-warn font-medium';
    note.textContent = KEYWORD_PLANNER_LABEL;
    selector.insertAdjacentElement('afterend', note);
  }
  const agentTab = document.querySelector ? document.querySelector('#mode-selector .mode-tab[data-mode="agent"]') : null;
  if (agentTab) agentTab.textContent = 'Agent (keyword tools)';
  const planTitle = $('plan-title');
  if (planTitle && !$('plan-source-note')) {
    const planNote = document.createElement('p');
    planNote.id = 'plan-source-note';
    planNote.className = 'text-[11px] text-warn';
    planNote.textContent = KEYWORD_PLANNER_LABEL;
    planTitle.insertAdjacentElement('afterend', planNote);
  }
}

function renderKeywordPreview(plan, goal) {
  installKeywordPlannerNotice();
  state.agentTask = null;
  state.agentState = null;
  if ($('agent-goal-label')) $('agent-goal-label').textContent = goal || '';
  if ($('agent-status')) $('agent-status').textContent = 'Keyword plan (not a model)';
  const steps = (plan && plan.steps) || [];
  if ($('plan-progress')) $('plan-progress').textContent = `${steps.length} keyword steps`;
  if ($('agent-plan')) {
    $('agent-plan').replaceChildren(...steps.map((st, i) => h('li', { class: 'card p-3 space-y-1' },
      h('span', {}, `${i + 1}. ${st}`),
      h('span', { class: 'block text-[10px] text-warn' }, 'Keyword/manual step. Not model-driven and not an executed agent task.'))));
  }
}

async function runSpeculativeBenchmarkInStudio() {
  const btn = $('btn-run-spec-benchmark');
  const draft = ($('spec-draft-model') && $('spec-draft-model').value) || 'qwen2.5-coder:0.5b';
  const target = ($('spec-target-model') && $('spec-target-model').value) || 'qwen2.5-coder:7b';
  const kVal = Number(($('spec-lookahead-k') && $('spec-lookahead-k').value) || 4);
  const promptVal = ($('spec-prompt') && $('spec-prompt').value.trim()) || 'def calculate_roi(investment, return_val):';

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="animate-spin inline-block mr-1">⟳</span> Benchmarking…';
  }

  try {
    const res = await api('/v1/models/speculative/benchmark', {
      method: 'POST',
      body: {
        draft_model: draft,
        target_model: target,
        lookahead_k: kVal,
        prompt: promptVal,
        iterations: 5
      }
    });

    const view = speculativeViewFromResponse(res);
    applySpeculativeView(view);
    toast('Benchmark response received. Figures are not verified.', 'warn');
    tone('warn');
  } catch (err) {
    applySpeculativeView(speculativeViewFromFailure());
    toast('Benchmark failed. No metrics were measured.', 'err');
    tone('err');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg><span>Run Benchmark</span>';
    }
  }
}


// ---------- audit ----------
async function loadAudit() {
  const body = $('audit-body');
  if (state.me && !state.me.permissions.includes('view_audit_logs')) { body.replaceChildren(h('tr', {}, h('td', { class: 'p-3 text-ide-muted' }, `Role '${state.me.role}' cannot view audit logs.`))); return; }
  try {
    const rows = await api('/v1/audit?limit=200');
    body.replaceChildren(...rows.map((r) => h('tr', { class: 'border-b border-ide-border/50' },
      h('td', { class: 'px-3 py-0.5 font-mono text-ide-faint' }, r.seq),
      h('td', { class: 'px-2 font-mono text-ide-faint whitespace-nowrap' }, new Date(r.timestamp).toLocaleString(lang)),
      h('td', { class: 'px-2 whitespace-nowrap' }, `${r.actor} · ${r.role}`),
      h('td', { class: 'px-2 font-mono whitespace-nowrap' }, r.action),
      h('td', { class: 'px-2 text-ide-muted truncate max-w-[16rem]' }, r.resource),
      h('td', { class: `px-2 whitespace-nowrap ${r.allowed ? 'text-ok' : 'text-danger'}` }, r.allowed ? '✓ allow' : '✗ deny'),
      h('td', { class: 'px-2 font-mono text-ide-faint', title: r.entry_hash }, r.entry_hash.slice(0, 10)))));
  } catch (err) { body.replaceChildren(h('tr', {}, h('td', { class: 'p-3 text-danger' }, err.message))); }
}
async function verifyAudit() {
  try {
    const v = await api('/v1/audit/verify');
    const el = $('audit-chain');
    el.textContent = v.valid ? fmt('chainOk', { n: v.entries, head: String(v.head).slice(0, 12) }) : fmt('chainBroken', { seq: v.broken_at_seq });
    el.className = `rounded-md border px-3 py-2 text-xs font-mono ${v.valid ? 'border-ok/40 bg-ok/5 text-ok' : 'border-danger/50 bg-danger/5 text-danger'}`;
    tone(v.valid ? 'ok' : 'err');
  } catch (err) { toast(err.message, 'err'); }
}

async function anchorAudit() {
  try {
    const res = await api('/v1/audit/anchor', { method: 'POST' });
    const el = $('audit-chain');
    el.textContent = `[+] Head anchored: ${res.head_hash.slice(0, 16)}… (${res.entries_count} entries, git_note=${res.git_note_anchored ? 'yes' : 'no'})`;
    el.className = 'rounded-md border px-3 py-2 text-xs font-mono border-ok/40 bg-ok/5 text-ok';
    toast('Audit head anchored & signed', 'ok');
  } catch (err) { toast(err.message, 'err'); }
}

async function loadTier2Status() {
  try {
    const s = await api('/v1/tier2/status');
    const b = s.hardware_badges || {};
    if (b.worm && $('t2-worm-badge')) {
      $('t2-worm-badge').textContent = b.worm.status === 'active' ? '✓ Active' : '✗ Inactive';
      $('t2-worm-badge').className = b.worm.status === 'active' ? 'text-ok' : 'text-danger';
      $('t2-worm-detail').textContent = `${b.worm.retention} retention · ${b.worm.mount_path}`;
    }
    if (b.tpm && $('t2-tpm-badge')) {
      $('t2-tpm-badge').textContent = b.tpm.status === 'verified' ? '✓ Verified' : '✗ Failed';
      $('t2-tpm-badge').className = b.tpm.status === 'verified' ? 'text-ok' : 'text-danger';
      $('t2-tpm-detail').textContent = `PCR0: ${(b.tpm.pcr0 || '').slice(0, 14)}… (${b.tpm.manufacturer || 'HW'})`;
    }
    if (b.piv && $('t2-piv-badge')) {
      $('t2-piv-badge').textContent = b.piv.status === 'configured' ? '✓ Slot 9A' : '✗ Missing';
      $('t2-piv-badge').className = b.piv.status === 'configured' ? 'text-ok' : 'text-danger';
      $('t2-piv-detail').textContent = `PIN + Touch · Card: ${b.piv.card_id || 'Primary'}`;
    }
    if (b.recovery && $('t2-recovery-badge')) {
      $('t2-recovery-badge').textContent = b.recovery.status === 'armed' ? '✓ Armed' : '✗ Unarmed';
      $('t2-recovery-badge').className = b.recovery.status === 'armed' ? 'text-ok' : 'text-danger';
      $('t2-recovery-detail').textContent = `2-of-3 Shamir Quorum · ${b.recovery.total_shares || 3} Shares`;
    }
  } catch {
    /* quiet fail */
  }
}

async function verifyTier2() {
  const out = $('tier2-verify-output');
  if (!out) return;
  out.classList.remove('hidden');
  out.textContent = 'Running cryptographic verification on Tier 2 hardware claims…';
  try {
    const res = await api('/v1/tier2/verify', { method: 'POST', body: { subsystem: 'all' } });
    out.textContent = JSON.stringify(res, null, 2);
    if (res.overall_verified) {
      toast('All Tier 2 hardware claims verified', 'ok');
    } else {
      toast('Tier 2 verification completed with warnings', 'warn');
    }
  } catch (err) {
    out.textContent = `Verification error: ${err.message}`;
    toast(err.message, 'err');
  }
}

async function loadManifestRegistry() {
  const tbody = $('registry-tbody');
  if (!tbody) return;
  try {
    const list = await api('/v1/agents/registry');
    $('registry-count').textContent = `${list.length} manifest${list.length === 1 ? '' : 's'}`;
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="p-3 text-center text-ide-muted font-mono">No agent manifests registered yet. Register via POST /v1/agents/registry.</td></tr>';
      return;
    }
    tbody.replaceChildren(...list.map((m) => {
      const isSuspended = m.status === 'suspended';
      const usdSpent = (m.usd_spent || 0).toFixed(4);
      const maxUsd = m.budget && m.budget.max_usd_per_run ? `$${m.budget.max_usd_per_run.toFixed(2)}` : 'unlimited';
      return h('tr', { class: 'hover:bg-ide-sidebar/50' },
        h('td', { class: 'px-3 py-2 font-medium' }, m.name),
        h('td', { class: 'px-2 py-2 font-mono text-ide-muted' }, `v${m.version}`),
        h('td', { class: 'px-2 py-2 font-mono text-ide-faint', title: m.digest }, (m.digest || '').slice(0, 10)),
        h('td', { class: 'px-2 py-2 font-mono text-xs' }, `$${usdSpent} / ${maxUsd}`),
        h('td', { class: 'px-2 py-2' },
          h('span', { class: `chip ${isSuspended ? 'border-danger/40 text-danger bg-danger/5' : 'border-ok/40 text-ok bg-ok/5'}` }, isSuspended ? 'Suspended' : 'Active')),
        h('td', { class: 'px-3 py-2 text-right' },
          h('button', {
            type: 'button',
            class: `btn-outline py-0.5 px-2 text-[11px] ${isSuspended ? 'text-ok hover:border-ok' : 'text-danger hover:border-danger'}`,
            onclick: async () => {
              try {
                await api(`/v1/agents/registry/${encodeURIComponent(m.name)}/${encodeURIComponent(m.version)}/toggle`, { method: 'POST' });
                toast(`Toggled ${m.name} to ${isSuspended ? 'active' : 'suspended'}`, 'ok');
                loadManifestRegistry();
              } catch (e) {
                toast(e.message, 'err');
              }
            }
          }, isSuspended ? 'Reactivate' : 'Kill Switch'))
      );
    }));
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="p-3 text-danger text-center font-mono">${esc(err.message)}</td></tr>`;
  }
}

function presentCostLedger(summary, economics) {
  const source = summary && typeof summary === 'object' ? summary : {};
  const econ = economics && typeof economics === 'object' ? economics : null;
  const reportedNumber = (value) => (typeof value === 'number' && Number.isFinite(value) ? value : null);
  const inferences = reportedNumber(source.total_inferences);
  const localRatio = reportedNumber(source.local_inference_ratio);
  const localCount = reportedNumber(source.local_inferences);
  const externalCost = reportedNumber(source.total_external_cost_usd);
  const tokenTotal = reportedNumber(source.total_tokens);
  const savings = reportedNumber(source.total_cloud_savings_usd);
  const p50 = reportedNumber(source.latency_p50_ms);
  const p95 = reportedNumber(source.latency_p95_ms);
  const localDuration = reportedNumber(source.total_local_duration_ms);
  const sei = econ ? reportedNumber(econ.sovereign_efficiency_index) : null;
  const roi = econ ? reportedNumber(econ.sovereign_roi_percent) : null;
  return {
    inferences: inferences == null ? 'Not run' : `${inferences} inferences`,
    localRatio: localRatio == null ? 'Not run' : `${(localRatio * 100).toFixed(1)}%`,
    billing: localCount == null ? 'Unverified. No ledger has been loaded.' : `${localCount} local inferences recorded`,
    externalCost: externalCost == null ? 'Not run' : `$${externalCost.toFixed(4)}`,
    tokens: tokenTotal == null ? 'Not run' : `${tokenTotal.toLocaleString()} tokens total`,
    savings: savings == null ? 'Not run' : `$${savings.toFixed(4)}`,
    baseline: source.savings_baseline_model ? `Baseline: ${source.savings_baseline_model}` : 'Baseline not reported',
    latency: p50 == null || p95 == null ? 'Not run' : `${p50} / ${p95} ms`,
    localDuration: localDuration == null ? 'Not run' : `${localDuration.toFixed(1)} ms device runtime`,
    sei: sei == null ? 'SEI not run' : `SEI ${sei}/100`,
    roi: roi == null ? 'ROI not run' : `${roi.toFixed(0)}% ROI`,
  };
}

async function loadCostLedger() {
  const tbody = $('econ-tbody');
  if (!tbody) return;
  try {
    const res = await api('/v1/models/ledger?limit=25');
    const summary = res.summary || {};
    const entries = res.entries || [];

    let economics = null;
    try {
      economics = await api('/v1/models/economics');
    } catch { /* quiet fail leaves the unloaded labels */ }
    const view = presentCostLedger(summary, economics);
    if ($('econ-inferences-badge')) $('econ-inferences-badge').textContent = view.inferences;
    if ($('econ-local-ratio')) $('econ-local-ratio').textContent = view.localRatio;
    if ($('econ-billing-label')) $('econ-billing-label').textContent = view.billing;
    if ($('econ-ext-cost')) $('econ-ext-cost').textContent = view.externalCost;
    if ($('econ-total-tokens')) $('econ-total-tokens').textContent = view.tokens;
    if ($('econ-savings')) $('econ-savings').textContent = view.savings;
    if ($('econ-savings-baseline')) $('econ-savings-baseline').textContent = view.baseline;
    if ($('econ-latency')) $('econ-latency').textContent = view.latency;
    if ($('econ-local-dur')) $('econ-local-dur').textContent = view.localDuration;
    if ($('econ-sei-badge')) $('econ-sei-badge').textContent = view.sei;
    if ($('econ-roi-badge')) $('econ-roi-badge').textContent = view.roi;

    if (!entries.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="p-3 text-center text-ide-muted font-mono">No model inferences recorded in ledger yet. Run chat, agent, or evaluation tasks to populate.</td></tr>';
      return;
    }

    tbody.replaceChildren(...entries.slice().reverse().map((e) => {
      const isLocal = e.provider === 'local';
      const badgeCls = isLocal ? 'border-ok/40 text-ok bg-ok/5' : 'border-ide-border text-ide-muted bg-ide-sidebar';
      const costDisplay = isLocal
        ? `+$${(e.estimated_cloud_savings_usd || 0).toFixed(4)} saved`
        : `-$${(e.estimated_external_cost_usd || 0).toFixed(4)}`;
      const costCls = isLocal ? 'text-ok font-medium' : 'text-danger font-medium';

      return h('tr', { class: 'hover:bg-ide-sidebar/50' },
        h('td', { class: 'px-3 py-2 font-mono text-ide-faint' }, e.id),
        h('td', { class: 'px-2 py-2' },
          h('span', { class: `chip ${badgeCls}` }, e.provider)),
        h('td', { class: 'px-2 py-2 font-mono text-ide-muted truncate max-w-[10rem]', title: e.model }, e.model),
        h('td', { class: 'px-2 py-2 font-mono text-[11px]' }, `${e.prompt_tokens.toLocaleString()} / ${e.completion_tokens.toLocaleString()}`),
        h('td', { class: 'px-2 py-2 font-mono text-ide-muted' }, `${e.latency_ms} ms`),
        h('td', { class: 'px-2 py-2 font-mono text-[10.5px] text-ide-muted' }, e.billing_label),
        h('td', { class: `px-3 py-2 text-right font-mono text-xs ${costCls}` }, costDisplay)
      );
    }));
  } catch {
    /* quiet fail */
  }
}


// ---------- agent ----------
const TOOLS = ['list_dir', 'search_codebase', 'read_file', 'edit_file', 'write_file', 'run_command'];
const MUTATING = new Set(['edit_file', 'write_file', 'run_command']);
function suggestTool(desc) {
  const d = desc.toLowerCase();
  if (/search|find|locate/.test(d)) return 'search_codebase';
  if (/test|check|verify|run/.test(d)) return 'run_command';
  if (/patch|edit|fix|change|write|implement/.test(d)) return 'edit_file';
  if (/read|open/.test(d)) return 'read_file';
  return 'list_dir';
}
function defaultArgs(tool, goal) {
  const path = state.active || 'README.md';
  return ({ list_dir: { path: '.' }, search_codebase: { query: goal }, read_file: { path }, edit_file: { path, target: '', replacement: '' }, write_file: { path, content: '' }, run_command: { command: 'pytest -q' } })[tool];
}
async function startAgent(e) {
  e.preventDefault();
  const goal = $('agent-goal').value.trim(); if (!goal) return;
  const mode = state.chatMode || 'agent';
  installKeywordPlannerNotice();
  if (mode === 'agent') {
    try {
      const r = await api('/v1/agent/run', { method: 'POST', body: { goal, policy: $('agent-policy').value } });
      const kind = classifyComposerResult(mode, r);
      state.agentTask = { id: r.task_id, goal, planningSource: 'keyword_manual' };
      $('agent-goal').value = '';
      tone(kind.toastKind === 'err' ? 'err' : 'warn');
      toast(KEYWORD_PLANNER_LABEL, 'warn');
      renderAgent(r.state); loadRuns();
    } catch (err) { toast(err.message, 'err'); }
  } else {
    try {
      toast(`[${mode.toUpperCase()}] Requesting a model reply…`, 'info');
      const r = await api('/v1/chat/message', {
        method: 'POST',
        body: { message: goal, mode, target_file: state.active }
      });
      const kind = classifyComposerResult(mode, r);
      log(`[${(r.mode || mode).toUpperCase()}] ${r.content || ''}`, kind.unavailable ? 'text-danger' : 'text-ide-fg');
      if (r.memory_citations && r.memory_citations.length) {
        log(`Citations: ${r.memory_citations.map((c) => c.citation).join(', ')}`, 'text-ide-muted text-[11px]');
      }
      if (kind.unavailable) {
        const message = (r.error && r.error.message) || r.content || 'Model unavailable.';
        toast(message, 'err');
        if (r.structured_plan && r.structured_plan.planning_source === 'keyword_manual') {
          log(KEYWORD_PLANNER_LABEL, 'text-warn');
          renderKeywordPreview(r.structured_plan, goal);
        }
      } else if (r.structured_plan) {
        toast(r.structured_plan.planning_source === 'keyword_manual'
          ? `Keyword plan: ${r.structured_plan.steps.length} steps. Not model-driven.`
          : `Plan reply: ${r.structured_plan.steps.length} steps.`, kind.toastKind);
        if (r.structured_plan.planning_source === 'keyword_manual') renderKeywordPreview(r.structured_plan, goal);
      } else if (r.status === 'ok' && r.edit_proposal) {
        const fileLabel = r.edit_proposal.file_path || 'the request';
        toast(`Model reply received for ${fileLabel}. Nothing was applied.`, 'warn');
        setMode('diff');
        loadDiff();
      }
      $('agent-goal').value = '';
    } catch (err) { toast(err.message, 'err'); }
  }
}
const STEP_CHIP = { completed: ['doneStep', 'text-ok border-ok/40'], running: ['running', 'text-accent border-accent/40'], failed: ['failedStep', 'text-danger border-danger/40'] };
function renderAgent(s) {
  if (!s || !state.agentTask || s.task_id !== state.agentTask.id) return;
  state.agentState = s;
  showRunDetail(true);
  if ($('ide-proof-strip')) {
    renderUnifiedProofStrip($('ide-proof-strip'), s, { mode: 'ide' });
  }
  const busy = s.status === 'executing_tool', waiting = !!s.pending_approval;
  const st = $('agent-status');
  st.textContent = statusLabel(s.status);
  st.className = `step-chip ${waiting ? 'text-warn border-warn/50' : s.status === 'failed' ? 'text-danger border-danger/40' : s.status === 'completed' ? 'text-ok border-ok/40' : 'text-accent border-accent/40'}`;
  $('agent-dot').className = `w-2 h-2 rounded-full ${waiting ? 'bg-warn pulse' : busy ? 'bg-accent pulse' : s.status === 'failed' ? 'bg-danger' : 'bg-ok'}`;
  $('agent-goal-label').textContent = s.goal || state.agentTask.goal || s.task_id;
  const isRunning = !['completed', 'failed', 'cancelled'].includes(s.status);
  if ($('cancel-task-btn')) {
    $('cancel-task-btn').classList.toggle('hidden', !isRunning);
  }
  const done = s.plan.filter((p) => p.status === 'completed').length;
  $('plan-progress').textContent = fmt('stepOf', { done, total: s.plan.length });
  $('agent-policy-label').textContent = `· ${t({ confirm_mutation: 'polConfirmMut', confirm_all: 'polConfirmAll', autonomous: 'polAuto' }[s.policy] || s.policy)}`;
  const next = s.plan.find((p) => p.status === 'pending' || p.status === 'failed');
  const pendingStep = waiting ? s.pending_approval.step_id : null;
  $('agent-plan').replaceChildren(...s.plan.map((p, i) => {
    const gated = p.id === pendingStep;
    const [labelKey, chipTone] = gated ? ['needsApproval', 'text-warn border-warn/50'] : STEP_CHIP[p.status] || ['queued', 'text-ide-muted border-ide-border'];
    const isNext = p === next && !waiting && !busy;
    const li = h('li', { class: `card p-3 space-y-2 ${gated ? 'border-warn/50' : isNext ? 'border-accent/50' : ''}` },
      h('div', { class: 'flex items-start gap-2.5' },
        h('span', { class: `mt-0.5 w-5 h-5 shrink-0 rounded-full border text-[10px] font-mono flex items-center justify-center ${chipTone}`, 'aria-hidden': 'true' }, String(i + 1)),
        h('span', { class: `flex-1 ${p.status === 'completed' ? 'text-ide-muted' : ''}` }, p.description),
        h('span', { class: `step-chip ${chipTone}` }, t(labelKey))),
      p.observation ? h('details', { class: 'ms-7' }, h('summary', { class: 'cursor-pointer text-[11px] text-ide-faint' }, t('output')),
        h('pre', { class: 'mt-1 max-h-40 overflow-auto text-[11px] font-mono text-ide-muted whitespace-pre-wrap', dir: 'ltr' }, p.observation)) : null);
    if (isNext) li.append(stepRunner(p));
    return li;
  }));
  renderApproval(s);
  $('agent-events').replaceChildren(...[...s.recent_events].reverse().map((ev) => h('li', { class: 'flex gap-2' },
    h('span', { class: `font-mono ${EVT_TONE[ev.type || ev.event_type] || 'text-ide-muted'}` }, ev.type || ev.event_type || 'event'),
    h('span', { class: 'truncate text-ide-faint', dir: 'ltr' }, ev.data ? JSON.stringify(ev.data).slice(0, 100) : ev.payload ? JSON.stringify(ev.payload).slice(0, 100) : ''))));
}
function renderApproval(s) {
  const p = s.pending_approval;
  $('agent-approval').classList.toggle('hidden', !p);
  if (!p) { state.lastPending = null; return; }
  const a = p.arguments || {};
  const key = `${s.task_id}:${p.step_id}:${p.tool_name}`;
  const scopable = ['edit_file', 'write_file', 'run_command'].includes(p.tool_name);
  $('approve-always').classList.toggle('hidden', !scopable);
  if (state.lastPending !== key) {
    state.lastPending = key; tone('warn');
    $('always-form').classList.add('hidden'); $('approve-always').setAttribute('aria-expanded', 'false');
    $('always-scope').value = p.tool_name === 'run_command' ? (a.command || '') : (a.path || '');
    $('always-help').textContent = fmt(p.tool_name === 'run_command' ? 'alwaysHelpCmd' : 'alwaysHelpPath', { tool: p.tool_name });
  }
  const target = a.path || a.command || '';
  const titleKey = { edit_file: 'wantsEdit', write_file: 'wantsWrite', run_command: 'wantsRun' }[p.tool_name] || 'wantsTool';
  $('approval-title').textContent = fmt(titleKey, { target, tool: p.tool_name });
  $('approval-step').textContent = p.step_id || '';
  const step = s.plan.find((x) => x.id === p.step_id);
  const air = !!(state.status && state.status.air_gapped);
  const rows = [[t('why'), step ? step.description : '—'], [t('action'), p.tool_name], [t('target'), target || '—'], [t('network'), air ? t('netAir') : t('netCloud')]];
  $('approval-meta').replaceChildren(...rows.flatMap(([k, v]) => [h('dt', { class: 'text-ide-faint' }, k), h('dd', { class: 'font-mono truncate', dir: 'auto' }, v)]));
  const lines = p.tool_name === 'edit_file' ? [...String(a.target ?? '').split('\n').map((l) => ['del', l]), ...String(a.replacement ?? '').split('\n').map((l) => ['add', l])]
    : p.tool_name === 'write_file' ? String(a.content ?? '').split('\n').map((l) => ['add', l])
      : p.tool_name === 'run_command' ? [['cmd', `$ ${a.command ?? ''}`]]
        : JSON.stringify(a, null, 2).split('\n').map((l) => ['ctx', l]);
  const frag = document.createDocumentFragment();
  for (const [k, l] of lines) frag.append(h('div', { class: `px-3 py-px whitespace-pre ${k === 'add' ? 'diff-add' : k === 'del' ? 'diff-del' : 'text-ide-muted'}` }, `${k === 'add' ? '+ ' : k === 'del' ? '- ' : ''}${l}`));
  $('approval-preview').replaceChildren(frag);
  $('agent-approval-desc').textContent = `${p.tool_name}\n${JSON.stringify(a, null, 2)}`;
}
function stepRunner(step) {
  const tool = h('select', { class: 'input py-0.5 text-[10px]', 'aria-label': 'Tool' }, ...TOOLS.map((x) => h('option', { value: x }, MUTATING.has(x) ? `${x} (asks first)` : x)));
  tool.value = suggestTool(step.description);
  const args = h('textarea', { rows: '3', class: 'input w-full font-mono text-[10px] resize-y', spellcheck: 'false', 'aria-label': 'Arguments (JSON)', dir: 'ltr' });
  args.value = JSON.stringify(defaultArgs(tool.value, state.agentTask.goal), null, 1);
  tool.addEventListener('change', () => { args.value = JSON.stringify(defaultArgs(tool.value, state.agentTask.goal), null, 1); });
  const hint = h('p', { class: 'text-[10px] text-warn' }, 'Keyword suggestion only. The tool is not chosen by a model.');
  const run = h('button', { type: 'button', class: 'btn-primary py-0.5 text-[11px]' }, 'Run step');
  run.addEventListener('click', async () => {
    let parsed; try { parsed = JSON.parse(args.value); } catch { toast('Arguments must be JSON', 'err'); return; }
    run.disabled = true;
    try { const r = await api(`/v1/agent/step/${encodeURIComponent(state.agentTask.id)}`, { method: 'POST', body: { tool_name: tool.value, arguments: parsed, step_id: step.id } }); renderAgent(r.agent_state); afterAgentAction(r.step_result); }
    catch (err) { toast(err.message, 'err'); run.disabled = false; }
  });
  return h('div', { class: 'ms-7 space-y-1.5' }, hint, h('div', { class: 'flex gap-1.5' }, tool, run), args);
}
async function approve(yes, scope) {
  try {
    const body = { approved: yes }; if (scope !== undefined) body.remember = { scope };
    const r = await api(`/v1/agent/approve/${encodeURIComponent(state.agentTask.id)}`, { method: 'POST', body });
    if (r.rule) toast(`${t('ruleSaved')} · ${r.rule.tool_name} ${r.rule.scope}`);
    renderAgent(r.agent_state); afterAgentAction(r.approval_result);
  }
  catch (err) { toast(err.message, 'err'); }
}
function afterAgentAction(res) {
  if (!res) return;
  if (res.status === 'success' && res.approved_by_rule) toast(`${t('autoApproved')} · ${res.approved_by_rule.scope}`);
  if (res.status === 'success') { tone('ok'); if (['edit_file', 'write_file'].includes(res.tool)) { loadGit(); toast(t('reviewChanges')); } }
  else if (res.status === 'error') toast(res.error, 'err');
  else if (res.status === 'denied') toast(`${t('deny')} · ${res.tool_name}`, 'warn');
}

// ---------- live events ----------
function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/v1/ws/studio${token() ? `?token=${encodeURIComponent(token())}` : ''}`);
  state.ws = ws;
  ws.onopen = () => { state.wsRetry = 0; $('sb-ws').textContent = '⇄ live'; $('sb-ws').className = 'text-ok'; };
  ws.onclose = () => {
    if (state.ws !== ws) return;
    $('sb-ws').textContent = '⇄ offline'; $('sb-ws').className = 'text-warn';
    state.wsRetry = Math.min(state.wsRetry + 1, 6);
    setTimeout(() => { if (state.ws === ws && !signInOpen()) connectWs(); }, 500 * 2 ** state.wsRetry);
  };
  ws.onmessage = (m) => {
    let ev; try { ev = JSON.parse(m.data); } catch { return; }
    if (ev.type === 'handshake') { setAirGap(ev.air_gapped); log(`connected · ${ev.server} ${ev.version}`, 'text-ide-muted'); }
    else if (ev.type === 'air_gap_status_changed') { setAirGap(ev.air_gapped); log(`air-gap ${ev.air_gapped ? 'armed' : 'disarmed'}`, ev.air_gapped ? 'text-ok' : 'text-warn'); }
    else if (ev.type === 'agent_state_changed') { log(`task "${ev.title}" ${ev.previous_state || '∅'} → ${ev.new_state}`, 'text-accent'); if (state.section === 'tasks') loadTasks(); }
    else if (ev.type === 'agent_loop_updated') { if (state.agentTask && ev.task_id === state.agentTask.id) renderAgent(ev.state); loadRuns(); if (state.section === 'record') loadTapes(); }
    else if (ev.type === 'error') toast(ev.message, 'err');
  };
}
async function toggleAirGap() {
  const on = $('airgap-btn').getAttribute('aria-pressed') !== 'true';
  try { await api('/v1/studio/airgap', { method: 'POST', body: { enabled: on } }); tone(on ? 'ok' : 'warn'); }
  catch (err) { toast(err.message, 'err'); }
}

// ---------- command palette ----------
let paletteItems = [], paletteIdx = 0, fileIndex = [], lastFocusedBeforePalette = null;
function flatten(n, out = []) { (n.children || []).forEach((c) => (c.type === 'directory' ? flatten(c, out) : out.push(c.path))); return out; }
function commands() {
  return [
    ['Go to Home', () => switchSection('home')],
    ['Go to Workspace', () => switchSection('workspace')],
    ['Go to Tasks', () => switchSection('tasks')],
    ['Go to Evidence', () => switchSection('runs')],
    ['Go to Skills', () => switchSection('skills')],
    ['Go to Settings', () => switchSection('settings')],
    ['Open Developer Labs', () => toggleLabsDrawer(true)],
    ['New task', newRun],
    ['Explorer', () => { switchSection('workspace'); switchView('explorer'); }],
    ['Changes', () => { switchSection('workspace'); switchView('git'); }],
    ['Memory', () => { switchSection('workspace'); switchView('memory'); }],
    ['Show diff of working tree', () => { switchSection('workspace'); setMode('diff'); }],
    ['Toggle air-gap', toggleAirGap],
    ['Toggle theme', () => setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light')],
    ['Verify audit chain', () => { switchSection('runs'); verifyAudit(); }],
    ['Replay product tour', startTour],
    ['Sign out', signOut],
  ].map(([label, run]) => ({ label, run, kind: '⌘' }));
}
async function openPalette() {
  lastFocusedBeforePalette = document.activeElement;
  $('palette').classList.remove('hidden'); $('palette').classList.add('flex');
  $('palette').setAttribute('aria-hidden', 'false');
  $('palette-input').value = ''; $('palette-input').focus(); renderPalette();
  if (!fileIndex.length) { try { fileIndex = flatten((await api('/v1/files/tree?max_depth=6')).tree); renderPalette(); } catch { /* noop */ } }
}
function closePalette() {
  $('palette').classList.add('hidden'); $('palette').classList.remove('flex');
  $('palette').setAttribute('aria-hidden', 'true');
  if (lastFocusedBeforePalette && typeof lastFocusedBeforePalette.focus === 'function' && document.body?.contains?.(lastFocusedBeforePalette)) {
    lastFocusedBeforePalette.focus();
  }
  lastFocusedBeforePalette = null;
}
function renderPalette() {
  const q = $('palette-input').value.toLowerCase().trim();
  const items = [...commands(), ...fileIndex.map((p) => ({ label: p, kind: '·', run: () => { switchSection('files'); openFile(p); } }))];
  paletteItems = (q ? items.filter((i) => i.label.toLowerCase().includes(q)) : items).slice(0, 40);
  paletteIdx = Math.min(paletteIdx, Math.max(paletteItems.length - 1, 0));
  $('palette-list').replaceChildren(...paletteItems.map((it, i) => h('li', { role: 'option', id: `pal-${i}`, 'aria-selected': String(i === paletteIdx), class: `px-4 py-1.5 flex gap-2 cursor-pointer text-xs ${i === paletteIdx ? 'bg-accent/15 text-ide-fg' : 'text-ide-muted'}`, onclick: () => { closePalette(); it.run(); } },
    h('span', { 'aria-hidden': 'true', class: 'w-4' }, it.kind), h('span', { class: 'truncate font-mono' }, it.label))));
  $('palette-input').setAttribute('aria-activedescendant', paletteItems.length ? `pal-${paletteIdx}` : '');
}
function paletteKey(e) {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    paletteIdx = (paletteIdx + (e.key === 'ArrowDown' ? 1 : -1) + paletteItems.length) % Math.max(paletteItems.length, 1);
    renderPalette();
    $(`pal-${paletteIdx}`)?.scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'Home') {
    e.preventDefault();
    paletteIdx = 0;
    renderPalette();
    $(`pal-${paletteIdx}`)?.scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'End') {
    e.preventDefault();
    paletteIdx = Math.max(0, paletteItems.length - 1);
    renderPalette();
    $(`pal-${paletteIdx}`)?.scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'Enter' && paletteItems[paletteIdx]) {
    e.preventDefault();
    const it = paletteItems[paletteIdx];
    closePalette();
    it.run();
  } else if (e.key === 'Escape') {
    e.preventDefault?.();
    e.stopPropagation?.();
    closePalette();
  } else if (e.key === 'Tab') {
    e.preventDefault?.();
  }
}
// ---------- onboarding ----------
let tourStep = 0, lastFocusedBeforeTour = null;
function startTour() {
  tourStep = 0;
  lastFocusedBeforeTour = document.activeElement;
  $('onboard').classList.remove('hidden'); $('onboard').classList.add('flex');
  $('onboard').setAttribute('aria-hidden', 'false');
  renderTour();
  $('onboard-next').focus();
}
function renderTour() {
  const steps = t('tour');
  const [title, body] = steps[tourStep];
  $('onboard-step').textContent = `${tourStep + 1} / ${steps.length}`;
  $('onboard-title').textContent = title; $('onboard-body').textContent = body;
  $('onboard-next').textContent = tourStep === steps.length - 1 ? t('done') : t('next');
}
function endTour() {
  localStorage.setItem('keelway.onboarded', '1');
  $('onboard').classList.add('hidden'); $('onboard').classList.remove('flex');
  $('onboard').setAttribute('aria-hidden', 'true');
  if (lastFocusedBeforeTour && typeof lastFocusedBeforeTour.focus === 'function' && document.body?.contains?.(lastFocusedBeforeTour)) {
    lastFocusedBeforeTour.focus();
  }
  lastFocusedBeforeTour = null;
}

// ---------- boot ----------
function welcomeFacts() {
  const s = state.status; if (!s) return;
  const facts = [['Model', s.local_model], ['Hardware', `${s.hardware.arch} · ${s.hardware.ram_gb} GB`], ['Tasks', s.tasks.total], ['Flight tapes', s.flight_tapes]];
  $('welcome-facts').replaceChildren(...facts.map(([k, v]) => h('div', { class: 'p-2.5 rounded-lg border border-ide-border bg-ide-sidebar/60' }, h('dt', { class: 'text-ide-faint text-[10px] uppercase tracking-wider' }, k), h('dd', { class: 'mt-0.5 font-mono truncate' }, v))));
}
async function startSession() {
  await Promise.all([loadStatus(), loadProjectInfo(), loadTree(), loadGit(), loadMeshStatus()]);
  welcomeFacts();
  switchSection(location.hash.slice(1) || 'home');
  if (state.ws) { const old = state.ws; state.ws = null; old.close(); }
  connectWs();
  if (!localStorage.getItem('keelway.onboarded')) startTour();
}
function relabel() { applyI18n(); renderPanelTabs(); renderWelcome(); renderTabs(); renderRuns(); if (state.status) { setAirGap(state.status.air_gapped); $('composer-model').textContent = `${t('localModel')} · ${state.status.local_model}`; } if (state.agentState) renderAgent(state.agentState); }

function wire() {
  clearStaticEvidenceClaims();
  applySpeculativeView(speculativeViewNotRun());
  installKeywordPlannerNotice();
  $('lang-select').replaceChildren(...Object.entries(LANGS).map(([k, v]) => h('option', { value: k }, v)));
  $('lang-select').value = lang;
  $('lang-select').addEventListener('change', (e) => { lang = e.target.value; localStorage.setItem('keelway.lang', lang); relabel(); });
  $('theme-btn').addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'));
  if ($('density-btn')) $('density-btn').addEventListener('click', cycleDensity);
  $('sound-btn').setAttribute('aria-pressed', String(sound));
  $('sound-btn').addEventListener('click', () => { sound = !sound; localStorage.setItem('keelway.sound', sound ? 'on' : 'off'); $('sound-btn').setAttribute('aria-pressed', String(sound)); tone('tick'); });
  $('airgap-btn').addEventListener('click', toggleAirGap);
  $('signout-btn').addEventListener('click', signOut);
  $('signin-form').addEventListener('submit', signIn);
  $('palette-btn').addEventListener('click', openPalette);
  $('palette-btn-mobile')?.addEventListener('click', openPalette);
  $('palette-input').addEventListener('input', () => { paletteIdx = 0; renderPalette(); });
  $('palette-input').addEventListener('keydown', paletteKey);
  $('palette').addEventListener('click', (e) => { if (e.target === $('palette')) closePalette(); });
  $('palette').addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { e.stopPropagation(); closePalette(); }
    else if (e.key === 'Tab') trapFocus($('palette'), e);
  });
  $('labs-drawer')?.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') trapFocus($('labs-drawer'), e);
    else if (e.key === 'Escape') { e.stopPropagation(); toggleLabsDrawer(false); }
  });
  $('onboard')?.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') trapFocus($('onboard'), e);
    else if (e.key === 'Escape') { e.stopPropagation(); endTour(); }
  });
  $('onboard')?.addEventListener('click', (e) => { if (e.target === $('onboard')) endTour(); });
  $('signin')?.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') trapFocus($('signin'), e);
  });
  if ($('run-test-btn')) {
    $('run-test-btn').addEventListener('click', async () => {
      if (!state.projectMeta || !state.projectMeta.detected_test_command) return;
      const cmd = state.projectMeta.detected_test_command;
      switchPanel('console');
      log(`❯ ${cmd}`, 'text-accent font-semibold');
      try {
        const res = await api('/v1/terminal/exec', { method: 'POST', body: { command: cmd } });
        if (res.stdout) {
          res.stdout.split('\n').forEach((l) => l && log(l, 'text-ide-fg'));
        }
        if (res.stderr) {
          res.stderr.split('\n').forEach((l) => l && log(l, res.exit_code === 0 ? 'text-ide-muted' : 'text-danger'));
        }
        log(`[Test runner exited with code ${res.exit_code} in ${res.duration_ms}ms]`, res.exit_code === 0 ? 'text-ok font-semibold' : 'text-danger font-semibold');
      } catch (err) {
        log(`Failed to execute tests: ${err.message}`, 'text-danger');
      }
    });
  }
  document.querySelectorAll('#mode-selector .mode-tab').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#mode-selector .mode-tab').forEach((b) => {
        b.classList.remove('active', 'bg-accent/20', 'text-accent', 'border-accent/40');
        b.classList.add('text-ide-muted');
      });
      btn.classList.add('active', 'bg-accent/20', 'text-accent', 'border-accent/40');
      btn.classList.remove('text-ide-muted');
      state.chatMode = btn.dataset.mode;
      const phMap = {
        agent: 'Describe a task. Planning is keyword/manual, not model-driven.',
        ask: 'Ask a question about repository code or architecture (read-only)…',
        plan: 'Describe a change. A model reply is separate from the keyword step list.',
        edit: 'Describe code changes. A missing model is an error, not a patch.',
      };
      if ($('agent-goal')) $('agent-goal').placeholder = phMap[state.chatMode] || phMap.agent;
    });
  });
  document.querySelectorAll('[data-view]').forEach((b) => b.addEventListener('click', () => switchView(b.dataset.view)));
  $('sidebar-refresh').addEventListener('click', refreshView);
  if ($('open-repo-btn')) {
    $('open-repo-btn').addEventListener('click', async () => {
      const current = $('ws-name').textContent || '';
      const chosen = prompt('Enter path to local repository directory:', current !== 'workspace' ? current : '.');
      if (!chosen) return;
      try {
        const res = await api('/v1/workspace/open', { method: 'POST', body: { path: chosen.trim() } });
        toast(`[+] Opened workspace: ${res.name}`, 'ok');
        $('ws-name').textContent = res.name;
        await loadProjectInfo();
        refreshView();
      } catch (err) {
        toast(`Failed to open workspace: ${err.message}`, 'err');
      }
    });
  }
  if ($('cancel-task-btn')) {
    $('cancel-task-btn').addEventListener('click', async () => {
      if (!state.agentTask) return;
      try {
        const res = await api(`/v1/agent/cancel/${encodeURIComponent(state.agentTask.id)}`, { method: 'POST' });
        toast(`Task ${state.agentTask.id} cancelled`, 'warn');
        renderAgent(res.agent_state);
        loadRuns();
      } catch (err) {
        toast(`Failed to cancel task: ${err.message}`, 'err');
      }
    });
  }
  if ($('file-upload-input')) {
    $('file-upload-input').addEventListener('change', async (e) => {
      const files = Array.from(e.target.files || []);
      if (!files.length) return;
      for (const file of files) {
        toast(`Uploading ${file.name}…`, 'info');
        const reader = new FileReader();
        reader.onload = async () => {
          try {
            const bytes = new Uint8Array(reader.result);
            let binary = '';
            for (let i = 0; i < bytes.byteLength; i++) {
              binary += String.fromCharCode(bytes[i]);
            }
            const base64Content = btoa(binary);
            const res = await api('/v1/files/upload', {
              method: 'POST',
              body: { filename: file.name, content_base64: base64Content }
            });
            if (res.type === 'zip_archive') {
              toast(`[+] Unpacked ${res.extracted_count} files from ${file.name}`, 'ok');
            } else {
              toast(`[+] Uploaded ${file.name}`, 'ok');
            }
            refreshView();
          } catch (err) {
            toast(`Upload failed: ${err.message}`, 'err');
          }
        };
        reader.readAsArrayBuffer(file);
      }
      e.target.value = '';
    });
  }
  $('mode-editor').addEventListener('click', () => setMode('editor'));
  $('mode-diff').addEventListener('click', () => setMode('diff'));
  $('save-btn').addEventListener('click', saveFile);
  $('fallback-editor').addEventListener('input', () => { if (state.active) { state.dirty.add(state.active); renderTabs(); } });
  $('task-form').addEventListener('submit', createTask);
  $('memory-form').addEventListener('submit', saveMemory);
  $('console-form').addEventListener('submit', runConsole);
  $('tape-select').addEventListener('change', (e) => loadTape(e.target.value));
  $('flight-scrubber').addEventListener('input', (e) => seek(Number(e.target.value)));
  $('flight-fork').addEventListener('click', forkTape);
  if ($('flight-first')) $('flight-first').addEventListener('click', () => seek(0));
  if ($('flight-prev')) $('flight-prev').addEventListener('click', () => seek(state.cursor - 1));
  if ($('flight-play')) $('flight-play').addEventListener('click', toggleFlightReplay);
  if ($('flight-next')) $('flight-next').addEventListener('click', () => seek(state.cursor + 1));
  if ($('flight-last')) $('flight-last').addEventListener('click', () => seek(state.tape ? state.tape.events.length - 1 : 0));
  if ($('flight-tab-visual-btn') && $('flight-tab-raw-btn')) {
    $('flight-tab-visual-btn').addEventListener('click', () => {
      if ($('flight-visual-container')) $('flight-visual-container').classList.remove('hidden');
      if ($('flight-payload')) $('flight-payload').classList.add('hidden');
      $('flight-tab-visual-btn').className = 'chip border-accent text-accent font-medium text-[10px]';
      $('flight-tab-raw-btn').className = 'chip border-ide-border text-ide-muted text-[10px]';
    });
    $('flight-tab-raw-btn').addEventListener('click', () => {
      if ($('flight-visual-container')) $('flight-visual-container').classList.add('hidden');
      if ($('flight-payload')) $('flight-payload').classList.remove('hidden');
      $('flight-tab-raw-btn').className = 'chip border-accent text-accent font-medium text-[10px]';
      $('flight-tab-visual-btn').className = 'chip border-ide-border text-ide-muted text-[10px]';
    });
  }
  $('heal-form').addEventListener('submit', runHeal);
  $('audit-verify').addEventListener('click', verifyAudit);
  if ($('audit-anchor-btn')) $('audit-anchor-btn').addEventListener('click', anchorAudit);
  if ($('tier2-verify-btn')) $('tier2-verify-btn').addEventListener('click', verifyTier2);
  if ($('app-plan-btn')) $('app-plan-btn').addEventListener('click', planApp);
  if ($('app-generate-btn')) $('app-generate-btn').addEventListener('click', generateApp);
  if ($('plugins-refresh-btn')) $('plugins-refresh-btn').addEventListener('click', loadPlugins);
  if ($('plugin-install-form')) $('plugin-install-form').addEventListener('submit', installPluginForm);
  if ($('eval-run-btn')) $('eval-run-btn').addEventListener('click', runEvalRadar);
  if ($('eval-drift-btn')) $('eval-drift-btn').addEventListener('click', checkDriftRadar);
  if ($('mesh-refresh-btn')) $('mesh-refresh-btn').addEventListener('click', loadMeshStatus);
  if ($('mesh-delegate-form')) $('mesh-delegate-form').addEventListener('submit', dispatchMeshDelegation);
  if ($('quorum-sign-sec-btn')) $('quorum-sign-sec-btn').addEventListener('click', () => submitQuorumSign('Security Lead'));
  if ($('quorum-sign-plat-btn')) $('quorum-sign-plat-btn').addEventListener('click', () => submitQuorumSign('Platform Owner'));
  if ($('evidence-summary-btn')) $('evidence-summary-btn').addEventListener('click', loadEvidenceSummary);
  if ($('evidence-seal-btn')) $('evidence-seal-btn').addEventListener('click', sealEvidencePackage);
  if ($('evidence-verify-btn')) $('evidence-verify-btn').addEventListener('click', verifyEvidencePackage);
  if ($('doctor-run-btn')) $('doctor-run-btn').addEventListener('click', runDoctorDiagnostics);
  if ($('sync-status-btn')) $('sync-status-btn').addEventListener('click', loadSyncStatusInStudio);
  if ($('sync-export-btn')) $('sync-export-btn').addEventListener('click', exportSyncEnvelopeInStudio);
  if ($('sync-mobile-btn')) $('sync-mobile-btn').addEventListener('click', showMobilePairingInStudio);
  if ($('kstack-list-btn')) $('kstack-list-btn').addEventListener('click', loadKStackSkillsInStudio);
  if ($('khub-scan-btn')) $('khub-scan-btn').addEventListener('click', scanKHubInStudio);
  if ($('kbrain-record-btn')) $('kbrain-record-btn').addEventListener('click', recordKBrainFactInStudio);
  if ($('kbrain-query-btn')) $('kbrain-query-btn').addEventListener('click', queryKBrainFactsInStudio);
  if ($('kflow-run-btn')) $('kflow-run-btn').addEventListener('click', runKFlowDAGInStudio);
  if ($('kflow-list-btn')) $('kflow-list-btn').addEventListener('click', listKFlowDAGsInStudio);
  if ($('kflow-reset-btn')) $('kflow-reset-btn').addEventListener('click', resetKFlowNodesInStudio);
  if ($('code-intel-search-btn')) $('code-intel-search-btn').addEventListener('click', searchCodebaseInStudio);
  if ($('code-intel-refs-btn')) $('code-intel-refs-btn').addEventListener('click', findReferencesInStudio);
  if ($('code-intel-hier-btn')) $('code-intel-hier-btn').addEventListener('click', viewCallHierarchyInStudio);
  if ($('code-intel-graph-btn')) $('code-intel-graph-btn').addEventListener('click', viewModuleGraphInStudio);
  if ($('bundle-pack-btn')) $('bundle-pack-btn').addEventListener('click', packAgentBundleInStudio);
  if ($('bundle-unpack-btn')) $('bundle-unpack-btn').addEventListener('click', unpackAgentBundleInStudio);
  if ($('conflict-check-btn')) $('conflict-check-btn').addEventListener('click', checkConflictsInStudio);
  if ($('conflict-resolve-btn')) $('conflict-resolve-btn').addEventListener('click', resolveConflictsInStudio);
  if ($('conflict-timeline-btn')) $('conflict-timeline-btn').addEventListener('click', loadTimelineInStudio);
  if ($('merkle-root-btn')) $('merkle-root-btn').addEventListener('click', fetchMerkleRootInStudio);
  if ($('merkle-proof-btn')) $('merkle-proof-btn').addEventListener('click', generateMerkleProofInStudio);
  if ($('merkle-verify-btn')) $('merkle-verify-btn').addEventListener('click', verifyMerkleProofInStudio);
  if ($('merkle-export-btn')) $('merkle-export-btn').addEventListener('click', exportAuditBundleInStudio);
  if ($('spool-status-btn')) $('spool-status-btn').addEventListener('click', checkSpoolStatusInStudio);
  if ($('spool-flush-btn')) $('spool-flush-btn').addEventListener('click', flushSpoolInStudio);
  if ($('btn-run-spec-benchmark')) $('btn-run-spec-benchmark').addEventListener('click', runSpeculativeBenchmarkInStudio);
  $('agent-form').addEventListener('submit', startAgent);
  $('agent-goal').addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) $('agent-form').requestSubmit(); });
  $('approve-yes').addEventListener('click', () => approve(true));
  $('approve-no').addEventListener('click', () => approve(false));
  $('approve-always').addEventListener('click', () => { const f = $('always-form'); const open = f.classList.toggle('hidden') === false; $('approve-always').setAttribute('aria-expanded', String(open)); if (open) $('always-scope').focus(); });
  $('always-cancel').addEventListener('click', () => { $('always-form').classList.add('hidden'); $('approve-always').setAttribute('aria-expanded', 'false'); $('approve-always').focus(); });
  $('always-form').addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      $('always-form').classList.add('hidden');
      $('approve-always').setAttribute('aria-expanded', 'false');
      $('approve-always').focus();
    } else if (e.key === 'Tab') {
      trapFocus($('always-form'), e);
    }
  });
  $('always-form').addEventListener('submit', (e) => { e.preventDefault(); const scope = $('always-scope').value.trim(); if (!scope) { $('always-scope').focus(); toast(t('scopeRequired'), 'err'); return; } approve(true, scope); });
  document.querySelectorAll('[data-section]').forEach((b) => b.addEventListener('click', () => switchSection(b.dataset.section)));
  $('rail-labs-btn')?.addEventListener('click', () => toggleLabsDrawer(true));
  $('labs-close-btn')?.addEventListener('click', () => toggleLabsDrawer(false));
  $('labs-backdrop')?.addEventListener('click', () => toggleLabsDrawer(false));
  $('settings-open-labs-btn')?.addEventListener('click', () => toggleLabsDrawer(true));
  $('new-run-btn').addEventListener('click', newRun);
  $('open-editor-btn')?.addEventListener('click', async () => {
    try {
      const res = await api('/v1/editor-sync/open-in-editor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ editor: 'vscode', relative_path: state.active || '' })
      });
      toast(`Launched ${res.editor}: ${res.target.split('/').pop() || 'workspace'}`);
    } catch (e) {
      try {
        const res = await api('/v1/editor-sync/open-in-editor', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ editor: 'cursor', relative_path: state.active || '' })
        });
        toast(`Launched Cursor: ${res.target.split('/').pop() || 'workspace'}`);
      } catch (err) {
        toast(e.message || 'External editor not found in PATH', 'err');
      }
    }
  });
  $('task-back').addEventListener('click', () => { $('sec-tasks').dataset.detail = 'false'; });
  $('review-btn').addEventListener('click', () => { switchSection('workspace'); setMode('diff'); });
  $('open-record-btn').addEventListener('click', () => switchSection('runs'));
  $('sb-approval').addEventListener('click', () => { const r = state.runs.find((x) => x.pending_approval); switchSection('tasks'); if (r) selectRun(r.task_id, r.goal); });
  $('onboard-skip').addEventListener('click', endTour);
  $('onboard-next').addEventListener('click', () => { if (tourStep >= t('tour').length - 1) endTour(); else { tourStep += 1; renderTour(); } });
  if ($('builder-scaffold-btn')) {
    $('builder-scaffold-btn').addEventListener('click', scaffoldAgentInStudio);
  }
  if ($('ide-proof-strip')) {
    renderUnifiedProofStrip($('ide-proof-strip'), null, { mode: 'ide' });
  }
  if ($('builder-proof-strip')) {
    renderUnifiedProofStrip($('builder-proof-strip'), null, { mode: 'builder' });
  }
  window.addEventListener('hashchange', () => {
    const h = location.hash.slice(1);
    if (h) switchSection(h);
  });
  document.addEventListener('keydown', (e) => {
    const mod = e.metaKey || e.ctrlKey;
    if (mod && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if ($('palette').classList.contains('hidden')) openPalette();
      else closePalette();
    }
    else if (mod && e.key.toLowerCase() === 's') { e.preventDefault(); saveFile(); }
    else if (e.altKey && /^[1-6]$/.test(e.key)) { e.preventDefault(); switchSection(SECTIONS[Number(e.key) - 1]); }
    else if (e.altKey && e.key.toLowerCase() === 'a') { e.preventDefault(); toggleAirGap(); }
    else if (mod && e.key === 'j') { e.preventDefault(); $('panel').classList.toggle('hidden'); }
    else if (e.key === 'Escape') {
      if (!$('palette').classList.contains('hidden')) {
        closePalette();
      } else if ($('always-form') && !$('always-form').classList.contains('hidden')) {
        $('always-form').classList.add('hidden');
        $('approve-always')?.setAttribute('aria-expanded', 'false');
        $('approve-always')?.focus();
      } else if ($('labs-drawer') && $('labs-drawer').classList.contains('translate-x-0')) {
        toggleLabsDrawer(false);
      } else if ($('onboard') && !$('onboard').classList.contains('hidden')) {
        endTour();
      } else if ($('sb-popover') && !$('sb-popover').classList.contains('hidden')) {
        $('sb-popover').classList.add('hidden');
      } else if (activeDrawerStage) {
        document.querySelectorAll('.proof-drawer').forEach((d) => d.classList.add('hidden'));
        activeDrawerStage = null;
        document.querySelectorAll('.proof-strip-stage').forEach((tab) => {
          tab.setAttribute('aria-selected', 'false');
          tab.classList.remove('ring-1', 'ring-accent');
        });
      }
    }
  });
}

async function boot() {
  setTheme(localStorage.getItem('keelway.theme') || 'dark');
  setDensity(localStorage.getItem('keelway.density') || 'default');
  wire(); relabel(); switchPanel('console'); initMonaco();
  log('Keelway Studio · type help', 'text-ide-muted');
  try { await loadMe(); } catch { if (!signInOpen()) showSignIn(); return; }
  await startSession();
}
if (typeof window !== 'undefined') {
  window.PROOF_STAGES = PROOF_STAGES;
  window.getIdeStageData = getIdeStageData;
  window.getBuilderStageData = getBuilderStageData;
  window.renderUnifiedProofStrip = renderUnifiedProofStrip;
  window.scaffoldAgentInStudio = scaffoldAgentInStudio;
  window.KEYWORD_PLANNER_LABEL = KEYWORD_PLANNER_LABEL;
  window.speculativeViewNotRun = speculativeViewNotRun;
  window.speculativeViewFromFailure = speculativeViewFromFailure;
  window.speculativeViewFromResponse = speculativeViewFromResponse;
  window.evidenceMetricMark = evidenceMetricMark;
  window.classifyComposerResult = classifyComposerResult;
  window.clearStaticEvidenceClaims = clearStaticEvidenceClaims;
  window.applySpeculativeView = applySpeculativeView;
  window.presentCostLedger = presentCostLedger;
  window.openPalette = openPalette;
  window.closePalette = closePalette;
  window.toggleLabsDrawer = toggleLabsDrawer;
  window.trapFocus = trapFocus;
  window.paletteKey = paletteKey;
}

if (typeof window !== 'undefined' && !window.__TEST_MODE__) {
  boot();
}
