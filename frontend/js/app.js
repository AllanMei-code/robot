// 允许 configReady 或 DOMContentLoaded 启动
(function(){
  let booted = false;
  function boot(){ if (booted) return; booted = true; initApp(); }

  document.addEventListener('configReady', boot);
  document.addEventListener('DOMContentLoaded', () => {
    if (window.AppConfig) boot(); else setTimeout(boot, 400);
  });
})();

function initApp() {
  // ===== 生成/读取会话ID（cid）=====
  const urlCid = new URLSearchParams(location.search).get('cid');
  let cid = urlCid || localStorage.getItem('cid');
  if (!cid) { cid = 'cid_' + Math.random().toString(36).slice(2, 10); localStorage.setItem('cid', cid); }

  // 单连接：默认作为“client”连接；测试页中两侧 UI 都渲染由前端控制
  const role = "client";
  const socket = io((window.AppConfig?.API_BASE_URL || "http://3.71.28.18:5000"), {
    transports: ['websocket'],
    query: { role, cid }
  });

  const clientInput = document.getElementById('client-input');
  const agentInput  = document.getElementById('agent-input');
  const clientMsgs  = document.getElementById('client-messages');
  const agentMsgs   = document.getElementById('agent-messages');
  const agentSendBtn= document.getElementById('agent-send');
  const toggleBtn   = document.getElementById('agent-online-toggle');

  // 时间 MM/DD HH:mm
  function formatTimestampToMDHM(input) {
    const src = typeof input === 'string' ? input : '';
    const d = new Date(src && src.includes(' ') ? src.replace(' ', 'T') : (src || Date.now()));
    const pad = n => String(n).padStart(2, '0');
    return `${pad(d.getMonth()+1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  // 渲染按钮与同步后端
  let agentIsOnline = true; // 在线=只学习；下线=机器人会自动回
  function renderToggleBtn(){
    if (!toggleBtn) return;
    toggleBtn.textContent = agentIsOnline ? '下线' : '上线';
    toggleBtn.classList.toggle('online',  agentIsOnline);
    toggleBtn.classList.toggle('offline', !agentIsOnline);
  }
  function applyAgentOnlineState(){
    renderToggleBtn();
    socket.emit('agent_set_status', { online: agentIsOnline, cid });
  }

  toggleBtn?.addEventListener('click', () => {
    agentIsOnline = !agentIsOnline;
    applyAgentOnlineState();
  });

  socket.on('agent_status', (data) => {
    if (!data || data.cid !== cid) return;
    agentIsOnline = !!data.online;
    renderToggleBtn();
  });

  // 首次同步一次
  applyAgentOnlineState();

  // ===== 接收服务器消息 =====
  socket.on('new_message', (data) => {
    if (data && data.cid && data.cid !== cid) return; // 只处理本会话
    const ts = data.timestamp || new Date().toISOString().replace("T", " ").substring(0, 16);
    const isTestPage = !!(clientMsgs && agentMsgs);

    // 图片
    if (data.image) {
      if (clientMsgs) {
        addMessage(clientMsgs, `<img src="${data.image}" class="chat-image">`,
          data.from, data.from === 'client' ? 'right' : 'left', true, ts);
      }
      if (agentMsgs) {
        // 测试页里，客服自己发的图片已本地渲染，这里避免重复
        if (!(isTestPage && data.from === 'agent')) {
          addMessage(agentMsgs, `<img src="${data.image}" class="chat-image">`,
            data.from, data.from === 'agent' ? 'right' : 'left', true, ts);
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
          addMessage(agentMsgs, `（建议）${data.suggest_zh}`, 'agent', 'right', false, ts);
        }
      } else if (data.from === 'agent') {
        // 测试页中，客服自己发的文本已本地渲染，这里防重复
        if (!isTestPage) addMessage(agentMsgs, data.original || '', 'agent', 'right', false, ts);
      }
    }
  });

  // ===== 客户端发送文本（不本地渲染，避免重复）=====
  clientInput?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') document.getElementById('client-send')?.click();
  });
  document.getElementById('client-send')?.addEventListener('click', () => {
    const msg = clientInput.value.trim();
    if (!msg) return;
    socket.emit('client_message', { message: msg, cid });
    clientInput.value = '';
  });

  // ===== 客服端发送文本（本地立即渲染）=====
  agentInput?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') document.getElementById('agent-send')?.click();
  });
  agentSendBtn?.addEventListener('click', () => {
    const msg = agentInput.value.trim();
    if (!msg) return;
    const ts = new Date().toISOString().replace("T"," ").substring(0,16);
    if (agentMsgs) addMessage(agentMsgs, msg, 'agent', 'right', false, ts); // 本地立即显示
    socket.emit('agent_message', {
      message: msg,
      cid,
      target_lang: window.AppConfig?.DEFAULT_CLIENT_LANG || 'fr'
    });
    agentInput.value = '';
  });

  // ===== 上传图片 =====
  ;['client','agent'].forEach(roleKey => {
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
        socket.emit(`${roleKey}_message`, { image: evt.target.result, cid });
      };
      reader.readAsDataURL(file);
      e.target.value = '';
    });
  });

  // ===== 表情选择 =====
  setupEmoji("client-emoji-panel", "client-emoji-btn", "client-input");
  setupEmoji("agent-emoji-panel", "agent-emoji-btn", "agent-input");

  function setupEmoji(panelId, btnId, inputId){
    const panel = document.getElementById(panelId);
    const btn   = document.getElementById(btnId);
    const input = document.getElementById(inputId);
    if (!panel || !btn || !input) return;

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
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

  // ===== 打字抑制（在线时上报）=====
  let typingTimer;
  agentInput?.addEventListener('input', () => {
    clearTimeout(typingTimer);
    if (agentIsOnline) socket.emit('agent_typing', { cid });
    typingTimer = setTimeout(()=>{}, 400);
  });

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
    const rawStamp = timestamp || new Date().toISOString().replace("T"," ").substring(0,16);
    timeDiv.className = 'message-time';
    timeDiv.textContent = formatTimestampToMDHM(rawStamp);
    timeDiv.title = rawStamp;

    bubble.appendChild(title);
    bubble.appendChild(body);
    bubble.appendChild(timeDiv);
    wrap.appendChild(bubble);
    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;
  }
}
