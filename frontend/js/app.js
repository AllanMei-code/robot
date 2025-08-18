document.addEventListener('configReady', initApp);

function initApp() {
  const socket = io("http://3.71.28.18:5000", {
    transports: ['websocket']
  });

  const currentUser = 'client'; // 或 'agent'，根据页面决定
  const clientInput = document.getElementById('client-input');
  const agentInput = document.getElementById('agent-input');
  const clientMessages = document.getElementById('client-messages');
  const agentMessages = document.getElementById('agent-messages');
  const API_CHAT_URL = `${window.AppConfig.API_BASE_URL}/api/v1/chat`;
  const API_AGENT_URL = `${window.AppConfig.API_BASE_URL}/api/v1/agent/reply`;
  // 监听服务器推送的新消息
socket.on('new_message', (data) => {
  if (data.from === 'client') {
    // 客户消息：在客服面板显示原文，在客户面板显示翻译
    addMessage(agentMessages, data.original, 'client');
    addMessage(clientMessages, data.translated, 'client');
  } else if (data.from === 'agent') {
    // 客服消息：在客服面板显示原文，在客户面板显示翻译
    addMessage(agentMessages, data.original, 'agent');
    addMessage(clientMessages, data.translated, 'agent');
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

function addMessage(container, text, sender) {
  const msgWrapper = document.createElement('div');
  msgWrapper.className = `message-wrapper ${sender}`;

  const title = document.createElement('div');
  title.className = 'message-title';

  // 根据当前所在面板决定显示标题
  const isAgentPanel = container.id === 'agent-messages';
  
  if (isAgentPanel) {
    // 在客服面板中：显示消息的真实来源
    title.textContent = sender === 'client' ? '客户' : '我（客服）';
  } else {
    // 在客户面板中：显示消息的真实来源
    title.textContent = sender === 'client' ? '我（客户）' : '客服';
  }

  const msgElement = document.createElement('div');
  msgElement.className = 'message-content';
  msgElement.textContent = text;

  msgWrapper.appendChild(title);
  msgWrapper.appendChild(msgElement);
  container.appendChild(msgWrapper);
  container.scrollTop = container.scrollHeight;
  }
}
