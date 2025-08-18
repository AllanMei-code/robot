// ==================== 新版config.js ====================
// 立即执行的配置加载函数（替换原有全部代码）
(function initConfig() {
  // 默认配置（兼容您原有的默认值）
  const defaults = {
    loading: true,
    API_BASE_URL: 'http://3.71.28.18:5000', // 保持您原有的生产环境地址
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
      const response = await fetch(`${window.AppConfig.API_BASE_URL}/api/v1/config`, {
        credentials: 'include'
      });
      const data = await response.json();
      window.AppConfig = { ...defaults, ...data.config, loading: false };
    } catch (error) {
      console.error('[Config] 加载失败:', error);
      window.AppConfig.loading = false;
    } finally {
      document.dispatchEvent(new CustomEvent('configReady', { detail: { config: window.AppConfig } }));
    }
  };

  loadConfig();
})();
