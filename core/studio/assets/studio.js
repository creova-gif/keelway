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

// ---------- i18n ----------
const STRINGS = {
  en: { skip: 'Skip to editor', search: 'Search files, symbols and commands', language: 'Language', theme: 'Theme', sounds: 'Sounds', signOut: 'Sign out', views: 'Views', explorer: 'Explorer', changes: 'Changes', tasks: 'Tasks', memory: 'Memory', refresh: 'Refresh', newTask: 'New task', newTaskPh: 'New task…', add: 'Add', rememberPh: 'Remember that…', save: 'Save', openFiles: 'Open files', viewMode: 'View mode', code: 'Code', diff: 'Diff', editor: 'Editor', tagline: 'Local-first · Deterministic · Yours', welcomeTitle: 'Build with agents that never leave your machine.', welcomeBody: 'Every step is recorded, replayable and auditable. Open a file, give the agent a goal, or review what changed.', panel: 'Panel', console: 'Console', flight: 'Flight recorder', healing: 'Self-healing', ledger: 'Ledger', audit: 'Audit', fork: 'Fork here', healWarn: 'Runs the command in this repository. A passing patch is applied to your working tree.', testCommand: 'Test command', attempts: 'Attempts', runRepair: 'Run repair cycle', paySim: 'Simulated: builds a payment payload only. No money moves.', rail: 'Rail', amount: 'Amount', currency: 'Currency', recipient: 'Recipient', buildIntent: 'Build intent', auditHint: 'Every permission decision is appended to a SHA-256 hash chain.', verify: 'Verify chain', agent: 'Keelway agent', idle: 'idle', noGoal: 'No goal yet.', plan: 'Plan', approvalNeeded: 'Approval needed', allow: 'Allow', deny: 'Deny', activity: 'Activity', goal: 'Goal', goalPh: 'Describe a goal for the agent…', polConfirmMut: 'Ask before changes', polConfirmAll: 'Ask before every step', polAuto: 'Autonomous (admin)', start: 'Start', signInTitle: 'Sign in to Keelway', signInBody: 'Open the link printed by keelway dev, or paste a token from keelway token create.', apiToken: 'API token', signIn: 'Sign in', skipTour: 'Skip', next: 'Next', done: 'Get started', airOn: 'Air-gapped', airOff: 'Cloud allowed', clean: 'Working tree clean', noTasks: 'No tasks yet', noMemories: 'No memories yet', noTapes: 'No flight tapes yet', openFile: 'Open a file', giveGoal: 'Give the agent a goal', reviewChanges: 'Review changes', saved: 'Saved', modified: 'Modified', badToken: 'That token was not accepted.',
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

// ---------- theme & sound ----------
function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('keelway.theme', theme);
  if (window.monaco) monaco.editor.setTheme(theme === 'light' ? 'vs' : 'keelwayDark');
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
  $('sb-sent').textContent = on ? 'sent: 0 B' : 'sent: unmeasured';
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
    foot.replaceChildren(...[['RAM', `${s.hardware.ram_gb} GB`], ['CPU', s.hardware.arch], ['Model', s.hardware.recommended_model], ['Tasks', s.tasks.total]].flatMap(([k, v]) => [h('dt', { class: 'text-ide-faint' }, k), h('dd', { class: 'text-end truncate' }, v)]));
  } catch { /* shown via sign-in or status bar */ }
}

function renderWelcome() {
  const acts = [[t('openFile'), () => switchSection('files')], [t('giveGoal'), () => $('agent-goal').focus()], [t('reviewChanges'), () => { switchSection('files'); setMode('diff'); }]];
  $('welcome-actions').replaceChildren(...acts.map(([label, fn]) => h('button', { type: 'button', class: 'btn-outline justify-start h-10', onclick: fn }, label)));
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
const SECTIONS = ['tasks', 'files', 'record', 'labs'];
function switchSection(sec) {
  if (!SECTIONS.includes(sec)) sec = 'tasks';
  state.section = sec;
  SECTIONS.forEach((x) => { const el = $(`sec-${x}`); el.classList.toggle('hidden', x !== sec); el.classList.toggle('flex', x === sec); });
  document.querySelectorAll('[data-section]').forEach((b) => b.setAttribute('aria-current', b.dataset.section === sec ? 'page' : 'false'));
  if (location.hash !== `#${sec}`) history.replaceState(null, '', `#${sec}`);
  if (sec === 'tasks') { loadRuns(); loadTasks(); }
  if (sec === 'files') { refreshView(); if (editor) editor.layout(); }
  if (sec === 'record') { loadTapes(); loadAudit(); verifyAudit(); loadRules(); loadTier2Status(); loadManifestRegistry(); }
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

// ---------- flight recorder ----------
async function loadTapes() {
  try {
    const { tapes } = await api('/v1/flight/tapes');
    state.tapes = tapes.map((x) => x.task_id).sort();
    const sel = $('tape-select');
    sel.replaceChildren(...(state.tapes.length ? state.tapes.map((id) => h('option', { value: id }, id)) : [h('option', { value: '' }, t('noTapes'))]));
    if (state.tapes.length) { const id = state.tapes.includes(state.tapeId) ? state.tapeId : state.tapes[state.tapes.length - 1]; sel.value = id; await loadTape(id); }
    else { $('flight-events').replaceChildren(); $('flight-payload').textContent = ''; }
  } catch { /* noop */ }
}
async function loadTape(id) {
  if (!id) return;
  try {
    state.tape = await api(`/v1/flight/tape/${encodeURIComponent(id)}`); state.tapeId = id;
    const n = state.tape.events.length;
    const sc = $('flight-scrubber'); sc.max = String(Math.max(n - 1, 0)); sc.disabled = n === 0; $('flight-fork').disabled = n === 0;
    seek(n ? n - 1 : 0);
  } catch (err) { toast(err.message, 'err'); }
}
const EVT_TONE = { prompt: 'text-accent', model_response: 'text-ide-fg', tool_call: 'text-warn', tool_result: 'text-ok', state_transition: 'text-ide-muted', approval_requested: 'text-warn', approval_denied: 'text-danger' };
function seek(i) {
  const evs = state.tape ? state.tape.events : [];
  state.cursor = Math.max(0, Math.min(i, evs.length - 1));
  $('flight-scrubber').value = String(state.cursor);
  $('flight-step').textContent = `${evs.length ? state.cursor + 1 : 0} / ${evs.length}`;
  $('flight-events').replaceChildren(...evs.map((ev, idx) => h('li', {}, h('button', { type: 'button', 'aria-current': idx === state.cursor ? 'step' : null, class: `w-full text-start px-2 py-0.5 rounded font-mono text-[11px] ${idx === state.cursor ? 'bg-accent/15' : idx > state.cursor ? 'opacity-40' : ''} ${EVT_TONE[ev.event_type] || ''}`, onclick: () => seek(idx) }, `#${idx + 1} ${ev.event_type}`))));
  $('flight-payload').textContent = evs.length ? JSON.stringify(evs[state.cursor], null, 2) : '';
}
async function forkTape() {
  try {
    const r = await api('/v1/flight/fork', { method: 'POST', body: { task_id: state.tapeId, at_index: state.cursor + 1 } });
    toast(`${t('fork')} → ${r.forked_task_id}`); state.tapeId = r.forked_task_id; loadTapes();
  } catch (err) { toast(err.message, 'err'); }
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
async function buildIntent(e) {
  e.preventDefault();
  try {
    const r = await api('/v1/payments/intent', { method: 'POST', body: { rail: $('pay-rail').value, amount: Number($('pay-amount').value), currency: $('pay-currency').value.toUpperCase(), recipient: $('pay-recipient').value } });
    $('pay-out').textContent = JSON.stringify(r, null, 2); tone('ok');
  } catch (err) { $('pay-out').textContent = err.message; tone('err'); }
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
    tbody.innerHTML = `<tr><td colspan="6" class="p-3 text-danger text-center font-mono">${err.message}</td></tr>`;
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
  if (mode === 'agent') {
    try {
      const r = await api('/v1/agent/run', { method: 'POST', body: { goal, policy: $('agent-policy').value } });
      state.agentTask = { id: r.task_id, goal };
      $('agent-goal').value = ''; tone('ok'); renderAgent(r.state); loadRuns();
    } catch (err) { toast(err.message, 'err'); }
  } else {
    try {
      toast(`[${mode.toUpperCase()}] Consulting Keelway…`, 'info');
      const r = await api('/v1/chat/message', {
        method: 'POST',
        body: { message: goal, mode, target_file: state.active }
      });
      log(`[${r.mode.toUpperCase()}] ${r.content}`, 'text-ide-fg');
      if (r.memory_citations && r.memory_citations.length) {
        log(`Citations: ${r.memory_citations.map((c) => c.citation).join(', ')}`, 'text-ide-muted text-[11px]');
      }
      if (r.structured_plan) {
        toast(`[+] Plan generated: ${r.structured_plan.steps.length} steps`, 'ok');
        state.agentTask = { id: `task_plan_${Date.now()}`, goal };
        renderAgent({
          task_id: state.agentTask.id,
          goal,
          status: 'plan_ready',
          policy: 'confirm_mutation',
          plan: r.structured_plan.steps.map((st, i) => ({ id: `step_${i+1}`, description: st, status: 'pending' })),
          pending_approval: null,
          recent_events: [{ type: 'plan_formulated', payload: r.structured_plan }],
        });
      } else if (r.edit_proposal) {
        toast(`[+] Edit proposed on ${r.edit_proposal.file_path}`, 'ok');
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
  const run = h('button', { type: 'button', class: 'btn-primary py-0.5 text-[11px]' }, 'Run step');
  run.addEventListener('click', async () => {
    let parsed; try { parsed = JSON.parse(args.value); } catch { toast('Arguments must be JSON', 'err'); return; }
    run.disabled = true;
    try { const r = await api(`/v1/agent/step/${encodeURIComponent(state.agentTask.id)}`, { method: 'POST', body: { tool_name: tool.value, arguments: parsed, step_id: step.id } }); renderAgent(r.agent_state); afterAgentAction(r.step_result); }
    catch (err) { toast(err.message, 'err'); run.disabled = false; }
  });
  return h('div', { class: 'ms-7 space-y-1.5' }, h('div', { class: 'flex gap-1.5' }, tool, run), args);
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
let paletteItems = [], paletteIdx = 0, fileIndex = [];
function flatten(n, out = []) { (n.children || []).forEach((c) => (c.type === 'directory' ? flatten(c, out) : out.push(c.path))); return out; }
function commands() {
  return [
    ['Go to Tasks', () => switchSection('tasks')], ['Go to Files', () => switchSection('files')], ['Go to Record', () => switchSection('record')], ['Go to Labs', () => switchSection('labs')],
    ['New task', newRun], ['Explorer', () => { switchSection('files'); switchView('explorer'); }], ['Changes', () => { switchSection('files'); switchView('git'); }], ['Memory', () => { switchSection('files'); switchView('memory'); }],
    ['Show diff of working tree', () => { switchSection('files'); setMode('diff'); }], ['Toggle air-gap', toggleAirGap], ['Toggle theme', () => setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light')],
    ['Verify audit chain', () => switchSection('record')], ['Replay product tour', startTour], ['Sign out', signOut],
  ].map(([label, run]) => ({ label, run, kind: '⌘' }));
}
async function openPalette() {
  $('palette').classList.remove('hidden'); $('palette').classList.add('flex');
  $('palette-input').value = ''; $('palette-input').focus(); renderPalette();
  if (!fileIndex.length) { try { fileIndex = flatten((await api('/v1/files/tree?max_depth=6')).tree); renderPalette(); } catch { /* noop */ } }
}
function closePalette() { $('palette').classList.add('hidden'); $('palette').classList.remove('flex'); }
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
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); paletteIdx = (paletteIdx + (e.key === 'ArrowDown' ? 1 : -1) + paletteItems.length) % Math.max(paletteItems.length, 1); renderPalette(); $(`pal-${paletteIdx}`)?.scrollIntoView({ block: 'nearest' }); }
  else if (e.key === 'Enter' && paletteItems[paletteIdx]) { e.preventDefault(); const it = paletteItems[paletteIdx]; closePalette(); it.run(); }
  else if (e.key === 'Escape') closePalette();
}
// ---------- onboarding ----------
let tourStep = 0;
function startTour() { tourStep = 0; $('onboard').classList.remove('hidden'); $('onboard').classList.add('flex'); renderTour(); $('onboard-next').focus(); }
function renderTour() {
  const steps = t('tour');
  const [title, body] = steps[tourStep];
  $('onboard-step').textContent = `${tourStep + 1} / ${steps.length}`;
  $('onboard-title').textContent = title; $('onboard-body').textContent = body;
  $('onboard-next').textContent = tourStep === steps.length - 1 ? t('done') : t('next');
}
function endTour() { localStorage.setItem('keelway.onboarded', '1'); $('onboard').classList.add('hidden'); $('onboard').classList.remove('flex'); }

// ---------- boot ----------
function welcomeFacts() {
  const s = state.status; if (!s) return;
  const facts = [['Model', s.local_model], ['Hardware', `${s.hardware.arch} · ${s.hardware.ram_gb} GB`], ['Tasks', s.tasks.total], ['Flight tapes', s.flight_tapes]];
  $('welcome-facts').replaceChildren(...facts.map(([k, v]) => h('div', { class: 'p-2.5 rounded-lg border border-ide-border bg-ide-sidebar/60' }, h('dt', { class: 'text-ide-faint text-[10px] uppercase tracking-wider' }, k), h('dd', { class: 'mt-0.5 font-mono truncate' }, v))));
}
async function startSession() {
  await Promise.all([loadStatus(), loadTree(), loadGit()]);
  welcomeFacts();
  switchSection(location.hash.slice(1) || 'tasks');
  if (state.ws) { const old = state.ws; state.ws = null; old.close(); }
  connectWs();
  if (!localStorage.getItem('keelway.onboarded')) startTour();
}
function relabel() { applyI18n(); renderPanelTabs(); renderWelcome(); renderTabs(); renderRuns(); if (state.status) { setAirGap(state.status.air_gapped); $('composer-model').textContent = `${t('localModel')} · ${state.status.local_model}`; } if (state.agentState) renderAgent(state.agentState); }

function wire() {
  $('lang-select').replaceChildren(...Object.entries(LANGS).map(([k, v]) => h('option', { value: k }, v)));
  $('lang-select').value = lang;
  $('lang-select').addEventListener('change', (e) => { lang = e.target.value; localStorage.setItem('keelway.lang', lang); relabel(); });
  $('theme-btn').addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'));
  $('sound-btn').setAttribute('aria-pressed', String(sound));
  $('sound-btn').addEventListener('click', () => { sound = !sound; localStorage.setItem('keelway.sound', sound ? 'on' : 'off'); $('sound-btn').setAttribute('aria-pressed', String(sound)); tone('tick'); });
  $('airgap-btn').addEventListener('click', toggleAirGap);
  $('signout-btn').addEventListener('click', signOut);
  $('signin-form').addEventListener('submit', signIn);
  $('palette-btn').addEventListener('click', openPalette);
  $('palette-input').addEventListener('input', () => { paletteIdx = 0; renderPalette(); });
  $('palette-input').addEventListener('keydown', paletteKey);
  $('palette').addEventListener('click', (e) => { if (e.target === $('palette')) closePalette(); });
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
        agent: 'Ask Keelway to execute an autonomous engineering task…',
        ask: 'Ask a question about repository code or architecture (read-only)…',
        plan: 'Describe what you want to build or refactor (produces structured plan)…',
        edit: 'Describe specific code changes or patch to formulate…',
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
  $('heal-form').addEventListener('submit', runHeal);
  $('pay-form').addEventListener('submit', buildIntent);
  $('audit-verify').addEventListener('click', verifyAudit);
  if ($('audit-anchor-btn')) $('audit-anchor-btn').addEventListener('click', anchorAudit);
  if ($('tier2-verify-btn')) $('tier2-verify-btn').addEventListener('click', verifyTier2);
  $('agent-form').addEventListener('submit', startAgent);
  $('agent-goal').addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) $('agent-form').requestSubmit(); });
  $('approve-yes').addEventListener('click', () => approve(true));
  $('approve-no').addEventListener('click', () => approve(false));
  $('approve-always').addEventListener('click', () => { const f = $('always-form'); const open = f.classList.toggle('hidden') === false; $('approve-always').setAttribute('aria-expanded', String(open)); if (open) $('always-scope').focus(); });
  $('always-cancel').addEventListener('click', () => { $('always-form').classList.add('hidden'); $('approve-always').setAttribute('aria-expanded', 'false'); });
  $('always-form').addEventListener('submit', (e) => { e.preventDefault(); const scope = $('always-scope').value.trim(); if (!scope) { $('always-scope').focus(); toast(t('scopeRequired'), 'err'); return; } approve(true, scope); });
  document.querySelectorAll('[data-section]').forEach((b) => b.addEventListener('click', () => switchSection(b.dataset.section)));
  $('new-run-btn').addEventListener('click', newRun);
  $('task-back').addEventListener('click', () => { $('sec-tasks').dataset.detail = 'false'; });
  $('review-btn').addEventListener('click', () => { switchSection('files'); setMode('diff'); });
  $('open-record-btn').addEventListener('click', () => switchSection('record'));
  $('sb-approval').addEventListener('click', () => { const r = state.runs.find((x) => x.pending_approval); switchSection('tasks'); if (r) selectRun(r.task_id, r.goal); });
  $('onboard-skip').addEventListener('click', endTour);
  $('onboard-next').addEventListener('click', () => { if (tourStep >= t('tour').length - 1) endTour(); else { tourStep += 1; renderTour(); } });
  document.addEventListener('keydown', (e) => {
    const mod = e.metaKey || e.ctrlKey;
    if (mod && e.key.toLowerCase() === 'k') { e.preventDefault(); openPalette(); }
    else if (mod && e.key.toLowerCase() === 's') { e.preventDefault(); saveFile(); }
    else if (e.altKey && /^[1-4]$/.test(e.key)) { e.preventDefault(); switchSection(SECTIONS[Number(e.key) - 1]); }
    else if (e.altKey && e.key.toLowerCase() === 'a') { e.preventDefault(); toggleAirGap(); }
    else if (mod && e.key === 'j') { e.preventDefault(); $('panel').classList.toggle('hidden'); }
    else if (e.key === 'Escape') { closePalette(); if (!$('onboard').classList.contains('hidden')) endTour(); }
  });
}

async function boot() {
  setTheme(localStorage.getItem('keelway.theme') || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'));
  wire(); relabel(); switchPanel('console'); initMonaco();
  log('Keelway Studio · type help', 'text-ide-muted');
  try { await loadMe(); } catch { if (!signInOpen()) showSignIn(); return; }
  await startSession();
}
boot();
