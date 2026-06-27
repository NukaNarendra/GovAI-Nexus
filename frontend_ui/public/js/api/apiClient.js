class CircuitBreaker {
  constructor(failureThreshold, recoveryTimeout) {
      this.failureThreshold = failureThreshold;
      this.recoveryTimeout = recoveryTimeout;
      this.failures = new Map();
      this.state = new Map();
      this.nextAttempt = new Map();
  }
  recordFailure(endpoint) {
      const count = (this.failures.get(endpoint) || 0) + 1;
      this.failures.set(endpoint, count);
      if (count >= this.failureThreshold) {
          this.state.set(endpoint, 'OPEN');
          this.nextAttempt.set(endpoint, Date.now() + this.recoveryTimeout);
      }
  }
  recordSuccess(endpoint) {
      this.failures.delete(endpoint);
      this.state.set(endpoint, 'CLOSED');
      this.nextAttempt.delete(endpoint);
  }
  canRequest(endpoint) {
      const currentState = this.state.get(endpoint) || 'CLOSED';
      if (currentState === 'CLOSED') return true;
      const attemptTime = this.nextAttempt.get(endpoint) || 0;
      if (Date.now() > attemptTime) {
          this.state.set(endpoint, 'HALF_OPEN');
          return true;
      }
      return false;
  }
}

class ApiError extends Error {
  constructor(message, status, payload, endpoint) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.payload = payload;
      this.endpoint = endpoint;
      this.timestamp = new Date().toISOString();
  }
}

class NetworkError extends Error {
  constructor(message, endpoint) {
      super(message);
      this.name = 'NetworkError';
      this.endpoint = endpoint;
      this.timestamp = new Date().toISOString();
  }
}

class TimeoutError extends Error {
  constructor(message, endpoint) {
      super(message);
      this.name = 'TimeoutError';
      this.endpoint = endpoint;
      this.timestamp = new Date().toISOString();
  }
}

class ApiClient {
  constructor() {
      this.baseURL = window.ENV?.API_BASE_URL || 'http://localhost:8000/api/v1';
      this.defaultTimeout = 30000;
      this.maxRetries = 3;
      this.baseBackoff = 1000;
      this.circuitBreaker = new CircuitBreaker(5, 60000);
      this.requestInterceptors = [];
      this.responseInterceptors = [];
      this.isRefreshing = false;
      this.refreshSubscribers = [];
      this.activeRequests = new Map();
      this.cache = new Map();

      this.setupDefaultInterceptors();
  }

  addRequestInterceptor(interceptor) {
      this.requestInterceptors.push(interceptor);
  }

  addResponseInterceptor(interceptor) {
      this.responseInterceptors.push(interceptor);
  }

  setupDefaultInterceptors() {
      this.addRequestInterceptor(async (config) => {
          const token = localStorage.getItem('access_token');
          if (token) {
              config.headers = config.headers || {};
              config.headers['Authorization'] = `Bearer ${token}`;
          }
          if (!config.headers['Content-Type'] && !(config.body instanceof FormData)) {
              config.headers['Content-Type'] = 'application/json';
          }
          config.headers['X-Client-Timestamp'] = new Date().toISOString();
          config.headers['X-Correlation-ID'] = this.generateUUID();
          return config;
      });

      this.addResponseInterceptor(async (response, config) => {
          if (!response.ok) {
              if (response.status === 401 && !config._isRetry) {
                  return this.handleTokenRefresh(config);
              }
              const errorData = await this.parseErrorData(response);
              throw new ApiError(
                  errorData.detail || errorData.message || 'API request failed',
                  response.status,
                  errorData,
                  config.url
              );
          }
          if (response.status === 204) return null;
          const contentType = response.headers.get('content-type');
          if (contentType && contentType.includes('application/json')) {
              return response.json();
          }
          if (contentType && (contentType.includes('application/pdf') || contentType.includes('image/'))) {
              return response.blob();
          }
          return response.text();
      });
  }

  generateUUID() {
      if (crypto && crypto.randomUUID) return crypto.randomUUID();
      return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
          const r = Math.random() * 16 | 0;
          const v = c === 'x' ? r : (r & 0x3 | 0x8);
          return v.toString(16);
      });
  }

  async parseErrorData(response) {
      try {
          const cloned = response.clone();
          const text = await cloned.text();
          return text ? JSON.parse(text) : {};
      } catch {
          return { detail: 'Unable to parse error response' };
      }
  }

  onTokenRefreshed(token) {
      this.refreshSubscribers.forEach((callback) => callback(token));
      this.refreshSubscribers = [];
  }

  addRefreshSubscriber(callback) {
      this.refreshSubscribers.push(callback);
  }

  async handleTokenRefresh(originalConfig) {
      if (!this.isRefreshing) {
          this.isRefreshing = true;
          const refreshToken = localStorage.getItem('refresh_token');

          if (!refreshToken) {
              this.isRefreshing = false;
              this.forceLogout();
              throw new Error('No refresh token available');
          }

          try {
              const response = await fetch(`${this.baseURL}/auth/refresh`, {
                  method: 'POST',
                  headers: {
                      'Content-Type': 'application/json',
                      'Authorization': `Bearer ${refreshToken}`
                  }
              });

              if (!response.ok) {
                  throw new Error('Refresh failed');
              }

              const data = await response.json();
              localStorage.setItem('access_token', data.access_token);
              if (data.refresh_token) {
                  localStorage.setItem('refresh_token', data.refresh_token);
              }

              this.isRefreshing = false;
              this.onTokenRefreshed(data.access_token);
          } catch (error) {
              this.isRefreshing = false;
              this.refreshSubscribers = [];
              this.forceLogout();
              throw error;
          }
      }

      return new Promise((resolve) => {
          this.addRefreshSubscriber((newToken) => {
              originalConfig.headers['Authorization'] = `Bearer ${newToken}`;
              originalConfig._isRetry = true;
              resolve(this.executeRequest(originalConfig));
          });
      });
  }

  forceLogout() {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user_context');
      window.location.href = '/index.html?reason=session_expired';
  }

  async executeRequest(config) {
      let finalConfig = { ...config };
      for (const interceptor of this.requestInterceptors) {
          finalConfig = await interceptor(finalConfig);
      }

      const url = finalConfig.url.startsWith('http') ? finalConfig.url : `${this.baseURL}${finalConfig.url}`;
      const method = (finalConfig.method || 'GET').toUpperCase();

      if (!this.circuitBreaker.canRequest(url)) {
          throw new Error(`Circuit breaker open for ${url}`);
      }

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), finalConfig.timeout || this.defaultTimeout);
      finalConfig.signal = controller.signal;

      if (finalConfig.params) {
          const query = new URLSearchParams();
          Object.entries(finalConfig.params).forEach(([key, value]) => {
              if (value !== undefined && value !== null) {
                  if (Array.isArray(value)) {
                      value.forEach(v => query.append(key, v));
                  } else {
                      query.append(key, value);
                  }
              }
          });
          const queryString = query.toString();
          if (queryString) {
              finalConfig.url = finalConfig.url.includes('?') 
                  ? `${finalConfig.url}&${queryString}` 
                  : `${finalConfig.url}?${queryString}`;
          }
      }

      const fetchOptions = {
          method,
          headers: finalConfig.headers,
          signal: finalConfig.signal,
          mode: 'cors'
      };

      if (finalConfig.body) {
          if (finalConfig.body instanceof FormData) {
              fetchOptions.body = finalConfig.body;
              delete fetchOptions.headers['Content-Type'];
          } else if (typeof finalConfig.body === 'object') {
              fetchOptions.body = JSON.stringify(finalConfig.body);
          } else {
              fetchOptions.body = finalConfig.body;
          }
      }

      try {
          const response = await fetch(url.includes('http') ? url : `${this.baseURL}${finalConfig.url}`, fetchOptions);
          clearTimeout(timeoutId);

          if (response.ok) {
              this.circuitBreaker.recordSuccess(url);
          }

          let finalResponse = response;
          for (const interceptor of this.responseInterceptors) {
              finalResponse = await interceptor(finalResponse, finalConfig);
          }
          return finalResponse;

      } catch (error) {
          clearTimeout(timeoutId);
          this.circuitBreaker.recordFailure(url);

          if (error.name === 'AbortError') {
              throw new TimeoutError(`Request to ${url} timed out`, url);
          }
          if (error instanceof ApiError) {
              throw error;
          }
          throw new NetworkError(error.message || 'Network request failed', url);
      }
  }

  async requestWithRetry(config, retries = this.maxRetries) {
      for (let i = 0; i < retries; i++) {
          try {
              return await this.executeRequest(config);
          } catch (error) {
              const isRetryable = 
                  error instanceof NetworkError || 
                  error instanceof TimeoutError || 
                  (error instanceof ApiError && [408, 429, 500, 502, 503, 504].includes(error.status));

              if (!isRetryable || i === retries - 1) {
                  throw error;
              }

              const delay = error.status === 429 
                  ? (parseInt(error.payload?.headers?.['retry-after'] || 1) * 1000)
                  : this.baseBackoff * Math.pow(2, i) + (Math.random() * 1000);

              await new Promise(resolve => setTimeout(resolve, delay));
          }
      }
  }

  async get(url, params = {}, options = {}) {
      const cacheKey = `${url}?${JSON.stringify(params)}`;
      if (options.cache && this.cache.has(cacheKey)) {
          const cached = this.cache.get(cacheKey);
          if (Date.now() - cached.timestamp < (options.cacheTTL || 60000)) {
              return cached.data;
          }
          this.cache.delete(cacheKey);
      }

      if (this.activeRequests.has(cacheKey)) {
          return this.activeRequests.get(cacheKey);
      }

      const requestPromise = this.requestWithRetry({ url, method: 'GET', params, ...options })
          .then(data => {
              if (options.cache) {
                  this.cache.set(cacheKey, { data, timestamp: Date.now() });
              }
              this.activeRequests.delete(cacheKey);
              return data;
          })
          .catch(err => {
              this.activeRequests.delete(cacheKey);
              throw err;
          });

      this.activeRequests.set(cacheKey, requestPromise);
      return requestPromise;
  }

  async post(url, body = {}, options = {}) {
      return this.requestWithRetry({ url, method: 'POST', body, ...options });
  }

  async put(url, body = {}, options = {}) {
      return this.requestWithRetry({ url, method: 'PUT', body, ...options });
  }

  async patch(url, body = {}, options = {}) {
      return this.requestWithRetry({ url, method: 'PATCH', body, ...options });
  }

  async delete(url, options = {}) {
      return this.requestWithRetry({ url, method: 'DELETE', ...options });
  }

  async upload(url, file, fieldName = 'file', additionalData = {}, options = {}) {
      const formData = new FormData();
      formData.append(fieldName, file);
      Object.entries(additionalData).forEach(([key, value]) => {
          formData.append(key, typeof value === 'object' ? JSON.stringify(value) : value);
      });

      const config = {
          url,
          method: 'POST',
          body: formData,
          timeout: 120000,
          ...options
      };

      return this.executeRequest(config);
  }
}

window.apiClient = new ApiClient();