// 等待配置加载完成
document.addEventListener('configReady', initApp);

function initApp() {
  if (window.AppConfig.loading) {
    console.error('配置加载超时');
    return;
  }

  console.log('当前配置:', window.AppConfig);
  
  // 常量定义
  const API_CHAT_URL = `${window.AppConfig.API_BASE_URL}/api/v1/chat`;
  const API_AGENT_URL = `${window.AppConfig.API_BASE_URL}/api/v1/agent/reply`;
  
  // 获取DOM元素
  const clientInput = document.getElementById('client-input');
  const agentInput = document.getElementById('agent-input');
  const clientMessages = document.getElementById('client-messages');
  const agentMessages = document.getElementById('agent-messages');

  // 客户端发送消息
  document.getElementById('client-send').addEventListener('click', sendClientMessage);
  clientInput.addEventListener('keypress', (e) => e.key === 'Enter' && sendClientMessage());

  // 客服端发送消息
  document.getElementById('agent-send').addEventListener('click', sendAgentMessage);
  agentInput.addEventListener('keypress', (e) => e.key === 'Enter' && sendAgentMessage());

  async function sendClientMessage() {
    const msg = clientInput.value.trim();
    if (!msg) return;
    
    addMessage(clientMessages, msg, 'client');
    clientInput.value = '';
    
    try {
      // 显示加载状态
      const loadingId = showLoading(clientMessages);
      
      const response = await fetch(API_CHAT_URL, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ message: msg })
      });
      
      removeLoading(loadingId);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `HTTP错误! 状态码: ${response.status}`);
      }
      
      const data = await response.json();
      if (data.status !== 'success') {
        throw new Error(data.message || '服务器返回未知错误');
      }
      
      addMessage(agentMessages, data.data.translated, 'agent');
      
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
    
    try {
      const loadingId = showLoading(agentMessages);
      
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
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `HTTP错误! 状态码: ${response.status}`);
      }
      
      const data = await response.json();
      if (data.status !== 'success') {
        throw new Error(data.message || '服务器返回未知错误');
      }
      
      addMessage(clientMessages, data.data.translated, 'client');
      
    } catch (error) {
      console.error('请求失败:', error);
      addMessage(clientMessages, `错误: ${error.message}`, 'error');
    }
  }

  // 显示加载状态
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

  // 添加消息到界面
  function addMessage(container, text, type) {
    const msgElement = document.createElement('div');
    msgElement.className = `message ${type}`;
    msgElement.textContent = text;
    container.appendChild(msgElement);
    container.scrollTop = container.scrollHeight;
  }
}
