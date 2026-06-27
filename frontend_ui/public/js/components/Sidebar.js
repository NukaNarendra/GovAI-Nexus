class Sidebar {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        if (!this.container) throw new Error('Sidebar container not found');

        this.state = {
            isMobileOpen: false,
            isCollapsed: localStorage.getItem('eg_sidebar_collapsed') === 'true',
            activePath: window.location.pathname,
            expandedGroups: new Set(JSON.parse(localStorage.getItem('eg_sidebar_expanded') || '[]'))
        };

        this.elements = {
            wrapper: null,
            overlay: null,
            logo: null,
            nav: null,
            toggleBtn: null,
            mobileCloseBtn: null
        };

        this.navConfig = [
            {
                id: 'nav-dashboard',
                label: 'Dashboard',
                path: '/dashboard.html',
                icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path></svg>',
                permissions: ['VIEW_HITL', 'VIEW_AUDIT']
            },
            {
                id: 'nav-hitl',
                label: 'HITL Review Queue',
                path: '/hitl-review.html',
                icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path></svg>',
                permissions: ['VIEW_HITL']
            },
            {
                id: 'nav-compliance',
                label: 'Compliance Engine',
                icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>',
                permissions: ['VIEW_HITL', 'APPROVE_HITL'],
                children: [
                    {
                        id: 'nav-kyc-profiles',
                        label: 'KYC Profiles',
                        path: '/compliance/kyc-profiles.html',
                        permissions: ['VIEW_HITL']
                    },
                    {
                        id: 'nav-aml-watchlists',
                        label: 'AML Watchlists',
                        path: '/compliance/aml-watchlists.html',
                        permissions: ['VIEW_HITL']
                    },
                    {
                        id: 'nav-risk-thresholds',
                        label: 'Risk Thresholds',
                        path: '/compliance/risk-thresholds.html',
                        permissions: ['SYSTEM_ADMIN']
                    }
                ]
            },
            {
                id: 'nav-audit',
                label: 'WORM Audit Logs',
                path: '/audit-logs.html',
                icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>',
                permissions: ['VIEW_AUDIT']
            },
            {
                id: 'nav-telemetry',
                label: 'System Telemetry',
                icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 13v-1m4 1v-3m4 3V8M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"></path></svg>',
                permissions: ['SYSTEM_ADMIN', 'AUDITOR'],
                children: [
                    {
                        id: 'nav-health',
                        label: 'Infrastructure Health',
                        path: '/telemetry/health.html',
                        permissions: ['SYSTEM_ADMIN']
                    },
                    {
                        id: 'nav-ai-metrics',
                        label: 'AI Execution Metrics',
                        path: '/telemetry/ai-metrics.html',
                        permissions: ['SYSTEM_ADMIN', 'AUDITOR']
                    }
                ]
            },
            {
                id: 'nav-settings',
                label: 'Configuration',
                icon: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>',
                permissions: ['SYSTEM_ADMIN'],
                children: [
                    {
                        id: 'nav-users',
                        label: 'User Management',
                        path: '/settings/users.html',
                        permissions: ['MANAGE_USERS']
                    },
                    {
                        id: 'nav-api-keys',
                        label: 'API Keys',
                        path: '/settings/api-keys.html',
                        permissions: ['SYSTEM_ADMIN']
                    }
                ]
            }
        ];

        this.init();
    }

    init() {
        this.buildDOM();
        this.render();
        this.attachListeners();
        this.checkInitialActiveState();
    }

    buildDOM() {
        this.container.innerHTML = '';

        this.elements.overlay = window.domUtils.createElement('div', {
            className: 'fixed inset-0 bg-gray-900 bg-opacity-50 z-20 hidden lg:hidden transition-opacity duration-300 opacity-0'
        });

        this.elements.wrapper = window.domUtils.createElement('aside', {
            className: `fixed top-0 left-0 z-30 h-screen transition-all duration-300 ease-in-out bg-gray-900 flex flex-col shadow-xl
                        ${this.state.isCollapsed ? 'w-20' : 'w-64'} 
                        -translate-x-full lg:translate-x-0`
        });

        const logoContainer = window.domUtils.createElement('div', {
            className: 'h-16 flex items-center justify-between px-4 border-b border-gray-800'
        });

        this.elements.logo = window.domUtils.createElement('a', {
            href: '/dashboard.html',
            className: 'flex items-center gap-3 overflow-hidden text-white no-underline focus:outline-none'
        });

        const logoIcon = window.domUtils.createElement('div', {
            className: 'flex-shrink-0 w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center shadow-lg',
            innerHTML: '<svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>'
        });

        const logoText = window.domUtils.createElement('span', {
            className: `font-bold text-lg tracking-tight whitespace-nowrap transition-opacity duration-300 ${this.state.isCollapsed ? 'opacity-0 w-0' : 'opacity-100 w-auto'}`,
            textContent: 'Nexus OS'
        });

        this.elements.logo.appendChild(logoIcon);
        this.elements.logo.appendChild(logoText);
        logoContainer.appendChild(this.elements.logo);

        this.elements.mobileCloseBtn = window.domUtils.createElement('button', {
            className: 'lg:hidden text-gray-400 hover:text-white focus:outline-none p-1',
            innerHTML: '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>'
        });
        logoContainer.appendChild(this.elements.mobileCloseBtn);

        this.elements.wrapper.appendChild(logoContainer);

        this.elements.nav = window.domUtils.createElement('nav', {
            className: 'flex-1 overflow-y-auto py-4 px-3 space-y-1 custom-scrollbar'
        });
        this.elements.wrapper.appendChild(this.elements.nav);

        const footerContainer = window.domUtils.createElement('div', {
            className: 'p-4 border-t border-gray-800 flex justify-center'
        });

        this.elements.toggleBtn = window.domUtils.createElement('button', {
            className: 'hidden lg:flex items-center justify-center w-8 h-8 rounded-lg bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700 focus:outline-none transition-colors',
            innerHTML: this.state.isCollapsed 
                ? '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 5l7 7-7 7M5 5l7 7-7 7"></path></svg>'
                : '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7"></path></svg>'
        });

        footerContainer.appendChild(this.elements.toggleBtn);
        this.elements.wrapper.appendChild(footerContainer);

        this.container.appendChild(this.elements.overlay);
        this.container.appendChild(this.elements.wrapper);
    }

    render() {
        window.domUtils.clearChildren(this.elements.nav);

        this.navConfig.forEach(item => {
            if (this.hasPermission(item.permissions)) {
                const el = this.buildNavItem(item, 0);
                this.elements.nav.appendChild(el);
            }
        });
    }

    buildNavItem(item, depth = 0) {
        const hasChildren = item.children && item.children.length > 0;
        const isExpanded = this.state.expandedGroups.has(item.id);
        const isActive = this.isItemActive(item);

        const wrapper = window.domUtils.createElement('div', { className: 'mb-1' });

        const linkClasses = `flex items-center justify-between w-full rounded-lg transition-colors group cursor-pointer
            ${depth === 0 ? 'px-3 py-2.5' : 'py-2 pl-11 pr-3'}
            ${isActive && !hasChildren ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-800 hover:text-white'}
            ${isActive && hasChildren && !this.state.isCollapsed ? 'bg-gray-800 text-white' : ''}`;

        const linkProps = { className: linkClasses };
        if (!hasChildren && item.path) {
            linkProps.href = item.path;
            linkProps.className = linkProps.className.replace('cursor-pointer', '');
        }

        const linkEl = window.domUtils.createElement(hasChildren ? 'button' : 'a', linkProps);

        const leftContent = window.domUtils.createElement('div', { className: 'flex items-center gap-3 overflow-hidden' });

        if (depth === 0 && item.icon) {
            const iconWrapper = window.domUtils.createElement('div', {
                className: `flex-shrink-0 ${isActive && !hasChildren ? 'text-white' : 'text-gray-400 group-hover:text-white transition-colors'}`,
                innerHTML: item.icon
            });
            leftContent.appendChild(iconWrapper);
        }

        const labelClasses = `text-sm font-medium whitespace-nowrap transition-all duration-300 
            ${this.state.isCollapsed && depth === 0 ? 'opacity-0 w-0 hidden' : 'opacity-100 w-auto block'}`;

        const labelEl = window.domUtils.createElement('span', {
            className: labelClasses,
            textContent: item.label
        });
        leftContent.appendChild(labelEl);
        linkEl.appendChild(leftContent);

        if (hasChildren) {
            const chevron = window.domUtils.createElement('div', {
                className: `flex-shrink-0 transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''} ${this.state.isCollapsed ? 'hidden' : 'block'}`,
                innerHTML: '<svg class="w-4 h-4 text-gray-400 group-hover:text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>'
            });
            linkEl.appendChild(chevron);

            linkEl.addEventListener('click', (e) => {
                e.preventDefault();
                if (this.state.isCollapsed) {
                    this.toggleSidebar();
                    setTimeout(() => this.toggleGroup(item.id, chevron), 300);
                } else {
                    this.toggleGroup(item.id, chevron);
                }
            });

            wrapper.appendChild(linkEl);

            const childrenWrapper = window.domUtils.createElement('div', {
                id: `submenu-${item.id}`,
                className: `overflow-hidden transition-all duration-300 ease-in-out ${this.state.isCollapsed ? 'hidden' : 'block'}`,
                style: { maxHeight: isExpanded && !this.state.isCollapsed ? '1000px' : '0px', opacity: isExpanded && !this.state.isCollapsed ? '1' : '0' }
            });

            const childrenList = window.domUtils.createElement('div', { className: 'pt-1 pb-2 space-y-1' });

            item.children.forEach(child => {
                if (this.hasPermission(child.permissions)) {
                    childrenList.appendChild(this.buildNavItem(child, depth + 1));
                }
            });

            childrenWrapper.appendChild(childrenList);
            wrapper.appendChild(childrenWrapper);
        } else {
            wrapper.appendChild(linkEl);
        }

        if (this.state.isCollapsed && depth === 0) {
            const tooltip = window.domUtils.createElement('div', {
                className: 'absolute left-20 bg-gray-800 text-white text-xs px-2 py-1 rounded shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all whitespace-nowrap z-50 pointer-events-none',
                textContent: item.label,
                style: { top: '50%', transform: 'translateY(-50%)' }
            });
            linkEl.style.position = 'relative';
            linkEl.appendChild(tooltip);
        }

        return wrapper;
    }

    attachListeners() {
        if (this.elements.toggleBtn) {
            this.elements.toggleBtn.addEventListener('click', () => this.toggleSidebar());
        }

        if (this.elements.mobileCloseBtn) {
            this.elements.mobileCloseBtn.addEventListener('click', () => this.closeMobile());
        }

        if (this.elements.overlay) {
            this.elements.overlay.addEventListener('click', () => this.closeMobile());
        }

        document.addEventListener('openMobileSidebar', () => {
            this.openMobile();
        });

        window.addEventListener('resize', window.domUtils.debounce(() => {
            if (window.innerWidth >= 1024 && this.state.isMobileOpen) {
                this.closeMobile();
            }
        }, 150));
    }

    toggleSidebar() {
        this.state.isCollapsed = !this.state.isCollapsed;
        localStorage.setItem('eg_sidebar_collapsed', this.state.isCollapsed);

        if (this.state.isCollapsed) {
            this.elements.wrapper.classList.remove('w-64');
            this.elements.wrapper.classList.add('w-20');
            this.elements.toggleBtn.innerHTML = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 5l7 7-7 7M5 5l7 7-7 7"></path></svg>';
        } else {
            this.elements.wrapper.classList.remove('w-20');
            this.elements.wrapper.classList.add('w-64');
            this.elements.toggleBtn.innerHTML = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7"></path></svg>';
        }

        document.dispatchEvent(new CustomEvent('sidebarToggled', { detail: { isCollapsed: this.state.isCollapsed } }));

        setTimeout(() => this.render(), 150);
    }

    openMobile() {
        this.state.isMobileOpen = true;
        this.elements.overlay.classList.remove('hidden');
        requestAnimationFrame(() => {
            this.elements.overlay.classList.add('opacity-100');
            this.elements.overlay.classList.remove('opacity-0');
            this.elements.wrapper.classList.remove('-translate-x-full');
            this.elements.wrapper.classList.add('translate-x-0');
        });
        document.body.style.overflow = 'hidden';
    }

    closeMobile() {
        this.state.isMobileOpen = false;
        this.elements.overlay.classList.remove('opacity-100');
        this.elements.overlay.classList.add('opacity-0');
        this.elements.wrapper.classList.remove('translate-x-0');
        this.elements.wrapper.classList.add('-translate-x-full');

        setTimeout(() => {
            if (!this.state.isMobileOpen) {
                this.elements.overlay.classList.add('hidden');
            }
        }, 300);
        document.body.style.overflow = '';
    }

    toggleGroup(groupId, chevronEl) {
        const submenu = this.elements.nav.querySelector(`#submenu-${groupId}`);
        if (!submenu) return;

        const isExpanded = this.state.expandedGroups.has(groupId);

        if (isExpanded) {
            this.state.expandedGroups.delete(groupId);
            submenu.style.maxHeight = '0px';
            submenu.style.opacity = '0';
            if (chevronEl) chevronEl.classList.remove('rotate-90');
        } else {
            this.state.expandedGroups.add(groupId);
            submenu.style.maxHeight = submenu.scrollHeight + 'px';
            submenu.style.opacity = '1';
            if (chevronEl) chevronEl.classList.add('rotate-90');

            setTimeout(() => {
                if (this.state.expandedGroups.has(groupId)) {
                    submenu.style.maxHeight = '1000px';
                }
            }, 300);
        }

        localStorage.setItem('eg_sidebar_expanded', JSON.stringify(Array.from(this.state.expandedGroups)));
    }

    isItemActive(item) {
        if (item.path && this.state.activePath.includes(item.path)) {
            return true;
        }
        if (item.children) {
            return item.children.some(child => this.isItemActive(child));
        }
        return false;
    }

    checkInitialActiveState() {
        this.navConfig.forEach(item => {
            if (item.children && this.isItemActive(item) && !this.state.isCollapsed) {
                this.state.expandedGroups.add(item.id);
                localStorage.setItem('eg_sidebar_expanded', JSON.stringify(Array.from(this.state.expandedGroups)));
            }
        });
        this.render();
    }

    hasPermission(permissions) {
        if (!permissions || permissions.length === 0) return true;
        if (!window.authStore) return false;

        return permissions.some(p => window.authStore.hasPermission(p));
    }
}