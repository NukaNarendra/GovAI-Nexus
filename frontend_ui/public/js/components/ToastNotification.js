class ToastManager {
  constructor() {
      this.positions = {
          'top-right': null,
          'top-left': null,
          'bottom-right': null,
          'bottom-left': null,
          'top-center': null,
          'bottom-center': null
      };
      this.maxToasts = 5;
      this.icons = {
          success: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
          error: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
          warning: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>',
          info: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
          loading: '<svg class="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>'
      };
      this.colors = {
          success: { bg: 'bg-white', border: 'border-green-500', text: 'text-gray-800', icon: 'text-green-500', progress: 'bg-green-500' },
          error: { bg: 'bg-white', border: 'border-red-500', text: 'text-gray-800', icon: 'text-red-500', progress: 'bg-red-500' },
          warning: { bg: 'bg-white', border: 'border-orange-500', text: 'text-gray-800', icon: 'text-orange-500', progress: 'bg-orange-500' },
          info: { bg: 'bg-white', border: 'border-blue-500', text: 'text-gray-800', icon: 'text-blue-500', progress: 'bg-blue-500' },
          loading: { bg: 'bg-white', border: 'border-gray-400', text: 'text-gray-800', icon: 'text-gray-500', progress: 'bg-gray-400' }
      };
  }

  getContainer(position) {
      if (!this.positions[position]) {
          const container = window.domUtils.createElement('div', {
              className: `fixed z-[9999] flex flex-col gap-3 pointer-events-none p-4 ${this.getPositionClasses(position)}`
          });
          document.body.appendChild(container);
          this.positions[position] = container;
      }
      return this.positions[position];
  }

  getPositionClasses(position) {
      const parts = position.split('-');
      let classes = '';
      if (parts[0] === 'top') classes += 'top-0 ';
      if (parts[0] === 'bottom') classes += 'bottom-0 flex-col-reverse ';
      if (parts[1] === 'right') classes += 'right-0 items-end ';
      if (parts[1] === 'left') classes += 'left-0 items-start ';
      if (parts[1] === 'center') classes += 'left-1/2 -translate-x-1/2 items-center ';
      return classes;
  }

  show(options) {
      const opt = {
          title: '',
          message: '',
          type: 'info',
          duration: 5000,
          position: 'top-right',
          dismissible: true,
          actionBtn: null,
          ...options
      };

      const container = this.getContainer(opt.position);

      if (container.children.length >= this.maxToasts) {
          const oldest = opt.position.startsWith('top') ? container.lastChild : container.firstChild;
          if (oldest && oldest.__toastInstance) oldest.__toastInstance.dismiss();
      }

      const toast = new Toast(opt, container, this);
      toast.mount();
      return toast;
  }

  success(message, title = 'Success', options = {}) {
      return this.show({ ...options, message, title, type: 'success' });
  }

  error(message, title = 'Error', options = {}) {
      return this.show({ ...options, message, title, type: 'error' });
  }

  warning(message, title = 'Warning', options = {}) {
      return this.show({ ...options, message, title, type: 'warning' });
  }

  info(message, title = 'Information', options = {}) {
      return this.show({ ...options, message, title, type: 'info' });
  }

  promise(promise, options = {}) {
      const opt = {
          loadingMsg: 'Processing...',
          successMsg: 'Completed successfully',
          errorMsg: 'Operation failed',
          ...options
      };

      const loadingToast = this.show({ message: opt.loadingMsg, type: 'loading', duration: 0, dismissible: false });

      return promise.then((res) => {
          loadingToast.dismiss();
          this.success(typeof opt.successMsg === 'function' ? opt.successMsg(res) : opt.successMsg);
          return res;
      }).catch((err) => {
          loadingToast.dismiss();
          this.error(typeof opt.errorMsg === 'function' ? opt.errorMsg(err) : opt.errorMsg);
          throw err;
      });
  }
}

class Toast {
  constructor(options, container, manager) {
      this.options = options;
      this.container = container;
      this.manager = manager;
      this.element = null;
      this.progressBar = null;
      this.timerId = null;
      this.startTime = Date.now();
      this.remaining = options.duration;
      this.isDismissed = false;

      this.swipeState = {
          isSwiping: false,
          startX: 0,
          currentX: 0
      };

      this.buildDOM();
  }

  buildDOM() {
      const theme = this.manager.colors[this.options.type];

      this.element = window.domUtils.createElement('div', {
          className: `relative flex flex-col w-80 sm:w-96 shadow-lg rounded-lg border-l-4 ${theme.bg} ${theme.border} overflow-hidden pointer-events-auto transform transition-all duration-300 translate-x-full opacity-0`
      });

      this.element.__toastInstance = this;

      const contentWrapper = window.domUtils.createElement('div', { className: 'p-4 flex items-start gap-3' });

      const iconWrapper = window.domUtils.createElement('div', {
          className: `flex-shrink-0 mt-0.5 ${theme.icon}`,
          innerHTML: this.manager.icons[this.options.type]
      });

      const textWrapper = window.domUtils.createElement('div', { className: 'flex-1 min-w-0' });

      if (this.options.title) {
          textWrapper.appendChild(window.domUtils.createElement('p', {
              className: `text-sm font-bold ${theme.text} mb-1`,
              textContent: this.options.title
          }));
      }

      textWrapper.appendChild(window.domUtils.createElement('p', {
          className: `text-sm text-gray-600 break-words`,
          innerHTML: window.domUtils.sanitizeHTML(this.options.message)
      }));

      if (this.options.actionBtn) {
          const btnWrapper = window.domUtils.createElement('div', { className: 'mt-3' });
          const btn = window.domUtils.createElement('button', {
              className: 'text-xs font-semibold text-blue-600 hover:text-blue-800 transition-colors focus:outline-none',
              textContent: this.options.actionBtn.text,
              onclick: (e) => {
                  if (typeof this.options.actionBtn.onClick === 'function') {
                      this.options.actionBtn.onClick(this, e);
                  }
              }
          });
          btnWrapper.appendChild(btn);
          textWrapper.appendChild(btnWrapper);
      }

      contentWrapper.appendChild(iconWrapper);
      contentWrapper.appendChild(textWrapper);

      if (this.options.dismissible) {
          const closeBtn = window.domUtils.createElement('button', {
              className: 'flex-shrink-0 ml-4 text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-300 rounded p-1',
              innerHTML: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>',
              onclick: () => this.dismiss()
          });
          contentWrapper.appendChild(closeBtn);
      }

      this.element.appendChild(contentWrapper);

      if (this.options.duration > 0) {
          const progressContainer = window.domUtils.createElement('div', { className: 'h-1 w-full bg-gray-100 absolute bottom-0 left-0' });
          this.progressBar = window.domUtils.createElement('div', {
              className: `h-full ${theme.progress}`,
              style: { width: '100%', transition: 'width 0.1s linear' }
          });
          progressContainer.appendChild(this.progressBar);
          this.element.appendChild(progressContainer);
      }

      this.setupInteractions();
  }

  setupInteractions() {
      if (this.options.duration > 0) {
          this.element.addEventListener('mouseenter', () => this.pauseTimer());
          this.element.addEventListener('mouseleave', () => this.resumeTimer());
      }

      if (this.options.dismissible) {
          this.element.addEventListener('touchstart', (e) => {
              this.swipeState.isSwiping = true;
              this.swipeState.startX = e.touches[0].clientX;
              this.element.style.transition = 'none';
              this.pauseTimer();
          }, { passive: true });

          this.element.addEventListener('touchmove', (e) => {
              if (!this.swipeState.isSwiping) return;
              this.swipeState.currentX = e.touches[0].clientX;
              const diff = this.swipeState.currentX - this.swipeState.startX;
              if (diff > 0) {
                  this.element.style.transform = `translateX(${diff}px)`;
                  this.element.style.opacity = 1 - (diff / this.element.offsetWidth);
              }
          }, { passive: true });

          this.element.addEventListener('touchend', () => {
              if (!this.swipeState.isSwiping) return;
              this.swipeState.isSwiping = false;
              const diff = this.swipeState.currentX - this.swipeState.startX;
              this.element.style.transition = 'all 0.3s ease-out';

              if (diff > 100) {
                  this.dismiss();
              } else {
                  this.element.style.transform = 'translateX(0)';
                  this.element.style.opacity = '1';
                  this.resumeTimer();
              }
          });
      }
  }

  mount() {
      if (this.options.position.startsWith('top')) {
          this.container.insertBefore(this.element, this.container.firstChild);
      } else {
          this.container.appendChild(this.element);
      }

      requestAnimationFrame(() => {
          this.element.classList.remove('translate-x-full', 'opacity-0');
          this.element.classList.add('translate-x-0', 'opacity-100');
          if (this.options.duration > 0) {
              this.startTimer();
          }
      });
  }

  startTimer() {
      this.startTime = Date.now();
      const animate = () => {
          if (this.isDismissed || !this.timerId) return;

          const elapsed = Date.now() - this.startTime;
          this.remaining = this.options.duration - elapsed;

          if (this.remaining <= 0) {
              this.dismiss();
          } else {
              if (this.progressBar) {
                  const percentage = (this.remaining / this.options.duration) * 100;
                  this.progressBar.style.width = `${percentage}%`;
              }
              this.timerId = requestAnimationFrame(animate);
          }
      };
      this.timerId = requestAnimationFrame(animate);
  }

  pauseTimer() {
      if (this.timerId) {
          cancelAnimationFrame(this.timerId);
          this.timerId = null;
      }
  }

  resumeTimer() {
      if (!this.isDismissed && this.options.duration > 0) {
          this.options.duration = this.remaining;
          this.startTimer();
      }
  }

  dismiss() {
      if (this.isDismissed) return;
      this.isDismissed = true;
      this.pauseTimer();

      this.element.style.transition = 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
      this.element.classList.remove('translate-x-0', 'opacity-100');
      this.element.classList.add('translate-x-full', 'opacity-0');

      setTimeout(() => {
          if (this.element && this.element.parentNode) {
              this.element.parentNode.removeChild(this.element);
          }
          if (this.container.children.length === 0) {
              if (this.container.parentNode) {
                  this.container.parentNode.removeChild(this.container);
              }
              this.manager.positions[this.options.position] = null;
          }
      }, 300);
  }
}

window.toastManager = new ToastManager();