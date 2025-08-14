// 全局配置对象（带默认值）
window.AppConfig = {
  loading: true,
  API_BASE_URL: 'http://3.71.28.18:5000', // 生产环境默认值
  DEFAULT_LANGUAGE: 'fr',
  FALLBACK: false // 标记是否使用了备用配置
};

// 动态加载配置
(async function loadConfig() {
  try {
    console.log('[Config] 开始加载远程配置...');
    
    const apiUrl = `${window.AppConfig.API_BASE_URL}/api/v1/config`;
    const response = await fetch(apiUrl, {
      headers: {
        'Accept': 'application/json',
        'Cache-Control': 'no-cache'
      }
    });

    // 检查HTTP状态码
    if (!response.ok) {
      throw new Error(`HTTP错误! 状态码: ${response.status}`);
    }

    // 验证响应内容类型
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      throw new TypeError('返回的不是JSON数据');
    }

    const remoteConfig = await response.json();
    
    // 配置验证
    if (!remoteConfig || typeof remoteConfig !== 'object') {
      throw new Error('无效的配置格式');
    }

    console.log('[Config] 远程配置加载成功:', remoteConfig);
    
    // 深度合并配置（保留未覆盖的默认值）
    window.AppConfig = {
      ...window.AppConfig,
      ...remoteConfig,
      FALLBACK: false
    };

  } catch (error) {
    console.error('[Config] 配置加载失败:', error);
    
    // 使用备用配置
    window.AppConfig.FALLBACK = true;
    
    // 如果是本地开发环境，自动切换为本地地址
    if (window.location.hostname === 'localhost' || 
        window.location.hostname === '127.0.0.1') {
      window.AppConfig.API_BASE_URL = window.location.origin;
    }
  } finally {
    // 无论成功失败都标记加载完成
    window.AppConfig.loading = false;
    
    console.log('[Config] 最终配置:', window.AppConfig);
    
    // 触发配置就绪事件
    document.dispatchEvent(new Event('configReady'));
  }
})();