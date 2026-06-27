class AuthController {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        if (!this.container) return;

        this.api = window.authApi;
        this.store = window.authStore;
        this.utils = window.domUtils;

        this.state = {
            view: 'LOGIN',
            isLoading: false,
            email: '',
            error: null,
            mfaRequired: false
        };

        this.init();
    }

    init() {
        if (this.store.isAuthenticated()) {
            window.location.href = this.store.getRedirectUrl();
            return;
        }

        this.checkUrlParams();
        this.render();
    }

    checkUrlParams() {
        const urlParams = new URLSearchParams(window.location.search);
        const reason = urlParams.get('reason');
        if (reason) {
            if (reason === 'session_expired' || reason === 'idle_timeout') {
                this.state.error = 'Your session has expired. Please log in again.';
            } else if (reason === 'remote_logout') {
                this.state.error = 'You were logged out from another tab.';
            }
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    }

    render() {
        this.utils.clearChildren(this.container);

        const wrapper = this.utils.createElement('div', {
            className: 'min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8 bg-gradient-to-br from-gray-50 to-gray-100'
        });

        const header = this.utils.createElement('div', { className: 'sm:mx-auto sm:w-full sm:max-w-md text-center' });

        const logo = this.utils.createElement('div', {
            className: 'mx-auto h-16 w-16 bg-blue-600 rounded-xl flex items-center justify-center shadow-lg transform transition-transform hover:scale-105',
            innerHTML: '<svg class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>'
        });

        header.appendChild(logo);
        header.appendChild(this.utils.createElement('h2', {
            className: 'mt-6 text-center text-3xl font-extrabold text-gray-900 tracking-tight',
            textContent: 'Nexus Governance OS'
        }));
        header.appendChild(this.utils.createElement('p', {
            className: 'mt-2 text-center text-sm text-gray-600',
            textContent: 'Enterprise Agentic Compliance Platform'
        }));

        const cardWrapper = this.utils.createElement('div', { className: 'mt-8 sm:mx-auto sm:w-full sm:max-w-md' });
        const card = this.utils.createElement('div', {
            className: 'bg-white py-8 px-4 shadow-xl shadow-gray-200/50 sm:rounded-2xl sm:px-10 border border-gray-100 relative overflow-hidden transition-all duration-300'
        });

        if (this.state.isLoading) {
            const loaderOverlay = this.utils.createElement('div', {
                className: 'absolute inset-0 bg-white/80 backdrop-blur-sm flex items-center justify-center z-10'
            });
            loaderOverlay.appendChild(this.utils.createLoader('large'));
            card.appendChild(loaderOverlay);
        }

        if (this.state.error) {
            const errorAlert = this.utils.createElement('div', {
                className: 'mb-6 p-4 rounded-md bg-red-50 border-l-4 border-red-500 flex items-start gap-3'
            });
            errorAlert.innerHTML = `
                <svg class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                <p class="text-sm text-red-700">${this.utils.sanitizeHTML(this.state.error)}</p>
            `;
            card.appendChild(errorAlert);
        }

        if (this.state.view === 'LOGIN') {
            card.appendChild(this.buildLoginForm());
        } else if (this.state.view === 'MFA') {
            card.appendChild(this.buildMFAForm());
        }

        const footer = this.utils.createElement('div', {
            className: 'mt-8 text-center text-xs text-gray-400',
            innerHTML: `&copy; ${new Date().getFullYear()} Nexus OS. High-Security Enterprise Environment.<br/>Unauthorized access is strictly prohibited and logged.`
        });

        cardWrapper.appendChild(card);
        wrapper.appendChild(header);
        wrapper.appendChild(cardWrapper);
        wrapper.appendChild(footer);

        this.container.appendChild(wrapper);
    }

    buildLoginForm() {
        const form = this.utils.createElement('form', { className: 'space-y-6' });

        const emailDiv = this.utils.createElement('div');
        emailDiv.innerHTML = `
            <label for="email" class="block text-sm font-medium text-gray-700">Enterprise Email</label>
            <div class="mt-1 relative rounded-md shadow-sm">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <svg class="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207"></path></svg>
                </div>
                <input id="email" name="email" type="email" autocomplete="email" required value="${this.state.email}"
                    class="appearance-none block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm transition-colors" 
                    placeholder="officer@nexus.local">
            </div>
        `;
        form.appendChild(emailDiv);

        const passDiv = this.utils.createElement('div');
        passDiv.innerHTML = `
            <label for="password" class="block text-sm font-medium text-gray-700">Master Password</label>
            <div class="mt-1 relative rounded-md shadow-sm">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <svg class="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
                </div>
                <input id="password" name="password" type="password" autocomplete="current-password" required 
                    class="appearance-none block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm transition-colors" 
                    placeholder="••••••••••••••••">
            </div>
        `;
        form.appendChild(passDiv);

        const actionsDiv = this.utils.createElement('div', { className: 'flex items-center justify-between' });
        actionsDiv.innerHTML = `
            <div class="text-sm">
                <a href="#" class="font-medium text-blue-600 hover:text-blue-500 transition-colors">Forgot your password?</a>
            </div>
        `;
        form.appendChild(actionsDiv);

        const submitBtn = this.utils.createElement('button', {
            type: 'submit',
            className: 'w-full flex justify-center py-2.5 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all transform active:scale-[0.98]',
            textContent: 'Authenticate & Enter'
        });
        form.appendChild(submitBtn);

        form.addEventListener('submit', (e) => this.handleLoginSubmit(e));
        return form;
    }

    buildMFAForm() {
        const container = this.utils.createElement('div', { className: 'text-center' });

        container.innerHTML = `
            <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-blue-100 mb-4">
                <svg class="h-6 w-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 11c0 3.517-1.009 6.799-2.753 9.571m-3.44-2.04l.054-.09A13.916 13.916 0 008 11a4 4 0 118 0c0 1.017-.07 2.019-.203 3m-2.118 6.844A21.88 21.88 0 0015.171 17m3.839 1.132c.645-2.266.99-4.659.99-7.132A8 8 0 008 4.07M3 15.364c.64-1.319 1-2.8 1-4.364 0-1.457.39-2.823 1.07-4"></path></svg>
            </div>
            <h3 class="text-lg font-medium text-gray-900 mb-1">Two-Factor Authentication</h3>
            <p class="text-sm text-gray-500 mb-6">Enter the 6-digit code from your authenticator app.</p>
        `;

        const form = this.utils.createElement('form', { className: 'space-y-6' });

        const inputDiv = this.utils.createElement('div');
        inputDiv.innerHTML = `
            <div class="mt-1">
                <input id="mfa_code" name="mfa_code" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="6" required autocomplete="one-time-code"
                    class="appearance-none block w-full px-3 py-3 border border-gray-300 rounded-md placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-center text-2xl tracking-[0.5em] font-mono transition-colors" 
                    placeholder="000000">
            </div>
        `;
        form.appendChild(inputDiv);

        const submitBtn = this.utils.createElement('button', {
            type: 'submit',
            className: 'w-full flex justify-center py-2.5 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all',
            textContent: 'Verify Token'
        });
        form.appendChild(submitBtn);

        const cancelBtn = this.utils.createElement('button', {
            type: 'button',
            className: 'w-full flex justify-center py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none transition-colors mt-3',
            textContent: 'Cancel & Return',
            onclick: () => {
                this.state.view = 'LOGIN';
                this.state.error = null;
                this.render();
            }
        });
        form.appendChild(cancelBtn);

        form.addEventListener('submit', (e) => this.handleMFASubmit(e));
        container.appendChild(form);

        setTimeout(() => {
            const input = container.querySelector('#mfa_code');
            if (input) input.focus();
        }, 100);

        return container;
    }

    async handleLoginSubmit(e) {
        e.preventDefault();
        const values = this.utils.getFormValues(e.target);

        if (!window.validators.isEmail(values.email)) {
            this.state.error = 'Please enter a valid enterprise email format.';
            this.render();
            return;
        }

        this.state.email = values.email;
        this.state.isLoading = true;
        this.state.error = null;
        this.render();

        try {
            const fp = await this.api.generateDeviceFingerprint();
            const response = await this.api.login(values.email, values.password, null, fp);

            if (response.mfa_required) {
                this.state.mfaRequired = true;
                this.state.view = 'MFA';
                this.state.cachedPassword = values.password;
            } else {
                this.store.setSession(response, response.user_context);
                if (window.toastManager) window.toastManager.success('Authentication successful');
                window.location.href = this.store.getRedirectUrl();
            }
        } catch (error) {
            this.state.error = error.message || 'Authentication failed. Please check your credentials.';
            if (error.status === 403) {
                this.state.error = 'Account locked due to multiple failed attempts. Contact IT Security.';
            }
        } finally {
            this.state.isLoading = false;
            this.render();
        }
    }

    async handleMFASubmit(e) {
        e.preventDefault();
        const values = this.utils.getFormValues(e.target);
        const code = values.mfa_code;

        if (!/^\d{6}$/.test(code)) {
            this.state.error = 'MFA code must be exactly 6 digits.';
            this.render();
            return;
        }

        this.state.isLoading = true;
        this.state.error = null;
        this.render();

        try {
            const fp = await this.api.generateDeviceFingerprint();
            const response = await this.api.login(this.state.email, this.state.cachedPassword, code, fp);

            this.store.setSession(response, response.user_context);
            this.state.cachedPassword = null;
            if (window.toastManager) window.toastManager.success('MFA Verification successful');
            window.location.href = this.store.getRedirectUrl();

        } catch (error) {
            this.state.error = error.message || 'Invalid MFA token.';
            const input = document.getElementById('mfa_code');
            if (input) {
                input.value = '';
                input.focus();
            }
        } finally {
            this.state.isLoading = false;
            this.render();
        }
    }
}