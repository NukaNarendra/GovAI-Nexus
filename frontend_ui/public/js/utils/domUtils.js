const domUtils = {

  sanitizeHTML(str) {
      if (!str) return '';
      const temp = document.createElement('div');
      temp.textContent = str;
      return temp.innerHTML;
  },

  createElement(tag, attributes = {}, children = []) {
      const element = document.createElement(tag);

      for (const [key, value] of Object.entries(attributes)) {
          if (key === 'className' || key === 'class') {
              element.className = value;
          } else if (key === 'dataset') {
              for (const [dataKey, dataValue] of Object.entries(value)) {
                  element.dataset[dataKey] = dataValue;
              }
          } else if (key === 'style' && typeof value === 'object') {
              for (const [styleKey, styleValue] of Object.entries(value)) {
                  element.style[styleKey] = styleValue;
              }
          } else if (key === 'innerHTML') {
              element.innerHTML = value;
          } else if (key === 'textContent' || key === 'innerText') {
              element.textContent = value;
          } else if (key.startsWith('on') && typeof value === 'function') {
              const eventName = key.toLowerCase().substring(2);
              element.addEventListener(eventName, value);
          } else if (key === 'aria') {
              for (const [ariaKey, ariaValue] of Object.entries(value)) {
                  element.setAttribute(`aria-${ariaKey}`, ariaValue);
              }
          } else if (value !== null && value !== false) {
              element.setAttribute(key, value === true ? '' : value);
          }
      }

      if (!Array.isArray(children)) {
          children = [children];
      }

      children.forEach(child => {
          if (child instanceof Node) {
              element.appendChild(child);
          } else if (child !== null && child !== undefined) {
              element.appendChild(document.createTextNode(String(child)));
          }
      });

      return element;
  },

  clearChildren(element) {
      if (typeof element === 'string') {
          element = document.querySelector(element);
      }
      if (!element) return;
      while (element.firstChild) {
          element.removeChild(element.firstChild);
      }
  },

  delegateEvent(parentSelector, eventType, childSelector, handler) {
      const parent = typeof parentSelector === 'string' ? document.querySelector(parentSelector) : parentSelector;
      if (!parent) return null;

      const listener = function(event) {
          let target = event.target;
          while (target && target !== parent) {
              if (target.matches && target.matches(childSelector)) {
                  handler.call(target, event, target);
                  break;
              }
              target = target.parentNode;
          }
      };

      parent.addEventListener(eventType, listener);
      return () => parent.removeEventListener(eventType, listener);
  },

  addClass(element, ...classNames) {
      const el = this._resolveElement(element);
      if (el && el.classList) {
          classNames.forEach(className => {
              if (className) el.classList.add(...className.split(' ').filter(Boolean));
          });
      }
      return this;
  },

  removeClass(element, ...classNames) {
      const el = this._resolveElement(element);
      if (el && el.classList) {
          classNames.forEach(className => {
              if (className) el.classList.remove(...className.split(' ').filter(Boolean));
          });
      }
      return this;
  },

  toggleClass(element, className, force) {
      const el = this._resolveElement(element);
      if (el && el.classList) {
          if (typeof force === 'boolean') {
              el.classList.toggle(className, force);
          } else {
              el.classList.toggle(className);
          }
      }
      return this;
  },

  hasClass(element, className) {
      const el = this._resolveElement(element);
      return el && el.classList ? el.classList.contains(className) : false;
  },

  show(element, displayStyle = 'block') {
      const el = this._resolveElement(element);
      if (el) el.style.display = displayStyle;
      return this;
  },

  hide(element) {
      const el = this._resolveElement(element);
      if (el) el.style.display = 'none';
      return this;
  },

  toggleVisibility(element, displayStyle = 'block') {
      const el = this._resolveElement(element);
      if (el) {
          if (window.getComputedStyle(el).display === 'none') {
              el.style.display = displayStyle;
          } else {
              el.style.display = 'none';
          }
      }
      return this;
  },

  setAttributes(element, attributes) {
      const el = this._resolveElement(element);
      if (!el) return this;
      for (const [key, value] of Object.entries(attributes)) {
          if (value === null || value === false) {
              el.removeAttribute(key);
          } else {
              el.setAttribute(key, value === true ? '' : value);
          }
      }
      return this;
  },

  getClosest(element, selector) {
      const el = this._resolveElement(element);
      if (!el) return null;
      if (el.closest) return el.closest(selector);

      let target = el;
      while (target && target.nodeType === 1) {
          if (target.matches && target.matches(selector)) return target;
          target = target.parentNode;
      }
      return null;
  },

  insertAfter(newNode, referenceNode) {
      const ref = this._resolveElement(referenceNode);
      const nw = this._resolveElement(newNode);
      if (ref && ref.parentNode && nw) {
          ref.parentNode.insertBefore(nw, ref.nextSibling);
      }
      return this;
  },

  removeNode(element) {
      const el = this._resolveElement(element);
      if (el && el.parentNode) {
          el.parentNode.removeChild(el);
      }
      return this;
  },

  getFormValues(formElement) {
      const form = this._resolveElement(formElement);
      if (!form) return {};

      const data = new FormData(form);
      const values = {};

      for (let [key, value] of data.entries()) {
          if (values[key] !== undefined) {
              if (!Array.isArray(values[key])) {
                  values[key] = [values[key]];
              }
              values[key].push(value);
          } else {
              values[key] = value;
          }
      }
      return values;
  },

  fillFormValues(formElement, data) {
      const form = this._resolveElement(formElement);
      if (!form || !data) return this;

      Object.keys(data).forEach(key => {
          const input = form.querySelector(`[name="${key}"]`);
          if (input) {
              if (input.type === 'checkbox' || input.type === 'radio') {
                  input.checked = !!data[key];
              } else {
                  input.value = data[key];
              }
          }
      });
      return this;
  },

  createLoader(size = 'medium', colorClass = 'text-blue-600') {
      const sizeClasses = {
          small: 'w-4 h-4',
          medium: 'w-8 h-8',
          large: 'w-12 h-12'
      };
      const dimClass = sizeClasses[size] || sizeClasses.medium;

      return this.createElement('div', { className: 'flex justify-center items-center' }, [
          this.createElement('svg', {
              className: `animate-spin ${dimClass} ${colorClass}`,
              xmlns: 'http://www.w3.org/2000/svg',
              fill: 'none',
              viewBox: '0 0 24 24'
          }, [
              this.createElement('circle', {
                  className: 'opacity-25',
                  cx: '12',
                  cy: '12',
                  r: '10',
                  stroke: 'currentColor',
                  'stroke-width': '4'
              }),
              this.createElement('path', {
                  className: 'opacity-75',
                  fill: 'currentColor',
                  d: 'M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z'
              })
          ])
      ]);
  },

  debounce(func, wait) {
      let timeout;
      return function executedFunction(...args) {
          const later = () => {
              clearTimeout(timeout);
              func(...args);
          };
          clearTimeout(timeout);
          timeout = setTimeout(later, wait);
      };
  },

  throttle(func, limit) {
      let inThrottle;
      return function(...args) {
          if (!inThrottle) {
              func(...args);
              inThrottle = true;
              setTimeout(() => inThrottle = false, limit);
          }
      };
  },

  observeIntersection(selector, callback, options = {}) {
      const defaultOptions = {
          root: null,
          rootMargin: '0px',
          threshold: 0.1
      };

      const observer = new IntersectionObserver((entries) => {
          entries.forEach(entry => {
              if (entry.isIntersecting) {
                  callback(entry.target, entry);
              }
          });
      }, { ...defaultOptions, ...options });

      const elements = typeof selector === 'string' ? document.querySelectorAll(selector) : [selector];
      elements.forEach(el => observer.observe(el));

      return observer;
  },

  trapFocus(element) {
      const el = this._resolveElement(element);
      if (!el) return null;

      const focusableElements = el.querySelectorAll(
          'a[href], button, textarea, input[type="text"], input[type="radio"], input[type="checkbox"], select, select, details, [tabindex]:not([tabindex="-1"])'
      );

      if (focusableElements.length === 0) return null;

      const firstFocusableElement = focusableElements[0];
      const lastFocusableElement = focusableElements[focusableElements.length - 1];

      const keydownHandler = function(e) {
          let isTabPressed = e.key === 'Tab' || e.keyCode === 9;

          if (!isTabPressed) return;

          if (e.shiftKey) {
              if (document.activeElement === firstFocusableElement) {
                  lastFocusableElement.focus();
                  e.preventDefault();
              }
          } else {
              if (document.activeElement === lastFocusableElement) {
                  firstFocusableElement.focus();
                  e.preventDefault();
              }
          }
      };

      el.addEventListener('keydown', keydownHandler);
      firstFocusableElement.focus();

      return () => el.removeEventListener('keydown', keydownHandler);
  },

  _resolveElement(element) {
      if (!element) return null;
      if (typeof element === 'string') return document.querySelector(element);
      if (element instanceof Node) return element;
      if (element.jquery || element.length !== undefined) return element[0];
      return null;
  }
};

window.domUtils = domUtils;