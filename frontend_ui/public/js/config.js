const ENVIRONMENT = {
  LOCAL: 'local',
  DEVELOPMENT: 'development',
  STAGING: 'staging',
  PRODUCTION: 'production'
};

const APP_CONFIG = {
  env: ENVIRONMENT.LOCAL,
  apiBaseUrl: '/api/v1', // Using strict relative path
  appVersion: '1.0.0',

  timeouts: {
    defaultApi: 30000,
    longApi: 60000,
    uploadApi: 120000,
    idleLogout: 900000
  },

  polling: {
    dashboardMetrics: 30000,
    hitlQueue: 15000,
    notifications: 60000
  },

  features: {
    enableWebSocket: false,
    enableAdvancedAnalytics: true,
    enableBulkActions: true,
    strictMode: true
  },

  pagination: {
    defaultSize: 50,
    options: [10, 25, 50, 100, 500]
  },

  security: {
    tokenStorageKey: 'eg_os_access_token',
    refreshStorageKey: 'eg_os_refresh_token',
    contextStorageKey: 'eg_os_user_context',
    enforceMFA: true,
    maxFailedLogins: 5
  },

  theme: {
    default: 'light',
    storageKey: 'eg_theme',
    colors: {
      primary: '#2563eb',
      danger: '#dc2626',
      success: '#16a34a',
      warning: '#ea580c',
      info: '#0284c7'
    }
  }
};

window.ENV = {
  API_BASE_URL: APP_CONFIG.apiBaseUrl,
  MODE: APP_CONFIG.env,
  VERSION: APP_CONFIG.appVersion
};

window.APP_CONFIG = APP_CONFIG;