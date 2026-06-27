const formatters = {
  locale: window.navigator.language || 'en-US',

  currencyMap: {
      USD: { locale: 'en-US', format: 'en-US' },
      EUR: { locale: 'de-DE', format: 'de-DE' },
      GBP: { locale: 'en-GB', format: 'en-GB' },
      JPY: { locale: 'ja-JP', format: 'ja-JP' },
      CHF: { locale: 'de-CH', format: 'de-CH' },
      AUD: { locale: 'en-AU', format: 'en-AU' },
      CAD: { locale: 'en-CA', format: 'en-CA' },
      INR: { locale: 'en-IN', format: 'en-IN' },
      CNY: { locale: 'zh-CN', format: 'zh-CN' },
      SGD: { locale: 'en-SG', format: 'en-SG' },
      HKD: { locale: 'en-HK', format: 'en-HK' },
      AED: { locale: 'ar-AE', format: 'en-AE' },
      BTC: { locale: 'en-US', format: 'en-US', fractionDigits: 8 },
      ETH: { locale: 'en-US', format: 'en-US', fractionDigits: 8 }
  },

  formatCurrency(amount, currencyCode = 'USD', compact = false) {
      if (amount === null || amount === undefined || isNaN(amount)) return '-';

      const numAmount = parseFloat(amount);
      const config = this.currencyMap[currencyCode.toUpperCase()] || this.currencyMap['USD'];

      const options = {
          style: 'currency',
          currency: currencyCode.toUpperCase(),
          minimumFractionDigits: config.fractionDigits || 2,
          maximumFractionDigits: config.fractionDigits || 2
      };

      if (compact && numAmount >= 10000) {
          options.notation = 'compact';
          options.compactDisplay = 'short';
          options.maximumFractionDigits = 1;
      }

      try {
          return new Intl.NumberFormat(config.format, options).format(numAmount);
      } catch (e) {
          return `${currencyCode} ${numAmount.toFixed(2)}`;
      }
  },

  formatDate(isoString, options = {}) {
      if (!isoString) return '-';
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return isoString;

      const defaultOptions = {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true
      };

      try {
          return new Intl.DateTimeFormat(this.locale, { ...defaultOptions, ...options }).format(date);
      } catch (e) {
          return date.toLocaleString();
      }
  },

  formatRelativeTime(isoString) {
      if (!isoString) return '-';
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return isoString;

      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffSec = Math.floor(diffMs / 1000);
      const diffMin = Math.floor(diffSec / 60);
      const diffHour = Math.floor(diffMin / 60);
      const diffDay = Math.floor(diffHour / 24);

      if (diffSec < 30) return 'Just now';
      if (diffSec < 60) return `${diffSec} seconds ago`;
      if (diffMin === 1) return '1 minute ago';
      if (diffMin < 60) return `${diffMin} minutes ago`;
      if (diffHour === 1) return '1 hour ago';
      if (diffHour < 24) return `${diffHour} hours ago`;
      if (diffDay === 1) return 'Yesterday';
      if (diffDay < 7) return `${diffDay} days ago`;

      return this.formatDate(isoString, { year: 'numeric', month: 'short', day: 'numeric' });
  },

  formatRiskScore(score) {
      if (score === null || score === undefined || isNaN(score)) {
          return { text: 'UNKNOWN', color: 'var(--color-gray-500)', bg: 'var(--color-gray-100)' };
      }

      const num = parseFloat(score);
      if (num >= 85) return { text: 'CRITICAL', color: 'var(--color-red-700)', bg: 'var(--color-red-100)', icon: 'alert-triangle' };
      if (num >= 65) return { text: 'HIGH', color: 'var(--color-orange-700)', bg: 'var(--color-orange-100)', icon: 'alert-circle' };
      if (num >= 35) return { text: 'MEDIUM', color: 'var(--color-yellow-700)', bg: 'var(--color-yellow-100)', icon: 'minus-circle' };
      return { text: 'LOW', color: 'var(--color-green-700)', bg: 'var(--color-green-100)', icon: 'check-circle' };
  },

  formatStatusBadge(status) {
      if (!status) return { text: 'UNKNOWN', class: 'badge-default' };
      const normalized = status.toUpperCase().replace(/\s+/g, '_');

      const mapping = {
          'CLEARED': 'badge-success',
          'APPROVED': 'badge-success',
          'EXECUTED': 'badge-success',
          'VERIFIED': 'badge-success',
          'PENDING_HITL': 'badge-warning',
          'HOLD_FOR_REVIEW': 'badge-warning',
          'UNDER_REVIEW': 'badge-warning',
          'MANUAL_REVIEW_REQUIRED': 'badge-warning',
          'BLOCKED': 'badge-error',
          'REJECTED': 'badge-error',
          'REJECTED_AUTO': 'badge-error',
          'FRAUD_SUSPECTED': 'badge-error',
          'EXPIRED': 'badge-neutral',
          'SYSTEM_ERROR': 'badge-neutral'
      };

      return {
          text: status.replace(/_/g, ' '),
          class: mapping[normalized] || 'badge-default'
      };
  },

  maskEmail(email) {
      if (!email || !email.includes('@')) return email;
      const [localPart, domain] = email.split('@');
      if (localPart.length <= 2) return `${localPart[0]}***@${domain}`;
      const maskedLocal = `${localPart[0]}${'*'.repeat(localPart.length - 2)}${localPart[localPart.length - 1]}`;
      return `${maskedLocal}@${domain}`;
  },

  maskAccount(accountString, visibleLast = 4) {
      if (!accountString) return '';
      const str = String(accountString).replace(/\s+/g, '');
      if (str.length <= visibleLast) return str;
      return `**** **** **** ${str.slice(-visibleLast)}`;
  },

  maskSSN(ssn) {
      if (!ssn) return '';
      const cleaned = String(ssn).replace(/\D/g, '');
      if (cleaned.length !== 9) return ssn;
      return `XXX-XX-${cleaned.slice(-4)}`;
  },

  formatBytes(bytes, decimals = 2) {
      if (bytes === 0) return '0 Bytes';
      if (!bytes || isNaN(bytes)) return '-';

      const k = 1024;
      const dm = decimals < 0 ? 0 : decimals;
      const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];

      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  },

  truncateText(text, maxLength = 50, useWordBoundary = true) {
      if (!text) return '';
      const str = String(text);
      if (str.length <= maxLength) return str;

      const subString = str.slice(0, maxLength - 1);
      if (useWordBoundary) {
          return (subString.substr(0, subString.lastIndexOf(' ')) || subString) + '...';
      }
      return subString + '...';
  },

  toCamelCase(str) {
      if (!str) return '';
      return str.replace(/(?:^\w|[A-Z]|\b\w)/g, (word, index) => {
          return index === 0 ? word.toLowerCase() : word.toUpperCase();
      }).replace(/\s+/g, '');
  },

  toKebabCase(str) {
      if (!str) return '';
      return str
          .match(/[A-Z]{2,}(?=[A-Z][a-z]+[0-9]*|\b)|[A-Z]?[a-z]+[0-9]*|[A-Z]|[0-9]+/g)
          .map(x => x.toLowerCase())
          .join('-');
  },

  toTitleCase(str) {
      if (!str) return '';
      return str.toLowerCase().split(/[_\s-]/).map(word => {
          return (word.charAt(0).toUpperCase() + word.slice(1));
      }).join(' ');
  },

  parseJwtClaims(token) {
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
  },

  generateRandomString(length = 16) {
      const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
      let result = '';
      const randomArray = new Uint8Array(length);
      if (window.crypto && window.crypto.getRandomValues) {
          window.crypto.getRandomValues(randomArray);
          for (let i = 0; i < length; i++) {
              result += chars[randomArray[i] % chars.length];
          }
      } else {
          for (let i = 0; i < length; i++) {
              result += chars.charAt(Math.floor(Math.random() * chars.length));
          }
      }
      return result;
  },

  serializeQueryParams(obj) {
      const str = [];
      for (let p in obj) {
          if (obj.hasOwnProperty(p) && obj[p] !== null && obj[p] !== undefined) {
              if (Array.isArray(obj[p])) {
                  obj[p].forEach(val => {
                      str.push(encodeURIComponent(p) + "=" + encodeURIComponent(val));
                  });
              } else {
                  str.push(encodeURIComponent(p) + "=" + encodeURIComponent(obj[p]));
              }
          }
      }
      return str.join("&");
  },

  calculatePercentage(value, total, decimals = 1) {
      if (!total || isNaN(total) || isNaN(value)) return '0%';
      const percent = (value / total) * 100;
      return `${percent.toFixed(decimals)}%`;
  },

  formatDuration(milliseconds) {
      if (isNaN(milliseconds) || milliseconds < 0) return '0ms';

      const ms = milliseconds % 1000;
      const seconds = Math.floor((milliseconds / 1000) % 60);
      const minutes = Math.floor((milliseconds / (1000 * 60)) % 60);
      const hours = Math.floor((milliseconds / (1000 * 60 * 60)) % 24);
      const days = Math.floor(milliseconds / (1000 * 60 * 60 * 24));

      const parts = [];
      if (days > 0) parts.push(`${days}d`);
      if (hours > 0) parts.push(`${hours}h`);
      if (minutes > 0) parts.push(`${minutes}m`);
      if (seconds > 0) parts.push(`${seconds}s`);
      if (parts.length === 0 || ms > 0 && parts.length < 2) parts.push(`${ms}ms`);

      return parts.slice(0, 2).join(' ');
  },

  extractDomain(url) {
      if (!url) return '';
      try {
          const parsed = new URL(url);
          return parsed.hostname;
      } catch (e) {
          const match = url.match(/^https?\:\/\/([^\/?#]+)(?:[\/?#]|$)/i);
          return match && match[1] ? match[1] : url;
      }
  }
};

window.formatters = formatters;