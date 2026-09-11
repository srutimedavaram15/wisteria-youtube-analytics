const CHANNEL_ID = 'UCpB959t8iPrxQWj7G6n0ctQ';
const DEFAULT_PLACEHOLDER = 'e.g. “How did my last video perform?” or “How many gaming videos have I posted?”';
const TITLE_PLACEHOLDER   = 'Enter a title for your video...';
let sending = false;

// ---------- helpers ----------
function truncate(str, max = 12) {
  return str.length > max ? str.slice(0, max - 1) + '…' : str;
}

// ---------- file button visual state ----------
function setFileButtonState(which, selected, filename) {
  const btn = document.getElementById(`${which}-btn`);
  if (selected) {
    btn.classList.add('bg-[#b7cbb7]');
    btn.title = truncate(filename);
  } else {
    btn.classList.remove('bg-[#b7cbb7]');
    btn.title = which === 'video' ? 'Attach your video' : 'Attach your thumbnail';
  }
}

function updatePlaceholder() {
  const hasVideo = document.getElementById('video-input').files?.length > 0;
  const hasThumb = document.getElementById('thumbnail-input').files?.length > 0;
  document.getElementById('chat-input').placeholder =
    (hasVideo && hasThumb) ? TITLE_PLACEHOLDER : DEFAULT_PLACEHOLDER;
}

document.getElementById('video-input').addEventListener('change', function () {
  const sel = this.files && this.files.length > 0;
  setFileButtonState('video', sel, sel ? this.files[0].name : '');
  updatePlaceholder();
});

document.getElementById('thumbnail-input').addEventListener('change', function () {
  const sel = this.files && this.files.length > 0;
  setFileButtonState('thumbnail', sel, sel ? this.files[0].name : '');
  updatePlaceholder();
});

// ---------- inline hint ----------
let hintTimer = null;

function showHint(message) {
  let hint = document.getElementById('chat-hint');
  if (!hint) {
    hint = document.createElement('p');
    hint.id = 'chat-hint';
    hint.className = 'text-xs text-ink/60 mt-1 ml-1';
    const inputRow = document.getElementById('chat-input').closest('div');
    inputRow.insertAdjacentElement('afterend', hint);
  }
  hint.textContent = message;
  clearTimeout(hintTimer);
  hintTimer = setTimeout(() => hint.remove(), 4000);
}

function clearHint() {
  const hint = document.getElementById('chat-hint');
  if (hint) hint.remove();
  clearTimeout(hintTimer);
}

// ---------- send button state ----------
function setSending(value) {
  sending = value;
  const btn = document.getElementById('send-button');
  btn.disabled = value;
  btn.style.opacity = value ? '0.5' : '';
}

// ---------- bubbles ----------
function appendBubble(text, role) {
  const history = document.getElementById('chat-history');

  const row = document.createElement('div');
  row.className = role === 'user' ? 'flex justify-end' : 'flex justify-start';

  const bubble = document.createElement('div');
  bubble.className = [
    'rounded-2xl px-4 py-2 max-w-[70%] whitespace-pre-wrap text-sm',
    role === 'user' ? 'bg-primary text-white' : 'bg-secondary text-ink',
  ].join(' ');
  bubble.textContent = text;

  row.appendChild(bubble);
  history.appendChild(row);
  history.scrollTop = history.scrollHeight;
  return row;
}

function appendThinking() {
  const history = document.getElementById('chat-history');
  const row = document.createElement('div');
  row.className = 'flex justify-start';
  row.id = 'thinking-bubble';
  const bubble = document.createElement('div');
  bubble.className = 'rounded-2xl px-4 py-2 text-sm bg-secondary text-ink/50 italic';
  bubble.textContent = 'Thinking…';
  row.appendChild(bubble);
  history.appendChild(row);
  history.scrollTop = history.scrollHeight;
}

function removeThinking() {
  document.getElementById('thinking-bubble')?.remove();
}

// ---------- send ----------
async function sendMessage() {
  if (sending) return;

  const input      = document.getElementById('chat-input');
  const videoInput = document.getElementById('video-input');
  const thumbInput = document.getElementById('thumbnail-input');
  const text       = input.value.trim();
  const hasVideo   = videoInput.files && videoInput.files.length > 0;
  const hasThumb   = thumbInput.files  && thumbInput.files.length  > 0;

  if (!text && !hasVideo && !hasThumb) return;

  if (hasVideo !== hasThumb) {
    showHint('Attach both a video and thumbnail to get a prediction.');
    return;
  }

  if (hasVideo && hasThumb && !text) {
    showHint('Add a title for this video first.');
    input.focus();
    return;
  }

  clearHint();

  const parts = [text];
  if (hasVideo) parts.push(`📹 ${videoInput.files[0].name}`);
  if (hasThumb) parts.push(`🖼 ${thumbInput.files[0].name}`);
  appendBubble(parts.join('\n'), 'user');

  input.value = '';

  const welcome = document.getElementById('welcome-cards');
  if (welcome) welcome.remove();

  setSending(true);
  appendThinking();

  try {
    if (hasVideo && hasThumb) {
      const form = new FormData();
      form.append('video',             videoInput.files[0]);
      form.append('thumbnail',         thumbInput.files[0]);
      form.append('channel_id',        CHANNEL_ID);
      form.append('category_id',       '22');
      form.append('published_weekday', '2');
      form.append('published_hour',    '15');
      form.append('title',             text);

      const res  = await fetch('http://127.0.0.1:8000/upload', { method: 'POST', body: form });
      const data = await res.json();
      removeThinking();
      appendBubble(
        `Performance tier: ${data.performance_tier}\n\nThumbnail feedback: ${data.thumbnail_feedback}`,
        'response',
      );
    } else {
      const res  = await fetch('http://127.0.0.1:8000/ask', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ channel_id: CHANNEL_ID, question: text }),
      });
      const data = await res.json();
      removeThinking();
      appendBubble(data.answer, 'response');
    }
  } catch {
    removeThinking();
    appendBubble(
      'Something went wrong reaching the server — make sure the backend is running and try again.',
      'response',
    );
  } finally {
    setSending(false);
    videoInput.value = '';
    thumbInput.value  = '';
    setFileButtonState('video', false, '');
    setFileButtonState('thumbnail', false, '');
    document.getElementById('chat-input').placeholder = DEFAULT_PLACEHOLDER;
  }
}

document.getElementById('send-button').addEventListener('click', sendMessage);
document.getElementById('chat-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') sendMessage();
});
