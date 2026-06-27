class BadgeTooltip {
  constructor(element, content, options = {}) {
      this.reference = element;
      this.content = content;
      this.options = {
          placement: 'top',
          offset: 8,
          delay: 200,
          theme: 'dark',
          ...options
      };
      this.tooltipEl = null;
      this.arrowEl = null;
      this.showTimeout = null;
      this.hideTimeout = null;
      this.isShown = false;
      this.handleMouseEnter = this.handleMouseEnter.bind(this);
      this.handleMouseLeave = this.handleMouseLeave.bind(this);
      this.handleScroll = this.handleScroll.bind(this);
      this.init();
  }

  init() {
      this.reference.addEventListener('mouseenter', this.handleMouseEnter);
      this.reference.addEventListener('mouseleave', this.handleMouseLeave);
      this.reference.addEventListener('focus', this.handleMouseEnter);
      this.reference.addEventListener('blur', this.handleMouseLeave);
  }

  build() {
      if (this.tooltipEl) return;

      this.tooltipEl = document.createElement('div');
      this.tooltipEl.setAttribute('role', 'tooltip');

      const baseClasses = ['fixed', 'z-[10000]', 'px-3', 'py-2', 'text-xs', 'font-medium', 'rounded-lg', 'shadow-xl', 'pointer-events-none', 'transition-opacity', 'duration-200', 'opacity-0', 'max-w-xs', 'break-words'];

      if (this.options.theme === 'dark') {
          baseClasses.push('bg-gray-900', 'text-white', 'border', 'border-gray-800');
      } else {
          baseClasses.push('bg-white', 'text-gray-900', 'border', 'border-gray-200');
      }

      this.tooltipEl.classList.add(...baseClasses);
      this.tooltipEl.innerHTML = this.content;

      this.arrowEl = document.createElement('div');
      this.arrowEl.className = 'absolute w-2 h-2 transform rotate-45';

      if (this.options.theme === 'dark') {
          this.arrowEl.classList.add('bg-gray-900', 'border-gray-800');
      } else {
          this.arrowEl.classList.add('bg-white', 'border-gray-200');
      }

      this.tooltipEl.appendChild(this.arrowEl);
      document.body.appendChild(this.tooltipEl);
  }

  position() {
      if (!this.tooltipEl || !this.isShown) return;

      const refRect = this.reference.getBoundingClientRect();
      const tooltipRect = this.tooltipEl.getBoundingClientRect();
      const scrollY = window.scrollY || window.pageYOffset;
      const scrollX = window.scrollX || window.pageXOffset;

      let top = 0;
      let left = 0;
      let arrowTop = '';
      let arrowLeft = '';
      let arrowBottom = '';
      let arrowRight = '';
      let arrowBorder = '';

      switch (this.options.placement) {
          case 'top':
              top = refRect.top + scrollY - tooltipRect.height - this.options.offset;
              left = refRect.left + scrollX + (refRect.width / 2) - (tooltipRect.width / 2);
              arrowBottom = '-4px';
              arrowLeft = '50%';
              arrowBorder = 'border-b border-r';
              break;
          case 'bottom':
              top = refRect.bottom + scrollY + this.options.offset;
              left = refRect.left + scrollX + (refRect.width / 2) - (tooltipRect.width / 2);
              arrowTop = '-4px';
              arrowLeft = '50%';
              arrowBorder = 'border-t border-l';
              break;
          case 'left':
              top = refRect.top + scrollY + (refRect.height / 2) - (tooltipRect.height / 2);
              left = refRect.left + scrollX - tooltipRect.width - this.options.offset;
              arrowRight = '-4px';
              arrowTop = '50%';
              arrowBorder = 'border-t border-r';
              break;
          case 'right':
              top = refRect.top + scrollY + (refRect.height / 2) - (tooltipRect.height / 2);
              left = refRect.right + scrollX + this.options.offset;
              arrowLeft = '-4px';
              arrowTop = '50%';
              arrowBorder = 'border-b border-l';
              break;
      }

      const viewportWidth = document.documentElement.clientWidth;
      const viewportHeight = document.documentElement.clientHeight;

      if (left < 8) {
          left = 8;
          arrowLeft = `${refRect.left + (refRect.width / 2) - 8}px`;
      } else if (left + tooltipRect.width > viewportWidth - 8) {
          left = viewportWidth - tooltipRect.width - 8;
          arrowLeft = `${refRect.left - left + (refRect.width / 2)}px`;
      }

      if (top < scrollY + 8 && this.options.placement === 'top') {
          this.options.placement = 'bottom';
          this.position();
          return;
      }

      this.tooltipEl.style.top = `${top}px`;
      this.tooltipEl.style.left = `${left}px`;

      this.arrowEl.className = `absolute w-2 h-2 transform rotate-45 ${this.options.theme === 'dark' ? 'bg-gray-900' : 'bg-white'} ${arrowBorder}`;

      if (arrowTop) this.arrowEl.style.top = arrowTop;
      if (arrowBottom) this.arrowEl.style.bottom = arrowBottom;
      if (arrowLeft) {
          this.arrowEl.style.left = arrowLeft;
          this.arrowEl.style.transform = `translateX(-50%) rotate(45deg)`;
      }
      if (arrowRight) {
          this.arrowEl.style.right = arrowRight;
          this.arrowEl.style.transform = `translateY(-50%) rotate(45deg)`;
      }
  }

  handleMouseEnter() {
      clearTimeout(this.hideTimeout);
      this.showTimeout = setTimeout(() => {
          this.build();
          this.isShown = true;
          this.position();
          requestAnimationFrame(() => {
              if (this.tooltipEl) this.tooltipEl.classList.remove('opacity-0');
          });
          window.addEventListener('scroll', this.handleScroll, True);
          window.addEventListener('resize', this.handleScroll);
      }, this.options.delay);
  }

  handleMouseLeave() {
      clearTimeout(this.showTimeout);
      this.hideTimeout = setTimeout(() => {
          this.isShown = false;
          if (this.tooltipEl) {
              this.tooltipEl.classList.add('opacity-0');
              setTimeout(() => {
                  if (!this.isShown && this.tooltipEl && this.tooltipEl.parentNode) {
                      this.tooltipEl.parentNode.removeChild(this.tooltipEl);
                      this.tooltipEl = null;
                  }
              }, 200);
          }
          window.removeEventListener('scroll', this.handleScroll, true);
          window.removeEventListener('resize', this.handleScroll);
      }, 100);
  }

  handleScroll() {
      if (this.isShown) {
          requestAnimationFrame(() => this.position());
      }
  }

  destroy() {
      this.reference.removeEventListener('mouseenter', this.handleMouseEnter);
      this.reference.removeEventListener('mouseleave', this.handleMouseLeave);
      this.reference.removeEventListener('focus', this.handleMouseEnter);
      this.reference.removeEventListener('blur', this.handleMouseLeave);
      window.removeEventListener('scroll', this.handleScroll, true);
      window.removeEventListener('resize', this.handleScroll);
      if (this.tooltipEl && this.tooltipEl.parentNode) {
          this.tooltipEl.parentNode.removeChild(this.tooltipEl);
      }
  }
}

class StatusBadge extends HTMLElement {
  constructor() {
      super();

      this.icons = {
          check: '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"></path></svg>',
          alert: '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>',
          cross: '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>',
          clock: '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
          shield: '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>',
          info: '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
          sync: '<svg class="w-3.5 h-3.5 animate-spin-slow" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>',
          lock: '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>',
          user: '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>',
          robot: '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>'
      };

      this.statusMap = {
          'CLEARED': { bg: 'bg-emerald-100', text: 'text-emerald-800', border: 'border-emerald-200', icon: 'shield', pulse: false },
          'APPROVED': { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-200', icon: 'check', pulse: false },
          'APPROVED_AUTO': { bg: 'bg-teal-100', text: 'text-teal-800', border: 'border-teal-200', icon: 'robot', pulse: false },
          'EXECUTED': { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-200', icon: 'check', pulse: false },
          'VERIFIED': { bg: 'bg-indigo-100', text: 'text-indigo-800', border: 'border-indigo-200', icon: 'shield', pulse: false },
          'PENDING_COMPLIANCE': { bg: 'bg-yellow-100', text: 'text-yellow-800', border: 'border-yellow-300', icon: 'clock', pulse: true },
          'PENDING_HITL': { bg: 'bg-amber-100', text: 'text-amber-800', border: 'border-amber-300', icon: 'user', pulse: true },
          'HOLD_FOR_REVIEW': { bg: 'bg-orange-100', text: 'text-orange-800', border: 'border-orange-300', icon: 'alert', pulse: true },
          'UNDER_REVIEW': { bg: 'bg-orange-100', text: 'text-orange-800', border: 'border-orange-300', icon: 'sync', pulse: false },
          'MANUAL_REVIEW_REQUIRED': { bg: 'bg-orange-100', text: 'text-orange-800', border: 'border-orange-300', icon: 'alert', pulse: true },
          'ESCALATED': { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-300', icon: 'alert', pulse: true },
          'BLOCKED': { bg: 'bg-rose-100', text: 'text-rose-800', border: 'border-rose-300', icon: 'lock', pulse: false },
          'BLOCKED_SANCTIONS': { bg: 'bg-red-600', text: 'text-white', border: 'border-red-700', icon: 'lock', pulse: true },
          'BLOCKED_STRUCTURING': { bg: 'bg-red-600', text: 'text-white', border: 'border-red-700', icon: 'lock', pulse: true },
          'BLOCKED_FRAUD': { bg: 'bg-red-600', text: 'text-white', border: 'border-red-700', icon: 'lock', pulse: true },
          'REJECTED': { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-200', icon: 'cross', pulse: false },
          'REJECTED_AUTO': { bg: 'bg-rose-100', text: 'text-rose-800', border: 'border-rose-200', icon: 'robot', pulse: false },
          'FRAUD_SUSPECTED': { bg: 'bg-red-600', text: 'text-white', border: 'border-red-700', icon: 'alert', pulse: true },
          'FAILED': { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', icon: 'cross', pulse: false },
          'REVERSED': { bg: 'bg-gray-200', text: 'text-gray-700', border: 'border-gray-300', icon: 'sync', pulse: false },
          'EXPIRED': { bg: 'bg-gray-100', text: 'text-gray-600', border: 'border-gray-200', icon: 'clock', pulse: false },
          'SYSTEM_ERROR': { bg: 'bg-gray-800', text: 'text-white', border: 'border-gray-900', icon: 'alert', pulse: true },
          'INITIATED': { bg: 'bg-sky-100', text: 'text-sky-800', border: 'border-sky-200', icon: 'sync', pulse: false },
          'PROCESSING': { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-200', icon: 'sync', pulse: true },
          'ACTIVE': { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-200', icon: 'check', pulse: false },
          'REVOKED': { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-200', icon: 'cross', pulse: false },
          'SYSTEM_ADMIN': { bg: 'bg-purple-100', text: 'text-purple-800', border: 'border-purple-200', icon: 'shield', pulse: false },
          'COMPLIANCE_OFFICER': { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-200', icon: 'shield', pulse: false },
          'RISK_ANALYST': { bg: 'bg-cyan-100', text: 'text-cyan-800', border: 'border-cyan-200', icon: 'user', pulse: false },
          'AUDITOR': { bg: 'bg-gray-100', text: 'text-gray-800', border: 'border-gray-300', icon: 'user', pulse: false },
          'READ_ONLY': { bg: 'bg-gray-50', text: 'text-gray-500', border: 'border-gray-200', icon: 'user', pulse: false },
          'LOW_RISK': { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-200', icon: 'check', pulse: false },
          'MEDIUM_RISK': { bg: 'bg-yellow-100', text: 'text-yellow-800', border: 'border-yellow-300', icon: 'alert', pulse: false },
          'HIGH_RISK': { bg: 'bg-orange-100', text: 'text-orange-800', border: 'border-orange-300', icon: 'alert', pulse: true },
          'UNACCEPTABLE_RISK': { bg: 'bg-red-600', text: 'text-white', border: 'border-red-700', icon: 'alert', pulse: true },
          'OPERATIONAL': { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-200', icon: 'check', pulse: false },
          'DEGRADED': { bg: 'bg-orange-100', text: 'text-orange-800', border: 'border-orange-300', icon: 'alert', pulse: true },
          'OUTAGE': { bg: 'bg-red-600', text: 'text-white', border: 'border-red-700', icon: 'cross', pulse: true }
      };

      this.tooltipInstance = null;
  }

  static get observedAttributes() {
      return ['status', 'label', 'size', 'tooltip', 'hide-icon', 'dot-only', 'pulse-override'];
  }

  attributeChangedCallback(name, oldValue, newValue) {
      if (oldValue !== newValue) {
          this.render();
      }
  }

  connectedCallback() {
      this.render();
  }

  disconnectedCallback() {
      if (this.tooltipInstance) {
          this.tooltipInstance.destroy();
          this.tooltipInstance = null;
      }
  }

  render() {
      const rawStatus = this.getAttribute('status') || 'UNKNOWN';
      const normalizedStatus = rawStatus.toUpperCase().replace(/\s+/g, '_');
      const customLabel = this.getAttribute('label');
      const size = this.getAttribute('size') || 'md';
      const tooltipText = this.getAttribute('tooltip');
      const hideIcon = this.hasAttribute('hide-icon');
      const dotOnly = this.hasAttribute('dot-only');
      const pulseOverride = this.getAttribute('pulse-override');

      const config = this.statusMap[normalizedStatus] || {
          bg: 'bg-gray-100', text: 'text-gray-700', border: 'border-gray-200', icon: 'info', pulse: false
      };

      const displayLabel = customLabel || rawStatus.replace(/_/g, ' ');
      const shouldPulse = pulseOverride === 'true' ? true : (pulseOverride === 'false' ? false : config.pulse);

      let sizeClasses = '';
      let dotSize = '';
      let iconSize = '';

      switch (size) {
          case 'sm':
              sizeClasses = 'px-1.5 py-0.5 text-[10px] gap-1';
              dotSize = 'w-1.5 h-1.5';
              iconSize = 'w-3 h-3';
              break;
          case 'lg':
              sizeClasses = 'px-3 py-1 text-xs gap-2';
              dotSize = 'w-2.5 h-2.5';
              iconSize = 'w-4 h-4';
              break;
          case 'xl':
              sizeClasses = 'px-4 py-1.5 text-sm gap-2';
              dotSize = 'w-3 h-3';
              iconSize = 'w-5 h-5';
              break;
          case 'md':
          default:
              sizeClasses = 'px-2.5 py-0.5 text-[11px] gap-1.5';
              dotSize = 'w-2 h-2';
              iconSize = 'w-3.5 h-3.5';
              break;
      }

      const wrapper = document.createElement('div');
      wrapper.className = `inline-flex items-center justify-center font-bold uppercase tracking-wider rounded-full border shadow-sm transition-all ${config.bg} ${config.text} ${config.border} ${sizeClasses}`;

      if (shouldPulse) {
          wrapper.classList.add('relative');
      }

      const innerContainer = document.createElement('div');
      innerContainer.className = 'flex items-center gap-inherit z-10 relative';

      if (dotOnly) {
          const dotWrapper = document.createElement('div');
          dotWrapper.className = 'relative flex items-center justify-center';

          const dot = document.createElement('div');
          let dotColorClass = config.text.replace('text-', 'bg-');
          if (config.bg.includes('600') || config.bg.includes('800') || config.bg.includes('900')) {
              dotColorClass = 'bg-white';
          }
          dot.className = `rounded-full ${dotColorClass} ${dotSize}`;

          if (shouldPulse) {
              const ping = document.createElement('div');
              ping.className = `absolute rounded-full ${dotColorClass} ${dotSize} animate-ping opacity-75`;
              dotWrapper.appendChild(ping);
          }

          dotWrapper.appendChild(dot);
          innerContainer.appendChild(dotWrapper);
      } else if (!hideIcon && config.icon && this.icons[config.icon]) {
          const iconWrapper = document.createElement('div');
          iconWrapper.className = `flex-shrink-0 flex items-center justify-center ${iconSize}`;
          let iconSvg = this.icons[config.icon];
          iconSvg = iconSvg.replace('w-3.5 h-3.5', iconSize);
          iconWrapper.innerHTML = iconSvg;
          innerContainer.appendChild(iconWrapper);
      }

      if (!dotOnly) {
          const textSpan = document.createElement('span');
          textSpan.textContent = displayLabel;
          textSpan.className = 'whitespace-nowrap truncate max-w-[200px]';
          innerContainer.appendChild(textSpan);
      }

      wrapper.appendChild(innerContainer);

      if (shouldPulse && !dotOnly) {
          const pulseRing = document.createElement('div');
          let pulseColorClass = config.border.replace('border-', 'bg-');
          pulseRing.className = `absolute inset-0 rounded-full ${pulseColorClass} opacity-20 animate-ping`;
          pulseRing.style.animationDuration = '2s';
          wrapper.appendChild(pulseRing);
      }

      this.innerHTML = '';
      this.appendChild(wrapper);

      if (tooltipText) {
          if (this.tooltipInstance) {
              this.tooltipInstance.destroy();
          }
          this.tooltipInstance = new BadgeTooltip(wrapper, tooltipText);
      }
  }
}

customElements.define('status-badge', StatusBadge);