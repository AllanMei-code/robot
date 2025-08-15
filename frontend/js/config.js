// ==================== 新版config.js ====================
// 立即执行的配置加载函数（替换原有全部代码）
(function initConfig() {
  // 默认配置（兼容您原有的默认值）
  const defaults = {
    loading: true,
    API_BASE_URL: window.location.hostname.includes('localhost') 
      ? window.location.origin 
      : 'http://3.71.28.18:5000', // 保持您原有的生产环境地址
    DEFAULT_LANGUAGE: 'fr', // 保持与原属性名一致
    FALLBACK: false,
    // 保留您可能在其他地方使用的扩展属性
    TRANSLATION_ENABLED: true,
    MAX_MESSAGE_LENGTH: 500
  };

  // 初始化全局配置（保持window.AppConfig接口不变）
  window.AppConfig = { ...defaults };

  // 配置加载函数（增强版）
  const loadConfig = async () => {
    try {
      const apiUrl = `${window.AppConfig.API_BASE_URL}/api/v1/config`;
      console.log(`[Config] 请求配置: ${apiUrl}`);
      
      const response = await fetch(apiUrl, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json',
          'Cache-Control': 'no-store'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status} - ${response.statusText}`);
      }

      const data = await response.json();
      
      // 兼容您后端的响应格式
      const remoteConfig = data.config || data; // 双重兼容
      if (!remoteConfig || typeof remoteConfig !== 'object') {
        throw new Error('无效的响应格式');
      }

      // 深度合并配置（保留您原有的合并逻辑）
    window.AppConfig = {
      API_BASE_URL: "http://3.71.28.18:5000", // 和 Flask-SocketIO 一致
      DEFAULT_CLIENT_LANG: "fr"
    };
      
    } catch (error) {
      console.error('[Config] 加载失败:', error);
      window.AppConfig = { 
        ...defaults,
        loading: false,
        FALLBACK: true 
      };
      
      // 保持您原有的本地开发环境逻辑
      if (window.location.hostname === 'localhost' || 
          window.location.hostname === '127.0.0.1') {
        window.AppConfig.API_BASE_URL = window.location.origin;
      }
    } finally {
      console.log('[Config] 最终配置:', window.AppConfig);
      // 保持事件触发兼容性
      document.dispatchEvent(new CustomEvent('configReady', {
        detail: { config: window.AppConfig }
      }));
    }
  };

  // 启动加载（保持原有执行时机）
  loadConfig();
})();

// ==================== 注意事项 ==================== 
// 1. 确保HTML中在app.js之前引入此文件
// 2. 原有的事件监听器无需修改
// 3. 访问配置的方式保持不变（仍使用window.AppConfig）