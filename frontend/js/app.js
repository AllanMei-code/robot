// 等待配置加载完成
document.addEventListener('configReady', initApp);

function initApp() {
  if (window.AppConfig.loading) {
    console.error('配置加载超时');
    return;
  }

  console.log('当前配置:', window.AppConfig);
  
  const API_CHAT_URL = `${window.AppConfig.API_BASE_URL}/api/v1/chat`;
  const API_AGENT_URL = `${window.AppConfig.API_BASE_URL}/api/v1/agent/reply`;
  
  const clientInput = document.getElementById('client-input');
  const agentInput = document.getElementById('agent-input');
  const clientMessages = document.getElementById('client-messages');
  const agentMessages = document.getElementById('agent-messages');

  document.getElementById('client-send').addEventListener('click', sendClientMessage);
  clientInput.addEventListener('keypress', (e) => e.key === 'Enter' && sendClientMessage());

  document.getElementById('agent-send').addEventListener('click', sendAgentMessage);
  agentInput.addEventListener('keypress', (e) => e.key === 'Enter' && sendAgentMessage());

  async function sendClientMessage() {
    const msg = clientInput.value.trim();
    if (!msg) return;

    addMessage(clientMessages, msg, 'client');
    clientInput.value = '';

    const loadingId = showLoading(clientMessages);
    try {
      const response = await fetch(API_CHAT_URL, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ message: msg })
      });

      removeLoading(loadingId);

      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        const text = await response.text();
        throw new Error(`Expected JSON but got: ${text.slice(0, 100)}...`);
      }

      const data = await response.json();
      if (data.status !== 'success') {
        throw new Error(data.message || '服务器返回未知错误');
      }

      addMessage(agentMessages, data.translated, 'agent');

    } catch (error) {
      console.error('请求失败:', error);
      addMessage(agentMessages, `错误: ${error.message}`, 'error');
    }
  }

  async function sendAgentMessage() {
    const msg = agentInput.value.trim();
    if (!msg) return;

    addMessage(agentMessages, msg, 'agent');
    agentInput.value = '';

    const loadingId = showLoading(agentMessages);
    try {
      const response = await fetch(API_AGENT_URL, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ 
          message: msg,
          target_lang: window.AppConfig.DEFAULT_CLIENT_LANG || 'fr'
        })
      });

      removeLoading(loadingId);

      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        const text = await response.text();
        throw new Error(`Expected JSON but got: ${text.slice(0, 100)}...`);
      }

      const data = await response.json();
      if (data.status !== 'success') {
        throw new Error(data.message || '服务器返回未知错误');
      }

      addMessage(clientMessages, data.translated, 'client');

    } catch (error) {
      console.error('请求失败:', error);
      addMessage(clientMessages, `错误: ${error.message}`, 'error');
    }
  }

  function showLoading(container) {
    const id = 'loading-' + Date.now();
    const loader = document.createElement('div');
    loader.id = id;
    loader.className = 'message loading';
    loader.textContent = '处理中...';
    container.appendChild(loader);
    container.scrollTop = container.scrollHeight;
    return id;
  }
  
  function removeLoading(id) {
    const element = document.getElementById(id);
    if (element) element.remove();
  }

  function addMessage(container, text, type) {
    const msgElement = document.createElement('div');
    msgElement.className = `message ${type}`;
    msgElement.textContent = text;
    container.appendChild(msgElement);
    container.scrollTop = container.scrollHeight;
  }
}
