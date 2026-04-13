const meetingState = document.getElementById('meeting-state');
const summaryView = document.getElementById('summary-view');
const decisionView = document.getElementById('decision-view');
const runLog = document.getElementById('run-log');
const hubStatus = document.getElementById('hub-status');

const hubFields = [
  'theme',
  'current',
  'goal',
  'constraints',
  'chatgpt',
  'gemini',
  'grok',
  'cursor',
  'openclaw',
  'conclusion',
  'next-actions',
];

function getHubData() {
  const data = {};
  for (const id of hubFields) {
    const el = document.getElementById(id);
    data[id] = el ? el.value : '';
  }
  return data;
}

function setHubData(data) {
  for (const id of hubFields) {
    const el = document.getElementById(id);
    if (!el) continue;
    el.value = data?.[id] || '';
  }
}

function saveHub() {
  localStorage.setItem('aiMeetingHubLite', JSON.stringify(getHubData()));
  hubStatus.textContent = 'Hub内容を保存しました';
}

function loadHub() {
  try {
    const raw = localStorage.getItem('aiMeetingHubLite');
    if (!raw) return;
    setHubData(JSON.parse(raw));
    hubStatus.textContent = '保存済みHub内容を読み込みました';
  } catch (error) {
    hubStatus.textContent = 'Hub内容の読み込みに失敗しました';
  }
}

function clearHub() {
  localStorage.removeItem('aiMeetingHubLite');
  setHubData({});
  hubStatus.textContent = 'Hub内容をクリアしました';
}

async function loadStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    meetingState.textContent = JSON.stringify(data.meeting_state, null, 2);
    summaryView.textContent = JSON.stringify(data.summary, null, 2);
    decisionView.textContent = JSON.stringify(data.decision, null, 2);
  } catch (error) {
    runLog.textContent = `状態取得に失敗しました: ${error}`;
  }
}

async function runAction(path, label) {
  runLog.textContent = `${label} 実行中...`;
  try {
    const res = await fetch(path, { method: 'POST' });
    const data = await res.json();
    runLog.textContent = JSON.stringify(data, null, 2);
    await loadStatus();
  } catch (error) {
    runLog.textContent = `${label} に失敗しました: ${error}`;
  }
}

document.getElementById('run-auto').addEventListener('click', () => {
  runAction('/api/run-auto', '計画 + dispatch');
});

document.getElementById('run-summary').addEventListener('click', () => {
  runAction('/api/build-summary', 'summary 生成');
});

document.getElementById('run-chairperson').addEventListener('click', () => {
  runAction('/api/chairperson', 'chairperson 生成');
});

document.getElementById('refresh-status').addEventListener('click', () => {
  loadStatus();
});

document.getElementById('save-hub').addEventListener('click', saveHub);
document.getElementById('clear-hub').addEventListener('click', clearHub);

loadHub();
loadStatus();
