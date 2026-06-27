class AuthStore {
  constructor() {
      this.subscribers = new Set();
      this.tokenKey = 'access_token';
      this.refreshKey = 'refresh_token';
      this.contextKey = 'user_context';
      this.storagePrefix = 'eg_os_';
      this.idleTimeout = 15 * 60 * 1000;
      this.idleTimer = null;
      this.lastActivity = Date.now();
      this.crossTabChannel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('auth_sync') : null;

      this.roles = {
          SYSTEM_ADMIN: 100,
          COMPLIANCE_OFFICER: 80,
          RISK_ANALYST: 60,
          AUDITOR: 40,
          VIEW_ONLY: 20
      };

      this.permissions = {
          EXECUTE_TRANSACTION: [this.roles.SYSTEM_ADMIN],
          APPROVE_HITL: [this.roles.SYSTEM_ADMIN, this.roles.COMPLIANCE_OFFICER],
          VIEW_HITL: [this.roles.SYSTEM_ADMIN, this.roles.COMPLIANCE_OFFICER, this.roles.RISK_ANALYST, this.roles.AUDITOR],
          VIEW_AUDIT: [this.roles.SYSTEM_ADMIN, this.roles.COMPLIANCE_OFFICER, this.roles.RISK_ANALYST, this.roles.AUDITOR, this.roles.VIEW_ONLY],
          EXPORT_AUDIT: [this.roles.SYSTEM_ADMIN, this.roles.AUDITOR],
          MANAGE_USERS: [this.roles.SYSTEM_ADMIN]
      };

      this.initCrossTabSync();
      this.initIdleTracking();
  }

  obfuscate(str) {
      if (!str) return str;
      return btoa(encodeURIComponent(str)).split('').reverse().join('');
  }

  deobfuscate(str) {
      if (!str) return str;
      try {
          return decodeURIComponent(atob(str.split('').reverse().join('')));
      } catch {
          return null;
      }
  }

  setSecureItem(key, value) {
      const prefixedKey = this.storagePrefix + key;
      const stringValue = typeof value === 'object' ? JSON.stringify(value) : String(value);
      localStorage.setItem(prefixedKey, this.obfuscate(stringValue));
  }

  getSecureItem(key, isJson = false) {
      const prefixedKey = this.storagePrefix + key;
      const raw = localStorage.getItem(prefixedKey);
      if (!raw) return null;
      const decoded = this.deobfuscate(raw);
      if (!decoded) return null;
      if (isJson) {
          try {
              return JSON.parse(decoded);
          } catch {
              return null;
          }
      }
      return decoded;
  }

  removeSecureItem(key) {
      localStorage.removeItem(this.storagePrefix + key);
  }

  subscribe(callback) {
      this.subscribers.add(callback);
      return () => this.subscribers.delete(callback);
  }

  notifySubscribers(event, data) {
      this.subscribers.forEach(cb => cb(event, data));
  }

  initCrossTabSync() {
      if (this.crossTabChannel) {
          this.crossTabChannel.onmessage = (event) => {
              if (event.data.type === 'LOGOUT') {
                  this.clearLocalSession();
                  window.location.href = '/index.html?reason=remote_logout';
              } else if (event.data.type === 'LOGIN') {
                  this.notifySubscribers('login_sync', this.getUserContext());
              }
          };
      } else {
          window.addEventListener('storage', (event) => {
              if (event.key === this.storagePrefix + this.tokenKey && !event.newValue) {
                  this.clearLocalSession();
                  window.location.href = '/index.html?reason=remote_logout';
              }
          });
      }
  }

  initIdleTracking() {
      const resetTimer = () => {
          this.lastActivity = Date.now();
          this.setSecureItem('last_activity', this.lastActivity.toString());
      };

      const checkIdle = () => {
          if (!this.isAuthenticated()) return;
          const storedLast = parseInt(this.getSecureItem('last_activity') || this.lastActivity);
          if (Date.now() - storedLast > this.idleTimeout) {
              this.logout('idle_timeout');
          }
      };

      ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'].forEach(evt => {
          document.addEventListener(evt, resetTimer, { passive: true, capture: true });
      });

      setInterval(checkIdle, 60000);
  }

  parseJwt(token) {
      try {
          const base64Url = token.split('.')[1];
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
              return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
          }).join(''));
          return JSON.parse(jsonPayload);
      } catch (e) {
          return null;
      }
  }

  setSession(tokens, userContext) {
      localStorage.setItem(this.tokenKey, tokens.access_token);
      if (tokens.refresh_token) {
          localStorage.setItem(this.refreshKey, tokens.refresh_token);
      }
      this.setSecureItem(this.contextKey, userContext);

      if (this.crossTabChannel) {
          this.crossTabChannel.postMessage({ type: 'LOGIN' });
      }
      this.notifySubscribers('login', userContext);
      this.lastActivity = Date.now();
      this.setSecureItem('last_activity', this.lastActivity.toString());
  }

  clearLocalSession() {
      localStorage.removeItem(this.tokenKey);
      localStorage.removeItem(this.refreshKey);
      this.removeSecureItem(this.contextKey);
      this.removeSecureItem('last_activity');
      this.notifySubscribers('logout', null);
  }

  logout(reason = 'user_initiated') {
      this.clearLocalSession();
      if (this.crossTabChannel) {
          this.crossTabChannel.postMessage({ type: 'LOGOUT', reason });
      }
      window.location.href = `/index.html?reason=${reason}`;
  }

  getToken() {
      return localStorage.getItem(this.tokenKey);
  }

  isAuthenticated() {
      const token = this.getToken();
      if (!token) return false;

      const decoded = this.parseJwt(token);
      if (!decoded || !decoded.exp) return false;

      const isExpired = (decoded.exp * 1000) < Date.now();
      if (isExpired) {
          const hasRefresh = !!localStorage.getItem(this.refreshKey);
          return hasRefresh; 
      }
      return true;
  }

  getUserContext() {
      return this.getSecureItem(this.contextKey, true);
  }

  hasRole(requiredRole) {
      const context = this.getUserContext();
      if (!context || !context.role) return false;
      const userRoleValue = this.roles[context.role] || 0;
      const requiredRoleValue = this.roles[requiredRole] || 0;
      return userRoleValue >= requiredRoleValue;
  }

  hasPermission(permission) {
      const context = this.getUserContext();
      if (!context || !context.role) return false;

      const allowedRoles = this.permissions[permission];
      if (!allowedRoles) return false;

      const userRoleValue = this.roles[context.role] || 0;
      return allowedRoles.includes(userRoleValue) || userRoleValue >= this.roles.SYSTEM_ADMIN;
  }

  enforceAuth() {
      if (!this.isAuthenticated()) {
          const currentPath = window.location.pathname;
          if (!currentPath.endsWith('index.html') && currentPath !== '/') {
              this.setSecureItem('redirect_after_login', window.location.href);
              window.location.href = '/index.html';
          }
      }
  }

  enforcePermission(permission, fallbackUrl = '/dashboard.html') {
      this.enforceAuth();
      if (!this.hasPermission(permission)) {
          window.location.href = fallbackUrl;
      }
  }

  getRedirectUrl() {
      const url = this.getSecureItem('redirect_after_login');
      this.removeSecureItem('redirect_after_login');
      return url || '/dashboard.html';
  }

  getTimeUntilExpiry() {
      const token = this.getToken();
      if (!token) return 0;
      const decoded = this.parseJwt(token);
      if (!decoded || !decoded.exp) return 0;
      return Math.max(0, (decoded.exp * 1000) - Date.now());
  }

  refreshSessionContext() {
      const token = this.getToken();
      if (!token) return null;
      const decoded = this.parseJwt(token);
      if (!decoded) return null;

      let currentContext = this.getUserContext() || {};
      if (decoded.sub) currentContext.id = decoded.sub;
      if (decoded.role) currentContext.role = decoded.role;

      this.setSecureItem(this.contextKey, currentContext);
      return currentContext;
  }

  getFingerprint() {
      let nav = window.navigator;
      let screen = window.screen;
      let guid = nav.mimeTypes.length;
      guid += nav.userAgent.replace(/\D+/g, '');
      guid += nav.plugins.length;
      guid += screen.height || '';
      guid += screen.width || '';
      guid += screen.pixelDepth || '';
      return guid;
  }
}

window.authStore = new AuthStore();