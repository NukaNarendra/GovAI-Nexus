class Header {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        if (!this.container) throw new Error('Header container not found');

        this.state = {
            searchOpen: false,
            searchQuery: '',
            notificationsOpen: false,
            profileOpen: false,
            notifications: [],
            unreadCount: 0,
            isDarkMode: localStorage.getItem('eg_theme') === 'dark'
        };

        this.elements = {
            wrapper: null,
            mobileMenuBtn: null,
            breadcrumb: null,
            searchBtn: null,
            searchModal: null,
            searchInput: null,
            searchResults: null,
            notificationBtn: null,
            notificationDropdown: null,
            profileBtn: null,
            profileDropdown: null,
            themeToggle: null
        };

        this.init();
    }

    init() {
        this.applyTheme();
        this.buildDOM();
        this.attachListeners();
        this.generateBreadcrumbs();
        this.startNotificationPolling();
    }

    buildDOM() {
        this.container.innerHTML = '';

        this.elements.wrapper = window.domUtils.createElement('header', {
            className: 'h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4 lg:px-8 w-full transition-colors duration-200 shadow-sm z-10 sticky top-0'
        });

        const leftSection = window.domUtils.createElement('div', { className: 'flex items-center gap-4' });

        this.elements.mobileMenuBtn = window.domUtils.createElement('button', {
            className: 'lg:hidden p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-md focus:outline-none transition-colors',
            innerHTML: '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>'
        });
        leftSection.appendChild(this.elements.mobileMenuBtn);

        this.elements.breadcrumb = window.domUtils.createElement('nav', {
            className: 'hidden sm:flex text-sm font-medium text-gray-500',
            aria: { label: 'Breadcrumb' }
        });
        leftSection.appendChild(this.elements.breadcrumb);

        const rightSection = window.domUtils.createElement('div', { className: 'flex items-center gap-2 sm:gap-4' });

        this.elements.searchBtn = window.domUtils.createElement('button', {
            className: 'p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full focus:outline-none transition-colors flex items-center gap-2 group',
            title: 'Search (Ctrl+K)'
        });
        this.elements.searchBtn.innerHTML = `
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
            <span class="hidden md:block text-xs border border-gray-200 rounded px-1.5 py-0.5 group-hover:border-gray-300">⌘K</span>
        `;
        rightSection.appendChild(this.elements.searchBtn);

        this.elements.themeToggle = window.domUtils.createElement('button', {
            className: 'p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full focus:outline-none transition-colors',
            title: 'Toggle Theme'
        });
        this.updateThemeIcon();
        rightSection.appendChild(this.elements.themeToggle);

        const notificationWrapper = window.domUtils.createElement('div', { className: 'relative' });
        this.elements.notificationBtn = window.domUtils.createElement('button', {
            className: 'relative p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full focus:outline-none transition-colors'
        });
        this.elements.notificationBtn.innerHTML = `
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path></svg>
            <span class="absolute top-1 right-1 flex items-center justify-center w-4 h-4 text-[10px] font-bold text-white bg-red-500 rounded-full border-2 border-white hidden" id="notif-badge">0</span>
        `;

        this.elements.notificationDropdown = window.domUtils.createElement('div', {
            className: 'absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-xl border border-gray-100 overflow-hidden transform origin-top-right transition-all duration-200 scale-95 opacity-0 invisible z-50'
        });
        notificationWrapper.appendChild(this.elements.notificationBtn);
        notificationWrapper.appendChild(this.elements.notificationDropdown);
        rightSection.appendChild(notificationWrapper);

        const profileWrapper = window.domUtils.createElement('div', { className: 'relative ml-2' });
        this.elements.profileBtn = window.domUtils.createElement('button', {
            className: 'flex items-center gap-2 focus:outline-none rounded-full ring-2 ring-transparent focus:ring-blue-500 transition-all'
        });

        const avatar = window.domUtils.createElement('div', {
            className: 'w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold text-sm shadow-sm',
            textContent: this.getInitials()
        });

        this.elements.profileBtn.appendChild(avatar);

        this.elements.profileDropdown = window.domUtils.createElement('div', {
            className: 'absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-xl border border-gray-100 overflow-hidden transform origin-top-right transition-all duration-200 scale-95 opacity-0 invisible z-50'
        });
        this.buildProfileDropdown();

        profileWrapper.appendChild(this.elements.profileBtn);
        profileWrapper.appendChild(this.elements.profileDropdown);
        rightSection.appendChild(profileWrapper);

        this.elements.wrapper.appendChild(leftSection);
        this.elements.wrapper.appendChild(rightSection);
        this.container.appendChild(this.elements.wrapper);

        this.buildSearchModal();
    }

    buildProfileDropdown() {
        const user = window.authStore ? window.authStore.getUserContext() : { email: 'unknown', role: 'UNKNOWN' };

        const header = window.domUtils.createElement('div', { className: 'px-4 py-3 border-b border-gray-100 bg-gray-50' });
        header.appendChild(window.domUtils.createElement('p', { className: 'text-sm font-medium text-gray-900 truncate', textContent: user.email }));
        header.appendChild(window.domUtils.createElement('p', { className: 'text-xs text-gray-500 truncate mt-0.5', textContent: user.role.replace(/_/g, ' ') }));

        const body = window.domUtils.createElement('div', { className: 'py-1' });

        const settingsLink = window.domUtils.createElement('a', {
            href: '/settings/profile.html',
            className: 'block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 hover:text-blue-600 transition-colors flex items-center gap-2',
            innerHTML: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg> My Profile'
        });

        const logoutBtn = window.domUtils.createElement('button', {
            className: 'w-full text-left block px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors flex items-center gap-2 border-t border-gray-100 mt-1',
            innerHTML: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg> Sign Out',
            onclick: () => {
                if (window.authApi) window.authApi.logout();
                else if (window.authStore) window.authStore.logout();
            }
        });

        body.appendChild(settingsLink);
        body.appendChild(logoutBtn);

        this.elements.profileDropdown.appendChild(header);
        this.elements.profileDropdown.appendChild(body);
    }

    buildSearchModal() {
        this.elements.searchModal = window.domUtils.createElement('div', {
            className: 'fixed inset-0 bg-gray-900 bg-opacity-50 backdrop-blur-sm z-[100] hidden items-start justify-center pt-16 sm:pt-24 px-4 transition-opacity duration-200 opacity-0'
        });

        const container = window.domUtils.createElement('div', {
            className: 'bg-white rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden transform transition-all duration-200 scale-95 opacity-0',
            id: 'search-container'
        });

        const inputWrapper = window.domUtils.createElement('div', { className: 'relative border-b border-gray-200' });
        const searchIcon = window.domUtils.createElement('div', {
            className: 'absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-gray-400',
            innerHTML: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>'
        });

        this.elements.searchInput = window.domUtils.createElement('input', {
            type: 'text',
            className: 'w-full pl-12 pr-4 py-4 text-gray-900 placeholder-gray-400 bg-transparent focus:outline-none sm:text-lg',
            placeholder: 'Search transactions, entities, or tasks...',
            autocomplete: 'off'
        });

        const escHint = window.domUtils.createElement('div', {
            className: 'absolute inset-y-0 right-0 pr-4 flex items-center pointer-events-none',
            innerHTML: '<span class="text-xs text-gray-400 border border-gray-200 rounded px-1.5 py-0.5">ESC</span>'
        });

        inputWrapper.appendChild(searchIcon);
        inputWrapper.appendChild(this.elements.searchInput);
        inputWrapper.appendChild(escHint);

        this.elements.searchResults = window.domUtils.createElement('div', {
            className: 'max-h-96 overflow-y-auto p-2 bg-gray-50 custom-scrollbar hidden'
        });

        container.appendChild(inputWrapper);
        container.appendChild(this.elements.searchResults);
        this.elements.searchModal.appendChild(container);
        document.body.appendChild(this.elements.searchModal);
    }

    attachListeners() {
        if (this.elements.mobileMenuBtn) {
            this.elements.mobileMenuBtn.addEventListener('click', () => {
                document.dispatchEvent(new CustomEvent('openMobileSidebar'));
            });
        }

        const toggleDropdown = (trigger, dropdown, stateKey) => {
            trigger.addEventListener('click', (e) => {
                e.stopPropagation();
                this.closeAllDropdowns();
                this.state[stateKey] = !this.state[stateKey];

                if (this.state[stateKey]) {
                    dropdown.classList.remove('invisible', 'scale-95', 'opacity-0');
                    dropdown.classList.add('scale-100', 'opacity-100');
                } else {
                    dropdown.classList.remove('scale-100', 'opacity-100');
                    dropdown.classList.add('invisible', 'scale-95', 'opacity-0');
                }
            });
        };

        toggleDropdown(this.elements.notificationBtn, this.elements.notificationDropdown, 'notificationsOpen');
        toggleDropdown(this.elements.profileBtn, this.elements.profileDropdown, 'profileOpen');

        document.addEventListener('click', (e) => {
            if (this.state.notificationsOpen && !this.elements.notificationDropdown.contains(e.target) && e.target !== this.elements.notificationBtn) {
                this.closeAllDropdowns();
            }
            if (this.state.profileOpen && !this.elements.profileDropdown.contains(e.target) && e.target !== this.elements.profileBtn) {
                this.closeAllDropdowns();
            }
        });

        if (this.elements.searchBtn) {
            this.elements.searchBtn.addEventListener('click', () => this.openSearch());
        }

        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                this.openSearch();
            }
            if (e.key === 'Escape' && this.state.searchOpen) {
                this.closeSearch();
            }
        });

        this.elements.searchModal.addEventListener('click', (e) => {
            if (e.target === this.elements.searchModal) {
                this.closeSearch();
            }
        });

        this.elements.searchInput.addEventListener('input', window.domUtils.debounce((e) => {
            this.handleSearchInput(e.target.value);
        }, 300));

        if (this.elements.themeToggle) {
            this.elements.themeToggle.addEventListener('click', () => {
                this.state.isDarkMode = !this.state.isDarkMode;
                localStorage.setItem('eg_theme', this.state.isDarkMode ? 'dark' : 'light');
                this.applyTheme();
                this.updateThemeIcon();
            });
        }
    }

    closeAllDropdowns() {
        this.state.notificationsOpen = false;
        this.state.profileOpen = false;
        this.elements.notificationDropdown.classList.remove('scale-100', 'opacity-100');
        this.elements.notificationDropdown.classList.add('invisible', 'scale-95', 'opacity-0');
        this.elements.profileDropdown.classList.remove('scale-100', 'opacity-100');
        this.elements.profileDropdown.classList.add('invisible', 'scale-95', 'opacity-0');
    }

    openSearch() {
        this.state.searchOpen = true;
        this.elements.searchModal.classList.remove('hidden');
        this.elements.searchModal.style.display = 'flex';

        requestAnimationFrame(() => {
            this.elements.searchModal.classList.remove('opacity-0');
            this.elements.searchModal.classList.add('opacity-100');
            const container = this.elements.searchModal.querySelector('#search-container');
            container.classList.remove('scale-95', 'opacity-0');
            container.classList.add('scale-100', 'opacity-100');
            this.elements.searchInput.focus();
        });
        document.body.style.overflow = 'hidden';
    }

    closeSearch() {
        this.state.searchOpen = false;
        this.elements.searchModal.classList.remove('opacity-100');
        this.elements.searchModal.classList.add('opacity-0');
        const container = this.elements.searchModal.querySelector('#search-container');
        container.classList.remove('scale-100', 'opacity-100');
        container.classList.add('scale-95', 'opacity-0');

        setTimeout(() => {
            this.elements.searchModal.classList.add('hidden');
            this.elements.searchModal.style.display = 'none';
            this.elements.searchInput.value = '';
            this.elements.searchResults.innerHTML = '';
            this.elements.searchResults.classList.add('hidden');
        }, 200);
        document.body.style.overflow = '';
    }

    async handleSearchInput(query) {
        if (!query.trim() || query.length < 2) {
            this.elements.searchResults.innerHTML = '';
            this.elements.searchResults.classList.add('hidden');
            return;
        }

        this.elements.searchResults.classList.remove('hidden');
        this.elements.searchResults.innerHTML = `
            <div class="flex justify-center py-8">
                <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
            </div>
        `;

        try {
            await new Promise(r => setTimeout(r, 400));
            const results = this.mockSearchEngine(query);
            this.renderSearchResults(results);
        } catch (e) {
            this.elements.searchResults.innerHTML = `<div class="p-4 text-sm text-red-500 text-center">Search failed</div>`;
        }
    }

    mockSearchEngine(query) {
        const q = query.toLowerCase();
        const results = [];
        if ('nexus global'.includes(q) || q.includes('ent')) {
            results.push({ type: 'Entity', title: 'Nexus Global Trading', subtitle: 'ID: ENT_001 • KYC: PENDING_HITL', icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4', path: '/hitl-review.html?q=ENT_001' });
        }
        if (q.includes('tx') || 'wire transfer'.includes(q)) {
            results.push({ type: 'Transaction', title: 'High Value Wire Transfer', subtitle: 'ID: TXN_982374 • Amount: $250,000.00', icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z', path: '/audit-logs.html?q=TXN_982374' });
        }
        if (results.length === 0) {
            return [];
        }
        return results;
    }

    renderSearchResults(results) {
        window.domUtils.clearChildren(this.elements.searchResults);

        if (results.length === 0) {
            this.elements.searchResults.innerHTML = `
                <div class="px-4 py-8 text-center text-sm text-gray-500">
                    No results found for "${window.domUtils.sanitizeHTML(this.elements.searchInput.value)}"
                </div>
            `;
            return;
        }

        const list = window.domUtils.createElement('ul', { className: 'space-y-1' });
        results.forEach(res => {
            const item = window.domUtils.createElement('li');
            const link = window.domUtils.createElement('a', {
                href: res.path,
                className: 'flex items-start p-3 rounded-lg hover:bg-white hover:shadow-sm transition-all group',
                onclick: () => this.closeSearch()
            });

            const iconWrapper = window.domUtils.createElement('div', {
                className: 'flex-shrink-0 w-8 h-8 rounded bg-gray-100 flex items-center justify-center text-gray-500 group-hover:text-blue-600 group-hover:bg-blue-50 transition-colors',
                innerHTML: `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${res.icon}"></path></svg>`
            });

            const content = window.domUtils.createElement('div', { className: 'ml-3' });
            content.appendChild(window.domUtils.createElement('p', { className: 'text-sm font-medium text-gray-900', textContent: res.title }));
            content.appendChild(window.domUtils.createElement('p', { className: 'text-xs text-gray-500', textContent: res.subtitle }));

            const typeBadge = window.domUtils.createElement('span', { className: 'ml-auto text-[10px] font-medium px-2 py-0.5 rounded bg-gray-200 text-gray-600', textContent: res.type });

            link.appendChild(iconWrapper);
            link.appendChild(content);
            link.appendChild(typeBadge);
            item.appendChild(link);
            list.appendChild(item);
        });

        this.elements.searchResults.appendChild(list);
    }

    generateBreadcrumbs() {
        window.domUtils.clearChildren(this.elements.breadcrumb);

        const path = window.location.pathname;
        const parts = path.split('/').filter(p => p && p !== 'index.html');

        const list = window.domUtils.createElement('ol', { className: 'flex items-center space-x-2' });

        const homeLi = window.domUtils.createElement('li', { className: 'flex items-center' });
        homeLi.appendChild(window.domUtils.createElement('a', {
            href: '/dashboard.html',
            className: 'text-gray-400 hover:text-blue-600 transition-colors',
            innerHTML: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path></svg>'
        }));
        list.appendChild(homeLi);

        let currentPath = '';
        parts.forEach((part, index) => {
            currentPath += `/${part}`;
            const isLast = index === parts.length - 1;

            const separator = window.domUtils.createElement('li', {
                className: 'text-gray-300',
                innerHTML: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>'
            });
            list.appendChild(separator);

            const formattedPart = window.formatters ? window.formatters.toTitleCase(part.replace('.html', '')) : part;

            const li = window.domUtils.createElement('li');
            if (isLast) {
                li.appendChild(window.domUtils.createElement('span', {
                    className: 'text-gray-800 font-semibold',
                    textContent: formattedPart
                }));
            } else {
                li.appendChild(window.domUtils.createElement('a', {
                    href: currentPath,
                    className: 'text-gray-500 hover:text-blue-600 transition-colors',
                    textContent: formattedPart
                }));
            }
            list.appendChild(li);
        });

        this.elements.breadcrumb.appendChild(list);
    }

    startNotificationPolling() {
        this.renderNotifications(); 

        setInterval(() => {
            if (window.dashboardApi && !this.state.notificationsOpen) {
                window.dashboardApi.getHitlMetrics().then(data => {
                    const criticalCount = data.pending_risk_distribution?.CRITICAL || 0;
                    if (criticalCount > this.state.unreadCount) {
                        if (window.toastManager) {
                            window.toastManager.warning(`${criticalCount} critical tasks pending review`, 'New Escalation');
                        }
                    }
                    this.state.unreadCount = criticalCount;
                    this.updateNotificationBadge();
                    this.renderNotifications(data);
                }).catch(() => {});
            }
        }, 60000);
    }

    updateNotificationBadge() {
        const badge = this.elements.notificationBtn.querySelector('#notif-badge');
        if (badge) {
            badge.textContent = this.state.unreadCount > 9 ? '9+' : this.state.unreadCount;
            if (this.state.unreadCount > 0) {
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }
    }

    renderNotifications(metricsData = null) {
        window.domUtils.clearChildren(this.elements.notificationDropdown);

        const header = window.domUtils.createElement('div', { className: 'px-4 py-3 border-b border-gray-100 flex justify-between items-center bg-gray-50 rounded-t-lg' });
        header.appendChild(window.domUtils.createElement('h3', { className: 'text-sm font-bold text-gray-900', textContent: 'Notifications' }));

        if (this.state.unreadCount > 0) {
            header.appendChild(window.domUtils.createElement('button', {
                className: 'text-xs text-blue-600 hover:text-blue-800',
                textContent: 'Mark all read',
                onclick: (e) => { e.stopPropagation(); this.state.unreadCount = 0; this.updateNotificationBadge(); this.renderNotifications(); }
            }));
        }
        this.elements.notificationDropdown.appendChild(header);

        const list = window.domUtils.createElement('div', { className: 'max-h-80 overflow-y-auto custom-scrollbar' });

        if (this.state.unreadCount === 0) {
            list.innerHTML = `
                <div class="px-4 py-8 text-center flex flex-col items-center justify-center">
                    <svg class="w-8 h-8 text-gray-300 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path></svg>
                    <p class="text-sm text-gray-500">All caught up!</p>
                </div>
            `;
        } else {
            const notif = window.domUtils.createElement('div', { className: 'px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors cursor-pointer bg-blue-50/50' });
            notif.innerHTML = `
                <div class="flex items-start gap-3">
                    <div class="flex-shrink-0 w-8 h-8 rounded-full bg-red-100 flex items-center justify-center text-red-600 mt-0.5">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                    </div>
                    <div>
                        <p class="text-sm font-medium text-gray-900">Critical Risks Pending</p>
                        <p class="text-xs text-gray-600 mt-0.5">${this.state.unreadCount} items require immediate HITL review.</p>
                        <p class="text-[10px] text-gray-400 mt-1">Just now</p>
                    </div>
                </div>
            `;
            notif.addEventListener('click', () => {
                window.location.href = '/hitl-review.html';
            });
            list.appendChild(notif);
        }

        this.elements.notificationDropdown.appendChild(list);

        const footer = window.domUtils.createElement('div', { className: 'p-2 border-t border-gray-100 bg-gray-50 rounded-b-lg' });
        footer.innerHTML = `<a href="/hitl-review.html" class="block w-full text-center text-sm text-blue-600 hover:text-blue-800 font-medium py-1">View Queue</a>`;
        this.elements.notificationDropdown.appendChild(footer);
    }

    getInitials() {
        if (!window.authStore) return 'U';
        const ctx = window.authStore.getUserContext();
        if (!ctx || !ctx.email) return 'U';
        return ctx.email.charAt(0).toUpperCase();
    }

    applyTheme() {
        if (this.state.isDarkMode) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
    }

    updateThemeIcon() {
        if (!this.elements.themeToggle) return;
        this.elements.themeToggle.innerHTML = this.state.isDarkMode
            ? '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>'
            : '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path></svg>';
    }
}