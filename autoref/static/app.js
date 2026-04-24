const chat  = document.getElementById('chat');
const input = document.getElementById('input');
const send  = document.getElementById('send');
const dot   = document.getElementById('status');
const stext = document.getElementById('status-text');

const ws = new WebSocket(`ws://${location.host}/ws`);

ws.onopen = () => {
  dot.classList.add('connected');
  stext.textContent = 'connected';
  input.disabled = false;
  send.disabled = false;
  input.focus();
};

ws.onclose = () => {
  dot.classList.remove('connected');
  stext.textContent = 'disconnected';
  input.disabled = true;
  send.disabled = true;
};

ws.onmessage = e => {
  const { username, message, outgoing } = JSON.parse(e.data);
  const div = document.createElement('div');
  div.className = 'msg ' + (outgoing ? 'out' : 'in');

  const user = document.createElement('span');
  user.className = 'user';
  user.textContent = username;

  const sep = document.createElement('span');
  sep.className = 'sep';
  sep.textContent = '»';

  const text = document.createElement('span');
  text.className = 'text';
  text.textContent = message;

  div.append(user, sep, text);
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
};

function doSend() {
  const text = input.value.trim();
  if (text && ws.readyState === WebSocket.OPEN) {
    ws.send(text);
    input.value = '';
  }
}

send.onclick = doSend;
input.onkeydown = e => { if (e.key === 'Enter') doSend(); };
