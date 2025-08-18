document.addEventListener('configReady', initApp);

function initApp() {
  const socket = io("http://3.71.28.18:5000", {
    transports: ['websocket']
  });

  const clientInput = document.getElementById('client-input');
  const agentInput = document.getElementById('agent-input');
  const clientMessages = document.getElementById('client-messages');
  const agentMessages = document.getElementById('agent-messages');
  const API_CHAT_URL = `${window.AppConfig.API_BASE_URL}/api/v1/chat`;
  const API_AGENT_URL = `${window.AppConfig.API_BASE_URL}/api/v1/agent/reply`;
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
   const msgWrapper = document.createElement('div');
  msgWrapper.className = `message-wrapper ${type}`; // 包裹消息，用于颜色区分

  // 添加标题
  const title = document.createElement('div');
  title.className = 'message-title';
  title.textContent = type === 'client' ? '客户' : '客服';

  // 添加消息内容
  const msgElement = document.createElement('div');
  msgElement.className = 'message-content';
  msgElement.textContent = text;

  // 组合
  msgWrapper.appendChild(title);
  msgWrapper.appendChild(msgElement);
  container.appendChild(msgWrapper);
  container.scrollTop = container.scrollHeight;
  }
}
