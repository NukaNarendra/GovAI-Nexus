class AuthApiService {
  constructor(apiClient) {
      this.api = apiClient;
      this.basePath = '/auth';
  }

    async login(username, password, mfaToken = null, deviceFingerprint = null) {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        formData.append('grant_type', 'password');

        if (mfaToken) {
            formData.append('mfa_token', mfaToken);
        }

        const headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        };

        if (deviceFingerprint) {
            headers['X-Device-Fingerprint'] = deviceFingerprint;
        }

        // FIX: Added .toString() so apiClient doesn't turn it into an empty JSON object!
        const response = await this.api.post(`${this.basePath}/login`, formData.toString(), { headers });
        return response;
    }

    async ssoLogin(provider, ssoToken, redirectUri) {
      const payload = {
          provider: provider,
          token: ssoToken,
          redirect_uri: redirectUri,
          initiated_at: new Date().toISOString()
      };
      return await this.api.post(`${this.basePath}/sso/verify`, payload);
  }

  async logout(global = false) {
      const endpoint = global ? `${this.basePath}/logout/all` : `${this.basePath}/logout`;
      try {
          await this.api.post(endpoint);
      } catch (e) {
          console.error('Logout request failed, cleaning local state anyway', e);
      }
      if (window.authStore) {
          window.authStore.logout('user_initiated');
      }
  }

  async refreshToken() {
      const currentRefreshToken = localStorage.getItem('refresh_token');
      if (!currentRefreshToken) {
          throw new Error('No refresh token available');
      }
      const response = await this.api.post(`${this.basePath}/refresh`, null, {
          headers: {
              'Authorization': `Bearer ${currentRefreshToken}`
          }
      });
      return response;
  }

  async changePassword(currentPassword, newPassword, confirmNewPassword) {
      if (newPassword !== confirmNewPassword) {
          throw new Error('New passwords do not match');
      }
      const payload = {
          current_password: currentPassword,
          new_password: newPassword,
          confirm_new_password: confirmNewPassword
      };
      return await this.api.post(`${this.basePath}/password/change`, payload);
  }

  async requestPasswordReset(email) {
      const payload = {
          email: email,
          request_origin: window.location.origin
      };
      return await this.api.post(`${this.basePath}/password/reset-request`, payload);
  }

  async confirmPasswordReset(resetToken, newPassword, confirmPassword) {
      const payload = {
          reset_token: resetToken,
          new_password: newPassword,
          confirm_password: confirmPassword
      };
      return await this.api.post(`${this.basePath}/password/reset-confirm`, payload);
  }

  async getActiveSessions() {
      return await this.api.get(`${this.basePath}/sessions`);
  }

  async revokeSession(sessionId) {
      return await this.api.delete(`${this.basePath}/sessions/${sessionId}`);
  }

  async revokeAllOtherSessions() {
      return await this.api.delete(`${this.basePath}/sessions/others`);
  }

  async listApiKeys() {
      return await this.api.get(`${this.basePath}/api-keys`);
  }

  async createApiKey(name, allowedIps = null, expirationDays = 30) {
      const payload = {
          name: name,
          expiration_days: expirationDays
      };
      if (allowedIps) {
          payload.allowed_ips = allowedIps;
      }
      return await this.api.post(`${this.basePath}/api-keys`, payload);
  }

  async revokeApiKey(keyId) {
      return await this.api.delete(`${this.basePath}/api-keys/${keyId}`);
  }

  async rotateApiKey(keyId, expirationDays = 30) {
      const payload = {
          expiration_days: expirationDays
      };
      return await this.api.post(`${this.basePath}/api-keys/${keyId}/rotate`, payload);
  }

  async getMyProfile() {
      return await this.api.get(`${this.basePath}/me`);
  }

  async updateMyProfile(profileData) {
      const allowedFields = ['first_name', 'last_name', 'phone_number', 'timezone', 'language_preference'];
      const payload = {};
      for (const key of allowedFields) {
          if (profileData[key] !== undefined) {
              payload[key] = profileData[key];
          }
      }
      return await this.api.patch(`${this.basePath}/me`, payload);
  }

  async setupMFA() {
      return await this.api.post(`${this.basePath}/mfa/setup`);
  }

  async verifyMFASetup(code, backupCodeStorageVerified = false) {
      const payload = {
          verification_code: code,
          backup_codes_saved: backupCodeStorageVerified
      };
      return await this.api.post(`${this.basePath}/mfa/verify-setup`, payload);
  }

  async disableMFA(currentPassword, mfaCode) {
      const payload = {
          password: currentPassword,
          verification_code: mfaCode
      };
      return await this.api.post(`${this.basePath}/mfa/disable`, payload);
  }

  async generateNewBackupCodes(mfaCode) {
      const payload = {
          verification_code: mfaCode
      };
      return await this.api.post(`${this.basePath}/mfa/backup-codes/regenerate`, payload);
  }

  async registerWebAuthnDevice(deviceName) {
      const challengeResponse = await this.api.post(`${this.basePath}/webauthn/register/challenge`, { device_name: deviceName });
      const credentialCreationOptions = this.transformWebAuthnOptions(challengeResponse);

      let credential;
      try {
          credential = await navigator.credentials.create({ publicKey: credentialCreationOptions });
      } catch (e) {
          throw new Error(`WebAuthn creation failed: ${e.message}`);
      }

      const verificationPayload = {
          id: credential.id,
          rawId: this.arrayBufferToBase64(credential.rawId),
          response: {
              clientDataJSON: this.arrayBufferToBase64(credential.response.clientDataJSON),
              attestationObject: this.arrayBufferToBase64(credential.response.attestationObject)
          },
          type: credential.type
      };

      return await this.api.post(`${this.basePath}/webauthn/register/verify`, verificationPayload);
  }

  async listWebAuthnDevices() {
      return await this.api.get(`${this.basePath}/webauthn/devices`);
  }

  async removeWebAuthnDevice(deviceId) {
      return await this.api.delete(`${this.basePath}/webauthn/devices/${deviceId}`);
  }

  async getRolePermissions() {
      const context = window.authStore ? window.authStore.getUserContext() : null;
      if (!context || !context.role) {
          return [];
      }
      return await this.api.get(`${this.basePath}/roles/${context.role}/permissions`, {}, { cache: true, cacheTTL: 3600000 });
  }

  async checkPermission(permissionCode) {
      try {
          const permissions = await this.getRolePermissions();
          return permissions.includes(permissionCode);
      } catch {
          return false;
      }
  }

  async getLoginHistory(page = 1, size = 20) {
      return await this.api.get(`${this.basePath}/history`, { page, size });
  }

  arrayBufferToBase64(buffer) {
      let binary = '';
      const bytes = new Uint8Array(buffer);
      const len = bytes.byteLength;
      for (let i = 0; i < len; i++) {
          binary += String.fromCharCode(bytes[i]);
      }
      return window.btoa(binary);
  }

  base64ToArrayBuffer(base64) {
      const binary_string = window.atob(base64);
      const len = binary_string.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
          bytes[i] = binary_string.charCodeAt(i);
      }
      return bytes.buffer;
  }

  transformWebAuthnOptions(options) {
      const transformed = { ...options };
      if (transformed.challenge) {
          transformed.challenge = this.base64ToArrayBuffer(transformed.challenge);
      }
      if (transformed.user && transformed.user.id) {
          transformed.user.id = this.base64ToArrayBuffer(transformed.user.id);
      }
      if (transformed.excludeCredentials) {
          transformed.excludeCredentials = transformed.excludeCredentials.map(cred => ({
              ...cred,
              id: this.base64ToArrayBuffer(cred.id)
          }));
      }
      return transformed;
  }

  generateDeviceFingerprint() {
      return new Promise((resolve) => {
          const components = [
              navigator.userAgent,
              navigator.language,
              new Date().getTimezoneOffset(),
              navigator.hardwareConcurrency,
              navigator.deviceMemory,
              window.screen.colorDepth,
              window.screen.width + 'x' + window.screen.height,
              !!window.sessionStorage,
              !!window.localStorage,
              !!window.indexedDB,
              typeof window.openDatabase,
              navigator.platform,
              navigator.doNotTrack,
              this.getCanvasFingerprint(),
              this.getWebGLFingerprint()
          ];

          const rawFingerprint = components.join('###');
          this.hashString(rawFingerprint).then(hash => resolve(hash));
      });
  }

  getCanvasFingerprint() {
      try {
          const canvas = document.createElement('canvas');
          const ctx = canvas.getContext('2d');
          canvas.width = 200;
          canvas.height = 50;
          ctx.textBaseline = 'top';
          ctx.font = '14px Arial';
          ctx.textBaseline = 'alphabetic';
          ctx.fillStyle = '#f60';
          ctx.fillRect(125, 1, 62, 20);
          ctx.fillStyle = '#069';
          ctx.fillText('Enterprise OS', 2, 15);
          ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
          ctx.fillText('Governance', 4, 17);
          return canvas.toDataURL();
      } catch (e) {
          return 'canvas_error';
      }
  }

  getWebGLFingerprint() {
      try {
          const canvas = document.createElement('canvas');
          const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
          if (!gl) return 'webgl_not_supported';
          const ext = gl.getExtension('WEBGL_debug_renderer_info');
          if (!ext) return 'webgl_extension_not_supported';
          const vendor = gl.getParameter(ext.UNMASKED_VENDOR_WEBGL);
          const renderer = gl.getParameter(ext.UNMASKED_RENDERER_WEBGL);
          return `${vendor}~${renderer}`;
      } catch (e) {
          return 'webgl_error';
      }
  }

  async hashString(str) {
      const msgUint8 = new TextEncoder().encode(str);
      const hashBuffer = await crypto.subtle.digest('SHA-256', msgUint8);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
      return hashHex;
  }
}

window.authApi = new AuthApiService(window.apiClient);