const validators = {
  patterns: {
      email: /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,
      url: /^(https?:\/\/)?([\da-z.-]+)\.([a-z.]{2,6})([/\w .-]*)*\/?$/,
      ipv4: /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/,
      ipv6: /^(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))$/,
      uuid: /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
      macAddress: /^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$/,
      jwt: /^[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]*$/,
      hexColor: /^#?([a-fA-F0-9]{6}|[a-fA-F0-9]{3})$/,
      alphaNumeric: /^[a-zA-Z0-9]+$/,
      numeric: /^\d+$/,
      base64: /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/,
      swiftBic: /^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$/,
      sanctionsMatch: /(global\s*shell\s*corp|restricted\s*trading\s*ltd|sanctioned\s*oil\s*inc)/i
  },

  isString(value) {
      return typeof value === 'string' || value instanceof String;
  },

  isNumber(value) {
      return typeof value === 'number' && !isNaN(value);
  },

  isBoolean(value) {
      return typeof value === 'boolean';
  },

  isObject(value) {
      return value !== null && typeof value === 'object' && !Array.isArray(value);
  },

  isArray(value) {
      return Array.isArray(value);
  },

  isFunction(value) {
      return typeof value === 'function';
  },

  isEmpty(value) {
      if (value === null || value === undefined) return true;
      if (this.isString(value) && value.trim().length === 0) return true;
      if (this.isArray(value) && value.length === 0) return true;
      if (this.isObject(value) && Object.keys(value).length === 0) return true;
      return false;
  },

  isRequired(value) {
      return !this.isEmpty(value);
  },

  isEmail(email) {
      if (!this.isString(email)) return false;
      return this.patterns.email.test(email);
  },

  isUrl(url) {
      if (!this.isString(url)) return false;
      return this.patterns.url.test(url);
  },

  isIP(ip) {
      if (!this.isString(ip)) return false;
      return this.patterns.ipv4.test(ip) || this.patterns.ipv6.test(ip);
  },

  isUUID(uuid) {
      if (!this.isString(uuid)) return false;
      return this.patterns.uuid.test(uuid);
  },

  isJWT(token) {
      if (!this.isString(token)) return false;
      return this.patterns.jwt.test(token);
  },

  isBase64(str) {
      if (!this.isString(str)) return false;
      return this.patterns.base64.test(str);
  },

  isAlphaNumeric(str) {
      if (!this.isString(str)) return false;
      return this.patterns.alphaNumeric.test(str);
  },

  isNumericOnly(str) {
      if (!this.isString(str) && !this.isNumber(str)) return false;
      return this.patterns.numeric.test(String(str));
  },

  isValidLength(str, min, max) {
      if (!this.isString(str)) return false;
      const len = str.length;
      if (min !== undefined && len < min) return false;
      if (max !== undefined && len > max) return false;
      return true;
  },

  isInRange(num, min, max) {
      if (!this.isNumber(num)) return false;
      if (min !== undefined && num < min) return false;
      if (max !== undefined && num > max) return false;
      return true;
  },

  isDateValid(dateInput) {
      if (dateInput instanceof Date) return !isNaN(dateInput.getTime());
      if (!this.isString(dateInput) && !this.isNumber(dateInput)) return false;
      const date = new Date(dateInput);
      return !isNaN(date.getTime());
  },

  isFutureDate(dateInput) {
      if (!this.isDateValid(dateInput)) return false;
      const date = new Date(dateInput);
      const now = new Date();
      return date.getTime() > now.getTime();
  },

  isPastDate(dateInput) {
      if (!this.isDateValid(dateInput)) return false;
      const date = new Date(dateInput);
      const now = new Date();
      return date.getTime() < now.getTime();
  },

  validatePasswordStrength(password) {
      if (!this.isString(password)) return { valid: false, score: 0, feedback: ['Must be a string'] };

      let score = 0;
      let feedback = [];

      if (password.length < 12) {
          feedback.push('Password must be at least 12 characters long');
      } else {
          score += 25;
      }

      if (password.length >= 16) {
          score += 15;
      }

      if (/[A-Z]/.test(password)) {
          score += 15;
      } else {
          feedback.push('Must contain at least one uppercase letter');
      }

      if (/[a-z]/.test(password)) {
          score += 15;
      } else {
          feedback.push('Must contain at least one lowercase letter');
      }

      if (/[0-9]/.test(password)) {
          score += 15;
      } else {
          feedback.push('Must contain at least one number');
      }

      if (/[^A-Za-z0-9]/.test(password)) {
          score += 15;
      } else {
          feedback.push('Must contain at least one special character');
      }

      const valid = score >= 85 && feedback.length === 0;

      return {
          valid,
          score,
          feedback,
          strength: score >= 85 ? 'STRONG' : score >= 55 ? 'MODERATE' : 'WEAK'
      };
  },

  validateLuhn(cardNumber) {
      if (!this.isString(cardNumber) && !this.isNumber(cardNumber)) return false;
      const str = String(cardNumber).replace(/\D/g, '');
      if (str.length === 0) return false;

      let sum = 0;
      let isSecond = false;

      for (let i = str.length - 1; i >= 0; i--) {
          let d = parseInt(str.charAt(i), 10);

          if (isSecond) {
              d = d * 2;
              if (d > 9) {
                  d -= 9;
              }
          }

          sum += d;
          isSecond = !isSecond;
      }

      return (sum % 10) === 0;
  },

  validateIBAN(iban) {
      if (!this.isString(iban)) return false;
      const str = iban.replace(/\s+/g, '').toUpperCase();

      if (str.length < 15 || str.length > 34) return false;

      if (!/^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$/.test(str)) return false;

      const rearranged = str.substring(4) + str.substring(0, 4);

      const numericStr = rearranged.replace(/[A-Z]/g, (match) => {
          return (match.charCodeAt(0) - 55).toString();
      });

      let remainder = numericStr;
      let block;

      while (remainder.length > 2) {
          block = remainder.slice(0, 9);
          remainder = (parseInt(block, 10) % 97) + remainder.slice(block.length);
      }

      return parseInt(remainder, 10) % 97 === 1;
  },

  validateSwiftBic(bic) {
      if (!this.isString(bic)) return false;
      return this.patterns.swiftBic.test(bic.toUpperCase().trim());
  },

  hasSanctionsHit(text) {
      if (!this.isString(text)) return false;
      return this.patterns.sanctionsMatch.test(text);
  },

  validateFileSize(file, maxSizeMB) {
      if (!file || !file.size) return false;
      const bytesInMB = 1048576;
      const maxBytes = maxSizeMB * bytesInMB;
      return file.size <= maxBytes;
  },

  validateFileType(file, allowedTypes) {
      if (!file || !file.type) return false;
      if (!this.isArray(allowedTypes)) return false;

      const fileType = file.type.toLowerCase();
      return allowedTypes.some(type => {
          if (type.endsWith('/*')) {
              const baseType = type.split('/')[0];
              return fileType.startsWith(baseType + '/');
          }
          return fileType === type.toLowerCase();
      });
  },

  validateSchema(data, schema) {
      const errors = [];

      if (!this.isObject(data) || !this.isObject(schema)) {
          return { valid: false, errors: ['Data and schema must be objects'] };
      }

      for (const [field, rules] of Object.entries(schema)) {
          const value = data[field];

          if (rules.required && this.isEmpty(value)) {
              errors.push({ field, message: `${field} is required` });
              continue;
          }

          if (this.isEmpty(value)) continue;

          if (rules.type) {
              let typeValid = false;
              switch (rules.type) {
                  case 'string': typeValid = this.isString(value); break;
                  case 'number': typeValid = this.isNumber(value); break;
                  case 'boolean': typeValid = this.isBoolean(value); break;
                  case 'array': typeValid = this.isArray(value); break;
                  case 'object': typeValid = this.isObject(value); break;
                  case 'email': typeValid = this.isEmail(value); break;
                  case 'uuid': typeValid = this.isUUID(value); break;
                  case 'date': typeValid = this.isDateValid(value); break;
                  case 'iban': typeValid = this.validateIBAN(value); break;
              }
              if (!typeValid) {
                  errors.push({ field, message: `${field} must be of type ${rules.type}` });
              }
          }

          if (rules.minLength !== undefined && this.isString(value)) {
              if (value.length < rules.minLength) {
                  errors.push({ field, message: `${field} must be at least ${rules.minLength} characters` });
              }
          }

          if (rules.maxLength !== undefined && this.isString(value)) {
              if (value.length > rules.maxLength) {
                  errors.push({ field, message: `${field} must not exceed ${rules.maxLength} characters` });
              }
          }

          if (rules.min !== undefined && this.isNumber(value)) {
              if (value < rules.min) {
                  errors.push({ field, message: `${field} must be at least ${rules.min}` });
              }
          }

          if (rules.max !== undefined && this.isNumber(value)) {
              if (value > rules.max) {
                  errors.push({ field, message: `${field} must not exceed ${rules.max}` });
              }
          }

          if (rules.pattern && this.isString(value)) {
              const regex = rules.pattern instanceof RegExp ? rules.pattern : new RegExp(rules.pattern);
              if (!regex.test(value)) {
                  errors.push({ field, message: `${field} format is invalid` });
              }
          }

          if (rules.enum && this.isArray(rules.enum)) {
              if (!rules.enum.includes(value)) {
                  errors.push({ field, message: `${field} must be one of: ${rules.enum.join(', ')}` });
              }
          }

          if (rules.custom && this.isFunction(rules.custom)) {
              const customValid = rules.custom(value, data);
              if (!customValid) {
                  errors.push({ field, message: rules.customMessage || `${field} failed custom validation` });
              }
          }
      }

      return {
          valid: errors.length === 0,
          errors
      };
  }
};

window.validators = validators;