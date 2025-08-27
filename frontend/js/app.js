document.addEventListener('configReady', initApp);

function initApp() {
  const role = document.body.dataset.role || "client";
  const socket = io("http://3.71.28.18:5000", { transports: ['websocket'], query: { role } });

  const clientInput = document.getElementById('client-input');
  const agentInput  = document.getElementById('agent-input');
  const clientMsgs  = document.getElementById('client-messages');
  const agentMsgs   = document.getElementById('agent-messages');

  // ===== 接收服务器消息 =====
  socket.on('new_message', (data) => {
    const ts = data.timestamp || new Date().toISOString().replace("T", " ").substring(0, 16);
    const isTestPage = !!(clientMsgs && agentMsgs);

    // 图片消息
    if (data.image) {
      if (clientMsgs) {
        addMessage(
          clientMsgs,
          `<img src="${data.image}" class="chat-image">`,
          data.from,
          data.from === 'client' ? 'right' : 'left',
          true,
          ts
        );
      }
      if (agentMsgs) {
        if (!(isTestPage && data.from === 'agent')) {
          addMessage(
            agentMsgs,
            `<img src="${data.image}" class="chat-image">`,
            data.from,
            data.from === 'agent' ? 'right' : 'left',
            true,
            ts
          );
        }
      }
      return;
    }

    // 客户端区域
    if (clientMsgs) {
      if (data.from === 'client') {
        addMessage(clientMsgs, data.original || '', 'client', 'right', false, ts);
        if (data.bot_reply) {
          addMessage(clientMsgs, data.reply_fr || data.bot_reply, 'agent', 'left', false, ts);
        }
      } else if (data.from === 'agent') {
        addMessage(clientMsgs, data.translated || data.original || '', 'agent', 'left', false, ts);
      }
    }

    // 客服端区域
    if (agentMsgs) {
      if (data.from === 'client') {
        addMessage(agentMsgs, data.client_zh || data.original || '', 'client', 'left', false, ts);
        if (data.bot_reply) {
          addMessage(agentMsgs, data.reply_zh || data.bot_reply, 'agent', 'right', false, ts);
        } else if (data.suggest_zh) {
          // 可选：把建议答案显示成灰色提示
          addMessage(agentMsgs, `（建议）${data.suggest_zh}`, 'agent', 'right', false, ts);
        }
      } else if (data.from === 'agent') {
        if (!isTestPage) {
          addMessage(agentMsgs, data.original || '', 'agent', 'right', false, ts);
        }
      }
    }
  });

  // ===== 客户端发送文本（避免重复：不本地渲染）=====
  clientInput?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') document.getElementById('client-send')?.click();
  });
  document.getElementById('client-send')?.addEventListener('click', () => {
    const msg = clientInput.value.trim();
    if (!msg) return;
    socket.emit('client_message', { message: msg });
    clientInput.value = '';
  });

  // ===== 客服端发送文本（本地立即显示）=====
  agentInput?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') document.getElementById('agent-send')?.click();
  });
  document.getElementById('agent-send')?.addEventListener('click', () => {
    const msg = agentInput.value.trim();
    if (!msg) return;
    const ts = new Date().toISOString().replace("T", " ").substring(0,16);
    if (agentMsgs) addMessage(agentMsgs, msg, 'agent', 'right', false, ts);
    socket.emit('agent_message', { message: msg, target_lang: window.AppConfig?.DEFAULT_CLIENT_LANG || 'fr' });
    agentInput.value = '';
  });

  // ===== 上传图片 =====
  ['client','agent'].forEach(roleKey => {
    const fileInput = document.getElementById(`${roleKey}-file`);
    if (!fileInput) return;
    fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (evt) => {
        if (roleKey === 'agent' && agentMsgs) {
          addMessage(agentMsgs, `<img src="${evt.target.result}" class="chat-image">`, 'agent', 'right', true);
        }
        socket.emit(`${roleKey}_message`, { image: evt.target.result });
      };
      reader.readAsDataURL(file);
      e.target.value = '';
    });
  });

  // ===== 表情选择逻辑 =====
  function setupEmoji(panelId, btnId, inputId) {
    const panel = document.getElementById(panelId);
    const btn = document.getElementById(btnId);
    const input = document.getElementById(inputId);
    if (!panel || !btn || !input) return;

    btn.addEventListener("click", () => {
      panel.style.display = panel.style.display === "block" ? "none" : "block";
    });

    panel.querySelectorAll("span").forEach(span => {
      span.addEventListener("click", () => {
        input.value += span.textContent;
        panel.style.display = "none";
      });
    });

    document.addEventListener("click", (e) => {
      if (!btn.contains(e.target) && !panel.contains(e.target)) panel.style.display = "none";
    });
  }
  setupEmoji("client-emoji-panel", "client-emoji-btn", "client-input");
  setupEmoji("agent-emoji-panel", "agent-emoji-btn", "agent-input");

  // ===== UI 渲染函数 =====
  function addMessage(container, content, sender, align, isHTML=false, timestamp=null) {
    if (!container) return;
    const wrap = document.createElement('div');
    wrap.className = `message-wrapper ${align}`;
    const bubble = document.createElement('div');
    bubble.className = `message-content ${sender}`;
    const title = document.createElement('div');
    title.className = 'message-title';
    title.textContent = sender==='client' ? 'je' : 'GameSawa service client';
    const body = document.createElement('div');
    body.className = 'message-body';
    if (isHTML) body.innerHTML = content; else body.textContent = content ?? '';
    const timeDiv = document.createElement('div');
    timeDiv.className='message-time';
    timeDiv.textContent = timestamp || new Date().toISOString().replace("T"," ").substring(0,16);
    bubble.appendChild(title);
    bubble.appendChild(body);
    bubble.appendChild(timeDiv);
    wrap.appendChild(bubble);
    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;
  }

  // ===== 人工/机器切换 & 打字抑制 =====
  const toggleBtn = document.getElementById('agent-online-toggle');
  let agentIsOnline = true;

  function renderToggleBtn() {
    if (!toggleBtn) return;
    toggleBtn.textContent = agentIsOnline ? '下线' : '上线';
    toggleBtn.classList.toggle('online', agentIsOnline);
    toggleBtn.classList.toggle('offline', !agentIsOnline);
  }

  socket.on('agent_status', (data) => {
    agentIsOnline = !!(data && data.online);
    renderToggleBtn();
  });

  toggleBtn?.addEventListener('click', () => {
    const nextOnline = !agentIsOnline;
    socket.emit('agent_set_status', { online: nextOnline });
    // 等服务器广播再更新 UI
  });

  // 打字抑制：客服输入时上报（节流）
  let typingTimer;
  agentInput?.addEventListener('input', () => {
    clearTimeout(typingTimer);
    socket.emit('agent_typing');
    typingTimer = setTimeout(() => {}, 500);
  });
}
