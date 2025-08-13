// 全局配置对象
window.AppConfig = {
  loading: true,
  API_BASE_URL: '',
  DEFAULT_LANGUAGE: 'fr'
};

// 动态加载配置
(async function loadConfig() {
  try {
    const response = await fetch('/api/config');
    const remoteConfig = await response.json();
    
    // 合并配置
    Object.assign(window.AppConfig, remoteConfig);
    
    // 标记加载完成
    window.AppConfig.loading = false;
    
    // 触发配置就绪事件
    const event = new Event('configReady');
    document.dispatchEvent(event);
    
  } catch (error) {
    console.error('加载配置失败:', error);
    // 使用默认值
    window.AppConfig.API_BASE_URL = window.location.origin;
    window.AppConfig.loading = false;
    document.dispatchEvent(new Event('configReady'));
  }
})();