document.addEventListener('configReady', initApp);

function initApp() {
  const socket = io("http://3.71.28.18:5000", { transports: ['websocket'] });

  const clientInput = document.getElementById('client-input');
  const agentInput  = document.getElementById('agent-input');
  const clientMsgs  = document.getElementById('client-messages'); // 客户页面容器（存在则代表当前是客户视图）
  const agentMsgs   = document.getElementById('agent-messages');  // 客服页面容器（存在则代表当前是客服视图）

  // 统一只从服务器广播渲染，避免重复
  socket.on('new_message', (data) => {
    // 图片：两边都按图片显示，不涉及翻译
    if (data.image) {
      if (clientMsgs) addMessage(clientMsgs, `<img src="${data.image}" class="chat-image">`, data.from, data.from === 'client' ? 'right' : 'left', true);
      if (agentMsgs)  addMessage(agentMsgs,  `<img src="${data.image}" class="chat-image">`,  data.from, data.from === 'agent'  ? 'right' : 'left', true);
      return;
    }

    // 文本：根据当前面板决定显示 original 还是 translated
        if (clientMsgs) {
      if (data.from === 'client') {
        // 客户端界面：自己发的用原文，机器人的回复用法语
        addMessage(clientMsgs, data.original || '', 'client', 'right');
        if (data.bot_reply) {
          addMessage(clientMsgs, data.reply_fr || data.bot_reply, 'agent', 'left');
        }
      } else if (data.from === 'agent') {
        addMessage(clientMsgs, data.translated || data.original || '', 'agent', 'left');
      }
    }

    if (agentMsgs) {
      if (data.from === 'client') {
        // ✅ 客户发的显示中文（翻译过的）
        addMessage(agentMsgs, data.client_zh || data.original || '', 'client', 'left');
        // ✅ 机器人回复显示中文
        if (data.bot_reply) {
          addMessage(agentMsgs, data.reply_zh || data.bot_reply, 'agent', 'right');
        }
      } else if (data.from === 'agent') {
        addMessage(agentMsgs, data.original || '', 'agent', 'right');
      }
    }


  });

  // ===== 发送文本（不本地渲染，等服务器广播） =====
  document.getElementById('client-send')?.addEventListener('click', () => {
    const msg = clientInput.value.trim();
    if (!msg) return;
    socket.emit('client_message', { message: msg });
    clientInput.value = '';
  });
  clientInput?.addEventListener('keypress', (e) => e.key === 'Enter' && document.getElementById('client-send').click());

  document.getElementById('agent-send')?.addEventListener('click', () => {
    const msg = agentInput.value.trim();
    if (!msg) return;
    socket.emit('agent_message', { 
      message: msg,
      target_lang: window.AppConfig?.DEFAULT_CLIENT_LANG || 'fr'
    });
    agentInput.value = '';
  });
  agentInput?.addEventListener('keypress', (e) => e.key === 'Enter' && document.getElementById('agent-send').click());

  // ===== 上传图片（客户端 & 客服端）=====
  document.getElementById('client-file')?.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      socket.emit('client_message', { image: evt.target.result });
    };
    reader.readAsDataURL(file);
    e.target.value = ''; // 允许重复选择同一文件
  });

  document.getElementById('agent-file')?.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      socket.emit('agent_message', { image: evt.target.result });
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  });

  // ===== UI 渲染 =====
  function addMessage(container, content, sender, align, isHTML = false) {
    if (!container) return;
    const wrap = document.createElement('div');
    wrap.className = `message-wrapper ${align}`;

    const bubble = document.createElement('div');
    bubble.className = `message-content ${sender}`;

    // 标题：客户/客服
    const title = document.createElement('div');
    title.className = 'message-title';
    title.textContent = sender === 'client' ? 'je' : 'GameSawa service client';

    const body = document.createElement('div');
    body.className = 'message-body';

    if (isHTML) {
      body.innerHTML = content;      // 用于 <img>，注意不要把任意不可信 HTML 放进来
    } else {
      body.textContent = content ?? '';
    }

    bubble.appendChild(title);
    bubble.appendChild(body);
    wrap.appendChild(bubble);
    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;
  }
}
