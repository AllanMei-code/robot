document.addEventListener('configReady', initApp);

function initApp() {
  const socket = io("http://3.71.28.18:5000", {
    transports: ['websocket']
  });

  const clientInput = document.getElementById('client-input');
  const agentInput = document.getElementById('agent-input');
  const clientMessages = document.getElementById('client-messages');
  const agentMessages = document.getElementById('agent-messages');

  // 监听服务器推送的新消息（统一入口）
  socket.on('new_message', (data) => {
    let displayText;

    if (data.image) {
      displayText = `<img src="${data.image}" class="chat-image">`;
    } else {
      displayText = data.from === 'client' ? data.original : data.translated;
    }

    if (clientMessages) {
      // 客户界面
      if (data.from === 'client') {
        addMessage(clientMessages, data.original, 'client', 'right');
      } else if (data.from === 'agent') {
        addMessage(clientMessages, displayText, 'agent', 'left');
      }
    }

    if (agentMessages) {
      // 客服界面
      if (data.from === 'client') {
        addMessage(agentMessages, displayText, 'client', 'left');
      } else if (data.from === 'agent') {
        addMessage(agentMessages, data.original, 'agent', 'right');
      }
    }
  });

  // 客户端发送文字消息
  document.getElementById('client-send')?.addEventListener('click', sendClientMessage);
  clientInput?.addEventListener('keypress', (e) => e.key === 'Enter' && sendClientMessage());

  function sendClientMessage() {
    const msg = clientInput.value.trim();
    if (!msg) return;
    socket.emit('client_message', { message: msg });
    clientInput.value = '';
  }

  // 客服端发送文字消息
  document.getElementById('agent-send')?.addEventListener('click', sendAgentMessage);
  agentInput?.addEventListener('keypress', (e) => e.key === 'Enter' && sendAgentMessage());

  function sendAgentMessage() {
    const msg = agentInput.value.trim();
    if (!msg) return;
    socket.emit('agent_message', { 
      message: msg,
      target_lang: window.AppConfig.DEFAULT_CLIENT_LANG || 'fr'
    });
    agentInput.value = '';
  }

  // 客户端上传图片
  document.getElementById('client-file')?.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function(evt) {
      const base64 = evt.target.result;
      socket.emit('client_message', { image: base64 });
    };
    reader.readAsDataURL(file);
  });

  // 添加消息到 UI
  function addMessage(container, text, sender, align) {
    if (!container) return;
    const msgWrapper = document.createElement('div');
    msgWrapper.className = `message-wrapper ${align}`;

    const msgElement = document.createElement('div');
    msgElement.className = `message-content ${sender}`;
    msgElement.innerHTML = text;

    msgWrapper.appendChild(msgElement);
    container.appendChild(msgWrapper);
    container.scrollTop = container.scrollHeight;
  }
}
