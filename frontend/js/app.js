document.addEventListener('configReady', initApp);

function initApp() {
  const socket = io("http://3.71.28.18:5000", { transports: ['websocket'] });

  const clientInput = document.getElementById('client-input');
  const agentInput  = document.getElementById('agent-input');
  const clientMsgs  = document.getElementById('client-messages'); // 客户端消息容器
  const agentMsgs   = document.getElementById('agent-messages');  // 客服端消息容器

  // ===== 接收服务器消息，渲染到两端 =====
  socket.on('new_message', (data) => {
    // 图片消息
    if (data.image) {
      if (clientMsgs) addMessage(clientMsgs, `<img src="${data.image}" class="chat-image">`, data.from, data.from === 'client' ? 'right' : 'left', true, data.timestamp);
      if (agentMsgs)  addMessage(agentMsgs,  `<img src="${data.image}" class="chat-image">`, data.from, data.from === 'agent'  ? 'right' : 'left', true, data.timestamp);
      return;
    }

    // 文本消息
    if (clientMsgs) {
      if (data.from === 'client') {
        // 客户端自己发的（右边，显示原文）
        addMessage(clientMsgs, data.original || '', 'client', 'right', false, data.timestamp);

        // 机器人回复（左边，显示法语）
        if (data.bot_reply) {
          addMessage(clientMsgs, data.reply_fr || data.bot_reply, 'agent', 'left', false, data.timestamp);
        }
      } else if (data.from === 'agent') {
        // 客服发的（左边，显示翻译）
        addMessage(clientMsgs, data.translated || data.original || '', 'agent', 'left', false, data.timestamp);
      }
    }

    if (agentMsgs) {
      if (data.from === 'client') {
        // 客户发的（左边，显示中文）
        addMessage(agentMsgs, data.client_zh || data.original || '', 'client', 'left', false, data.timestamp);

        // 机器人回复（右边，显示中文）
        if (data.bot_reply) {
          addMessage(agentMsgs, data.reply_zh || data.bot_reply, 'agent', 'right', false, data.timestamp);
        }
      } else if (data.from === 'agent') {
        // 客服发的（右边，显示原文）
        addMessage(agentMsgs, data.original || '', 'agent', 'right', false, data.timestamp);
      }
    }
  });

  // ===== 客户端发送文本 =====
document.getElementById('client-send')?.addEventListener('click', () => {
  const msg = clientInput.value.trim();
  if (!msg) return;

  // 本地立刻显示
  if (clientMsgs) {
    addMessage(clientMsgs, msg, 'client', 'right', false, 
      new Date().toISOString().replace("T", " ").substring(0, 16));
  }

  socket.emit('client_message', { message: msg });
  clientInput.value = '';
});
clientInput?.addEventListener('keypress', (e) => e.key === 'Enter' && document.getElementById('client-send').click());

// ===== 客服端发送文本 =====
document.getElementById('agent-send')?.addEventListener('click', () => {
  const msg = agentInput.value.trim();
  if (!msg) return;

  // 本地立刻显示
  if (agentMsgs) {
    addMessage(agentMsgs, msg, 'agent', 'right', false, 
      new Date().toISOString().replace("T", " ").substring(0, 16));
  }

  socket.emit('agent_message', { 
    message: msg,
    target_lang: window.AppConfig?.DEFAULT_CLIENT_LANG || 'fr'
  });
  agentInput.value = '';
});
agentInput?.addEventListener('keypress', (e) => e.key === 'Enter' && document.getElementById('agent-send').click());


  // ===== 客户端上传图片 =====
  document.getElementById('client-file')?.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      socket.emit('client_message', { image: evt.target.result });
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  });

  // ===== 客服端上传图片 =====
  document.getElementById('agent-file')?.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      // ✅ 本地立刻显示图片
      if (agentMsgs) {
        addMessage(agentMsgs, `<img src="${evt.target.result}" class="chat-image">`, 'agent', 'right', true);
      }
      socket.emit('agent_message', { image: evt.target.result });
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  });

  // ===== UI 渲染函数 =====
  function addMessage(container, content, sender, align, isHTML = false, timestamp = null) {
    if (!container) return;
    const wrap = document.createElement('div');
    wrap.className = `message-wrapper ${align}`;

    const bubble = document.createElement('div');
    bubble.className = `message-content ${sender}`;

    // 标题：客户/客服
    const title = document.createElement('div');
    title.className = 'message-title';
    title.textContent = sender === 'client' ? 'je' : 'GameSawa service client';

    // 内容
    const body = document.createElement('div');
    body.className = 'message-body';
    if (isHTML) {
      body.innerHTML = content;
    } else {
      body.textContent = content ?? '';
    }

    // 时间戳
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    const now = timestamp 
      ? timestamp 
      : new Date().toISOString().replace("T", " ").substring(0, 16);
    timeDiv.textContent = now;

    bubble.appendChild(title);
    bubble.appendChild(body);
    bubble.appendChild(timeDiv);
    wrap.appendChild(bubble);
    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;
  }
}
