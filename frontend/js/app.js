document.addEventListener('configReady', initApp);

function initApp() {
  const role = document.body.dataset.role || "client";
  const socket = io("http://3.71.28.18:5000", { transports: ['websocket'], query: { role } });

  const clientInput = document.getElementById('client-input');
  const agentInput  = document.getElementById('agent-input');
  const clientMsgs  = document.getElementById('client-messages'); 
  const agentMsgs   = document.getElementById('agent-messages'); 

  // ===== 接收服务器消息，渲染到两端 =====
  socket.on('new_message', (data) => {
    const ts = data.timestamp || new Date().toISOString().replace("T", " ").substring(0, 16);

    // 图片消息
    if (data.image) {
      if (role === 'client' && clientMsgs) {
        addMessage(clientMsgs, `<img src="${data.image}" class="chat-image">`, data.from, data.from === 'client' ? 'right' : 'left', true, ts);
      }
      if (role === 'agent' && agentMsgs) {
        addMessage(agentMsgs, `<img src="${data.image}" class="chat-image">`, data.from, data.from === 'agent' ? 'right' : 'left', true, ts);
      }
      return;
    }

    // 文本消息
    if (role === 'client' && clientMsgs) {
      if (data.from === 'client') {
        addMessage(clientMsgs, data.original || '', 'client', 'right', false, ts);
        if (data.bot_reply) {
          addMessage(clientMsgs, data.reply_fr || data.bot_reply, 'agent', 'left', false, ts);
        }
      } else if (data.from === 'agent') {
        addMessage(clientMsgs, data.translated || data.original || '', 'agent', 'left', false, ts);
      }
    }

    if (role === 'agent' && agentMsgs) {
      if (data.from === 'agent') {
        // 自己消息不重复显示
        if (data.original) addMessage(agentMsgs, data.original, 'agent', 'right', false, ts);
      } else if (data.from === 'client') {
        addMessage(agentMsgs, data.client_zh || data.original || '', 'client', 'left', false, ts);
        if (data.bot_reply) {
          addMessage(agentMsgs, data.reply_zh || data.bot_reply, 'agent', 'right', false, ts);
        }
      }
    }
  });

  // ===== 客户端发送文本 =====
  if (clientInput) {
    document.getElementById('client-send')?.addEventListener('click', () => {
      const msg = clientInput.value.trim();
      if (!msg) return;

      socket.emit('client_message', { message: msg });
      clientInput.value = '';
    });

    clientInput.addEventListener('keypress', (e) => e.key === 'Enter' && document.getElementById('client-send').click());
  }

  // ===== 客服端发送文本 =====
  if (agentInput) {
    document.getElementById('agent-send')?.addEventListener('click', () => {
      const msg = agentInput.value.trim();
      if (!msg) return;

      const ts = new Date().toISOString().replace("T", " ").substring(0, 16);
      addMessage(agentMsgs, msg, 'agent', 'right', false, ts);

      socket.emit('agent_message', { 
        message: msg,
        target_lang: window.AppConfig?.DEFAULT_CLIENT_LANG || 'fr'
      });

      agentInput.value = '';
    });

    agentInput.addEventListener('keypress', (e) => e.key === 'Enter' && document.getElementById('agent-send').click());
  }

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
      addMessage(agentMsgs, `<img src="${evt.target.result}" class="chat-image">`, 'agent', 'right', true);
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

    const title = document.createElement('div');
    title.className = 'message-title';
    title.textContent = sender === 'client' ? 'je' : 'GameSawa service client';

    const body = document.createElement('div');
    body.className = 'message-body';
    body[isHTML ? 'innerHTML' : 'textContent'] = content ?? '';

    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = timestamp || new Date().toISOString().replace("T", " ").substring(0, 16);

    bubble.appendChild(title);
    bubble.appendChild(body);
    bubble.appendChild(timeDiv);
    wrap.appendChild(bubble);
    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;
  }
}
