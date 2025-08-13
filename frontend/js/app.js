// 等待配置加载完成
document.addEventListener('configReady', initApp);

function initApp() {
  if (window.AppConfig.loading) {
    console.error('配置加载超时');
    return;
  }

  console.log('当前配置:', window.AppConfig);
  
  // 获取DOM元素
  const clientInput = document.getElementById('client-input');
  const agentInput = document.getElementById('agent-input');
  const clientMessages = document.getElementById('client-messages');
  const agentMessages = document.getElementById('agent-messages');

  // 客户端发送消息
  document.getElementById('client-send').addEventListener('click', async () => {
    const msg = clientInput.value.trim();
    if (!msg) return;
    
    addMessage(clientMessages, msg, 'client');
    clientInput.value = '';
    
    try {
      const res = await fetch(`${window.AppConfig.API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg })
      });
      
      const data = await res.json();
      addMessage(agentMessages, data.translated, 'agent');
      
    } catch (error) {
      console.error('请求失败:', error);
      addMessage(agentMessages, '翻译服务不可用', 'error');
    }
  });

  // 客服端发送消息
  document.getElementById('agent-send').addEventListener('click', async () => {
    const msg = agentInput.value.trim();
    if (!msg) return;
    
    addMessage(agentMessages, msg, 'agent');
    agentInput.value = '';
    
    try {
      const res = await fetch(`${window.AppConfig.API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          message: msg,
          target_lang: window.AppConfig.DEFAULT_LANGUAGE
        })
      });
      
      const data = await res.json();
      addMessage(clientMessages, data.translated, 'client');
      
    } catch (error) {
      console.error('请求失败:', error);
      addMessage(clientMessages, '翻译服务不可用', 'error');
    }
  });

  // 添加消息到界面
  function addMessage(container, text, type) {
    const msgElement = document.createElement('div');
    msgElement.className = `message ${type}`;
    msgElement.textContent = text;
    container.appendChild(msgElement);
    container.scrollTop = container.scrollHeight;
  }
}