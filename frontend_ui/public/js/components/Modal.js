class ModalManager {
  constructor() {
      this.modals = new Map();
      this.backdrop = null;
      this.stack = [];
      this.baseZIndex = 1000;
      this.initBackdrop();
      this.handleKeydown = this.handleKeydown.bind(this);
      document.addEventListener('keydown', this.handleKeydown);
  }

  initBackdrop() {
      this.backdrop = window.domUtils.createElement('div', {
          className: 'fixed inset-0 bg-gray-900 bg-opacity-50 backdrop-blur-sm transition-opacity duration-300 opacity-0 pointer-events-none',
          style: { zIndex: this.baseZIndex - 1 }
      });
      document.body.appendChild(this.backdrop);
  }

  updateBackdrop() {
      if (this.stack.length > 0) {
          this.backdrop.classList.remove('opacity-0', 'pointer-events-none');
          this.backdrop.classList.add('opacity-100');
          const topZIndex = this.baseZIndex + (this.stack.length * 10) - 5;
          this.backdrop.style.zIndex = topZIndex;
          document.body.style.overflow = 'hidden';
      } else {
          this.backdrop.classList.remove('opacity-100');
          this.backdrop.classList.add('opacity-0', 'pointer-events-none');
          this.backdrop.style.zIndex = this.baseZIndex - 1;
          document.body.style.overflow = '';
      }
  }

  register(modal) {
      this.modals.set(modal.id, modal);
  }

  unregister(modalId) {
      this.modals.delete(modalId);
      this.removeFromStack(modalId);
  }

  pushToStack(modalId) {
      if (!this.stack.includes(modalId)) {
          this.stack.push(modalId);
          this.updateBackdrop();
      }
  }

  removeFromStack(modalId) {
      const index = this.stack.indexOf(modalId);
      if (index > -1) {
          this.stack.splice(index, 1);
          this.updateBackdrop();
          if (this.stack.length > 0) {
              const topModalId = this.stack[this.stack.length - 1];
              const topModal = this.modals.get(topModalId);
              if (topModal && topModal.elements.container) {
                  topModal.elements.container.focus();
              }
          }
      }
  }

  handleKeydown(e) {
      if (e.key === 'Escape' && this.stack.length > 0) {
          const topModalId = this.stack[this.stack.length - 1];
          const modal = this.modals.get(topModalId);
          if (modal && modal.options.closeOnEscape) {
              modal.close();
          }
      }
  }
}

const modalManager = new ModalManager();

class Modal {
  constructor(options = {}) {
      this.id = 'modal_' + Math.random().toString(36).substr(2, 9);
      this.options = {
          title: '',
          content: '',
          size: 'md',
          closeOnEscape: true,
          closeOnBackdrop: true,
          showCloseIcon: true,
          destroyOnClose: true,
          draggable: false,
          buttons: [],
          onOpen: null,
          onClose: null,
          ...options
      };

      this.elements = {
          wrapper: null,
          container: null,
          header: null,
          body: null,
          footer: null,
          closeBtn: null
      };

      this.isOpen = false;
      this.releaseFocus = null;
      this.buildDOM();
      modalManager.register(this);
  }

  getSizeClass() {
      const sizes = {
          sm: 'max-w-md',
          md: 'max-w-lg',
          lg: 'max-w-2xl',
          xl: 'max-w-4xl',
          full: 'max-w-[95vw] h-[95vh]'
      };
      return sizes[this.options.size] || sizes.md;
  }

  buildDOM() {
      this.elements.wrapper = window.domUtils.createElement('div', {
          id: this.id,
          className: 'fixed inset-0 flex items-center justify-center pointer-events-none hidden',
          style: { zIndex: modalManager.baseZIndex },
          aria: { hidden: 'true', modal: 'true' },
          role: 'dialog'
      });

      this.elements.container = window.domUtils.createElement('div', {
          className: `bg-white rounded-xl shadow-2xl flex flex-col pointer-events-auto w-full mx-4 transform scale-95 opacity-0 transition-all duration-300 ${this.getSizeClass()}`,
          tabindex: '-1'
      });

      if (this.options.title || this.options.showCloseIcon) {
          this.buildHeader();
      }

      this.elements.body = window.domUtils.createElement('div', {
          className: 'p-6 overflow-y-auto flex-1 text-gray-700'
      });

      if (typeof this.options.content === 'string') {
          this.elements.body.innerHTML = window.domUtils.sanitizeHTML(this.options.content);
      } else if (this.options.content instanceof Node) {
          this.elements.body.appendChild(this.options.content);
      }

      this.elements.container.appendChild(this.elements.body);

      if (this.options.buttons && this.options.buttons.length > 0) {
          this.buildFooter();
      }

      this.elements.wrapper.appendChild(this.elements.container);
      document.body.appendChild(this.elements.wrapper);

      if (this.options.closeOnBackdrop) {
          this.elements.wrapper.addEventListener('mousedown', (e) => {
              if (e.target === this.elements.wrapper) {
                  this.close();
              }
          });
      }
  }

  buildHeader() {
      const headerClasses = 'flex justify-between items-center px-6 py-4 border-b border-gray-200 bg-gray-50 rounded-t-xl';
      this.elements.header = window.domUtils.createElement('div', {
          className: headerClasses + (this.options.draggable ? ' cursor-move select-none' : '')
      });

      const titleEl = window.domUtils.createElement('h3', {
          className: 'text-lg font-semibold text-gray-900',
          textContent: this.options.title
      });
      this.elements.header.appendChild(titleEl);

      if (this.options.showCloseIcon) {
          this.elements.closeBtn = window.domUtils.createElement('button', {
              className: 'text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded p-1 transition-colors',
              aria: { label: 'Close modal' },
              onclick: () => this.close(),
              innerHTML: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>'
          });
          this.elements.header.appendChild(this.elements.closeBtn);
      }

      this.elements.container.appendChild(this.elements.header);

      if (this.options.draggable) {
          this.setupDraggable();
      }
  }

  buildFooter() {
      this.elements.footer = window.domUtils.createElement('div', {
          className: 'px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-xl flex justify-end gap-3'
      });

      this.options.buttons.forEach(btnConfig => {
          const btnClass = btnConfig.type === 'primary' 
              ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm'
              : btnConfig.type === 'danger'
              ? 'bg-red-600 text-white hover:bg-red-700 shadow-sm'
              : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50';

          const btn = window.domUtils.createElement('button', {
              className: `px-4 py-2 text-sm font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors ${btnClass}`,
              textContent: btnConfig.text,
              onclick: (e) => {
                  if (typeof btnConfig.onClick === 'function') {
                      btnConfig.onClick(this, e);
                  }
              }
          });
          this.elements.footer.appendChild(btn);
      });

      this.elements.container.appendChild(this.elements.footer);
  }

  setupDraggable() {
      let isDragging = false;
      let startX, startY, initialX, initialY;

      const onMouseDown = (e) => {
          if (e.target === this.elements.closeBtn || this.elements.closeBtn.contains(e.target)) return;
          isDragging = true;
          startX = e.clientX;
          startY = e.clientY;

          const rect = this.elements.container.getBoundingClientRect();
          const wrapperRect = this.elements.wrapper.getBoundingClientRect();

          initialX = rect.left - wrapperRect.left - (wrapperRect.width - rect.width) / 2;
          initialY = rect.top - wrapperRect.top - (wrapperRect.height - rect.height) / 2;

          this.elements.container.style.transition = 'none';
          document.addEventListener('mousemove', onMouseMove);
          document.addEventListener('mouseup', onMouseUp);
      };

      const onMouseMove = (e) => {
          if (!isDragging) return;
          const dx = e.clientX - startX;
          const dy = e.clientY - startY;
          this.elements.container.style.transform = `translate(${initialX + dx}px, ${initialY + dy}px) scale(1)`;
      };

      const onMouseUp = () => {
          isDragging = false;
          this.elements.container.style.transition = 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease-out';
          document.removeEventListener('mousemove', onMouseMove);
          document.removeEventListener('mouseup', onMouseUp);
      };

      this.elements.header.addEventListener('mousedown', onMouseDown);
  }

  open() {
      if (this.isOpen) return;
      this.isOpen = true;

      window.domUtils.show(this.elements.wrapper, 'flex');
      this.elements.wrapper.setAttribute('aria-hidden', 'false');

      modalManager.pushToStack(this.id);

      const zIndex = modalManager.baseZIndex + (modalManager.stack.length * 10);
      this.elements.wrapper.style.zIndex = zIndex;

      requestAnimationFrame(() => {
          this.elements.container.classList.remove('scale-95', 'opacity-0');
          this.elements.container.classList.add('scale-100', 'opacity-100');
      });

      this.releaseFocus = window.domUtils.trapFocus(this.elements.container);

      if (typeof this.options.onOpen === 'function') {
          this.options.onOpen(this);
      }
  }

  close() {
      if (!this.isOpen) return;
      this.isOpen = false;

      this.elements.container.classList.remove('scale-100', 'opacity-100');
      this.elements.container.classList.add('scale-95', 'opacity-0');
      this.elements.wrapper.setAttribute('aria-hidden', 'true');

      if (this.releaseFocus) {
          this.releaseFocus();
          this.releaseFocus = null;
      }

      setTimeout(() => {
          window.domUtils.hide(this.elements.wrapper);
          modalManager.removeFromStack(this.id);

          if (typeof this.options.onClose === 'function') {
              this.options.onClose(this);
          }

          if (this.options.destroyOnClose) {
              this.destroy();
          }
      }, 300);
  }

  setContent(htmlOrNode) {
      window.domUtils.clearChildren(this.elements.body);
      if (typeof htmlOrNode === 'string') {
          this.elements.body.innerHTML = window.domUtils.sanitizeHTML(htmlOrNode);
      } else if (htmlOrNode instanceof Node) {
          this.elements.body.appendChild(htmlOrNode);
      }
  }

  destroy() {
      if (this.elements.wrapper && this.elements.wrapper.parentNode) {
          this.elements.wrapper.parentNode.removeChild(this.elements.wrapper);
      }
      modalManager.unregister(this.id);
  }

  static alert(title, message, options = {}) {
      return new Promise(resolve => {
          const modal = new Modal({
              title: title,
              content: `<div class="flex items-start gap-4">
                          <div class="flex-shrink-0 w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
                              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                          </div>
                          <div class="mt-1"><p class="text-sm text-gray-600">${window.domUtils.sanitizeHTML(message)}</p></div>
                        </div>`,
              size: 'md',
              buttons: [
                  { text: options.confirmText || 'OK', type: 'primary', onClick: (m) => { m.close(); resolve(true); } }
              ],
              onClose: () => resolve(false),
              ...options
          });
          modal.open();
      });
  }

  static confirm(title, message, options = {}) {
      return new Promise(resolve => {
          const modal = new Modal({
              title: title,
              content: `<div class="flex items-start gap-4">
                          <div class="flex-shrink-0 w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center text-orange-600">
                              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                          </div>
                          <div class="mt-1"><p class="text-sm text-gray-600">${window.domUtils.sanitizeHTML(message)}</p></div>
                        </div>`,
              size: 'md',
              buttons: [
                  { text: options.cancelText || 'Cancel', type: 'default', onClick: (m) => { m.close(); resolve(false); } },
                  { text: options.confirmText || 'Confirm', type: options.isDanger ? 'danger' : 'primary', onClick: (m) => { m.close(); resolve(true); } }
              ],
              onClose: () => resolve(false),
              ...options
          });
          modal.open();
      });
  }

  static prompt(title, message, inputConfig = {}, options = {}) {
      return new Promise(resolve => {
          const inputId = 'prompt_input_' + Math.random().toString(36).substr(2, 9);
          const inputType = inputConfig.type || 'text';
          const placeholder = inputConfig.placeholder || '';
          const defaultValue = inputConfig.value || '';

          const content = `
              <div class="space-y-4">
                  <p class="text-sm text-gray-600">${window.domUtils.sanitizeHTML(message)}</p>
                  <div>
                      <input type="${inputType}" id="${inputId}" value="${window.domUtils.sanitizeHTML(defaultValue)}" placeholder="${window.domUtils.sanitizeHTML(placeholder)}" 
                          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm">
                      <p id="${inputId}_error" class="mt-1 text-xs text-red-600 hidden"></p>
                  </div>
              </div>
          `;

          const modal = new Modal({
              title: title,
              content: content,
              size: 'md',
              onOpen: (m) => {
                  const inputEl = m.elements.body.querySelector(`#${inputId}`);
                  if (inputEl) setTimeout(() => inputEl.focus(), 100);
              },
              buttons: [
                  { text: 'Cancel', type: 'default', onClick: (m) => { m.close(); resolve(null); } },
                  { text: 'Submit', type: 'primary', onClick: (m) => {
                      const val = m.elements.body.querySelector(`#${inputId}`).value;
                      if (inputConfig.required && !val.trim()) {
                          const errEl = m.elements.body.querySelector(`#${inputId}_error`);
                          errEl.textContent = 'This field is required';
                          window.domUtils.show(errEl);
                          return;
                      }
                      m.close();
                      resolve(val);
                  }}
              ],
              onClose: () => resolve(null),
              ...options
          });
          modal.open();
      });
  }
}
window.Modal = Modal;