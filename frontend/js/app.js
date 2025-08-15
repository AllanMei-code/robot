document.addEventListener('configReady', initApp);

function initApp() {
  const socket = io("http://3.71.28.18:5000", {
    transports: ['websocket']
  });

  const clientInput = document.getElementById('client-input');
  const agentInput = document.getElementById('agent-input');
  const clientMessages = document.getElementById('client-messages');
  const agentMessages = document.getElementById('agent-messages');

  // 监听服务器推送的新消息
  socket.on('new_message', (data) => {
    if (data.from === 'client') {
      addMessage(clientMessages, data.original, 'client');
      addMessage(agentMessages, data.translated, 'agent');
    } else if (data.from === 'agent') {
      addMessage(agentMessages, data.original, 'agent');
      addMessage(clientMessages, data.translated, 'client');
    }
  });

  document.getElementById('client-send').addEventListener('click', sendClientMessage);
  clientInput.addEventListener('keypress', (e) => e.key === 'Enter' && sendClientMessage());

  document.getElementById('agent-send').addEventListener('click', sendAgentMessage);
  agentInput.addEventListener('keypress', (e) => e.key === 'Enter' && sendAgentMessage());

  function sendClientMessage() {
    const msg = clientInput.value.trim();
    if (!msg) return;
    socket.emit('client_message', { message: msg });
    clientInput.value = '';
  }

  function sendAgentMessage() {
    const msg = agentInput.value.trim();
    if (!msg) return;
    socket.emit('agent_message', { 
      message: msg,
      target_lang: window.AppConfig.DEFAULT_CLIENT_LANG || 'fr'
    });
    agentInput.value = '';
  }

  function addMessage(container, text, type) {
    const msgElement = document.createElement('div');
    msgElement.className = `message ${type}`;
    msgElement.textContent = text;
    container.appendChild(msgElement);
    container.scrollTop = container.scrollHeight;
  }
}
