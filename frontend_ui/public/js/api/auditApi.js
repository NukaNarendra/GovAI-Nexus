class AuditApiService {
  constructor(apiClient) {
      this.api = apiClient;
      this.basePath = '/audit';
      this.cache = new Map();
      this.activeSubscriptions = new Set();
      this.pollIntervals = new Map();

      this.eventTypes = {
          AI_DECISION_EXECUTED: 'AI_DECISION_EXECUTED',
          AI_DECISION_REJECTED: 'AI_DECISION_REJECTED',
          HITL_OVERRIDE: 'HITL_OVERRIDE',
          HITL_APPROVAL: 'HITL_APPROVAL',
          COMPLIANCE_RULE_TRIGGERED: 'COMPLIANCE_RULE_TRIGGERED',
          RISK_THRESHOLD_EXCEEDED: 'RISK_THRESHOLD_EXCEEDED',
          DATA_INTEGRATION_SYNC: 'DATA_INTEGRATION_SYNC',
          SYSTEM_CONFIGURATION_CHANGED: 'SYSTEM_CONFIGURATION_CHANGED',
          USER_AUTHENTICATION: 'USER_AUTHENTICATION',
          API_KEY_GENERATED: 'API_KEY_GENERATED'
      };

      this.severities = {
          INFO: 'INFO',
          LOW: 'LOW',
          MEDIUM: 'MEDIUM',
          HIGH: 'HIGH',
          CRITICAL: 'CRITICAL'
      };

      this.actorTypes = {
          AI_AGENT: 'AI_AGENT',
          HUMAN_USER: 'HUMAN_USER',
          SYSTEM_PROCESS: 'SYSTEM_PROCESS',
          EXTERNAL_API: 'EXTERNAL_API'
      };
  }

  buildQueryString(filters) {
      const queryParams = new URLSearchParams();
      if (!filters) return '';

      const validKeys = [
          'page', 'size', 'actor_id', 'resource_id', 
          'event_type', 'start_date', 'end_date', 'severity'
      ];

      validKeys.forEach(key => {
          if (filters[key] !== undefined && filters[key] !== null && filters[key] !== '') {
              if (key === 'start_date' || key === 'end_date') {
                  const dateObj = new Date(filters[key]);
                  if (!isNaN(dateObj.getTime())) {
                      queryParams.append(key, dateObj.toISOString());
                  }
              } else if (Array.isArray(filters[key])) {
                  filters[key].forEach(val => queryParams.append(key, val));
              } else {
                  queryParams.append(key, filters[key]);
              }
          }
      });

      const queryString = queryParams.toString();
      return queryString ? `?${queryString}` : '';
  }

  async getLogs(filters = {}) {
      const defaultFilters = { page: 1, size: 50 };
      const mergedFilters = { ...defaultFilters, ...filters };
      const queryString = this.buildQueryString(mergedFilters);
      const url = `${this.basePath}/logs${queryString}`;

      return await this.api.get(url);
  }

  async getLogsWithCache(filters = {}, ttl = 30000) {
      const defaultFilters = { page: 1, size: 50 };
      const mergedFilters = { ...defaultFilters, ...filters };
      const queryString = this.buildQueryString(mergedFilters);
      const url = `${this.basePath}/logs${queryString}`;

      if (this.cache.has(url)) {
          const cached = this.cache.get(url);
          if (Date.now() - cached.timestamp < ttl) {
              return cached.data;
          }
          this.cache.delete(url);
      }

      const data = await this.api.get(url);
      this.cache.set(url, {
          timestamp: Date.now(),
          data: data
      });

      return data;
  }

  async getLogById(logId) {
      if (!logId) throw new Error('Log ID is required');
      const filters = { resource_id: logId, size: 1 };
      const response = await this.getLogs(filters);
      if (response && response.items && response.items.length > 0) {
          return response.items[0];
      }
      throw new Error('Audit log entry not found');
  }

  async getLogsByActor(actorId, page = 1, size = 50) {
      if (!actorId) throw new Error('Actor ID is required');
      return await this.getLogs({ actor_id: actorId, page, size });
  }

  async getLogsByResource(resourceId, page = 1, size = 50) {
      if (!resourceId) throw new Error('Resource ID is required');
      return await this.getLogs({ resource_id: resourceId, page, size });
  }

  async getLogsByEventType(eventType, page = 1, size = 50) {
      if (!eventType) throw new Error('Event Type is required');
      return await this.getLogs({ event_type: eventType, page, size });
  }

  async getHighRiskEvents(hoursBack = 24, page = 1, size = 50) {
      const startDate = new Date(Date.now() - (hoursBack * 60 * 60 * 1000)).toISOString();
      const filters = {
          start_date: startDate,
          severity: [this.severities.HIGH, this.severities.CRITICAL],
          page: page,
          size: size
      };
      return await this.getLogs(filters);
  }

  async getAiExecutionEvents(daysBack = 7, page = 1, size = 50) {
      const startDate = new Date(Date.now() - (daysBack * 24 * 60 * 60 * 1000)).toISOString();
      const filters = {
          start_date: startDate,
          event_type: this.eventTypes.AI_DECISION_EXECUTED,
          page: page,
          size: size
      };
      return await this.getLogs(filters);
  }

  async getHitlOverrideEvents(daysBack = 7, page = 1, size = 50) {
      const startDate = new Date(Date.now() - (daysBack * 24 * 60 * 60 * 1000)).toISOString();
      const filters = {
          start_date: startDate,
          event_type: this.eventTypes.HITL_OVERRIDE,
          page: page,
          size: size
      };
      return await this.getLogs(filters);
  }

  async getComplianceViolations(daysBack = 7, page = 1, size = 50) {
      const startDate = new Date(Date.now() - (daysBack * 24 * 60 * 60 * 1000)).toISOString();
      const filters = {
          start_date: startDate,
          event_type: this.eventTypes.COMPLIANCE_RULE_TRIGGERED,
          page: page,
          size: size
      };
      return await this.getLogs(filters);
  }

  async verifyChainIntegrity(daysBack = 7) {
      const validDays = Math.max(1, Math.min(365, parseInt(daysBack)));
      if (isNaN(validDays)) throw new Error('daysBack must be a valid integer');

      const url = `${this.basePath}/verify-chain?days_back=${validDays}`;
      return await this.api.post(url, {});
  }

  async verifySpecificLogChain(logId) {
      if (!logId) throw new Error('Log ID is required');
      const targetLog = await this.getLogById(logId);

      if (!targetLog) throw new Error('Log not found for verification');

      const previousLogId = targetLog.previous_hash;
      if (!previousLogId || previousLogId === '0000000000000000000000000000000000000000000000000000000000000000') {
          return {
              verified: targetLog.is_tampered === false,
              isGenesis: true,
              log: targetLog
          };
      }

      return {
          verified: targetLog.is_tampered === false,
          isGenesis: false,
          log: targetLog
      };
  }

  async exportLedger(startDate, endDate, format = 'json') {
      const start = new Date(startDate);
      const end = new Date(endDate);

      if (isNaN(start.getTime()) || isNaN(end.getTime())) {
          throw new Error('Invalid start or end date');
      }

      if (start.getTime() > end.getTime()) {
          throw new Error('Start date must be before end date');
      }

      if (format === 'csv') {
          // Direct download from backend streaming endpoint
          const url = `${window.apiClient.baseURL}${this.basePath}/export/csv`;
          const a = document.createElement('a');
          a.style.display = 'none';
          // append token if needed or just rely on cookies/local storage. Since we use bearer tokens, we must fetch and blob.
          const headers = { 'Authorization': `Bearer ${window.authStore.getToken()}` };
          const response = await fetch(url, { headers });
          if (!response.ok) throw new Error('Failed to download CSV');
          const blob = await response.blob();
          const downloadUrl = window.URL.createObjectURL(blob);
          a.href = downloadUrl;
          a.download = `regulatory_audit_report_${Date.now()}.csv`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(downloadUrl);
          document.body.removeChild(a);
          return { status: 'success' };
      }

      const queryString = `?start_date=${start.toISOString()}&end_date=${end.toISOString()}`;
      const url = `${this.basePath}/export${queryString}`;
      const response = await this.api.get(url);

      if (format === 'json') {
          this.downloadJSON(response, `audit_ledger_export_${Date.now()}.json`);
      }

      return response;
  }

  async getAiMetrics(daysBack = 1) {
      const validDays = Math.max(1, Math.min(90, parseInt(daysBack)));
      if (isNaN(validDays)) throw new Error('daysBack must be a valid integer');

      const url = `${this.basePath}/ai-metrics?days_back=${validDays}`;
      return await this.api.get(url);
  }

  async getComprehensiveAuditStats(daysBack = 7) {
      const [chainIntegrity, aiMetrics] = await Promise.all([
          this.verifyChainIntegrity(daysBack).catch(() => ({ status: 'UNKNOWN' })),
          this.getAiMetrics(daysBack).catch(() => ({ total_ai_actions: 0 }))
      ]);

      return {
          chainStatus: chainIntegrity,
          aiActivity: aiMetrics,
          timestamp: new Date().toISOString()
      };
  }

  startPollingRecentLogs(callback, intervalMs = 15000) {
      const pollId = this.api.generateUUID ? this.api.generateUUID() : Date.now().toString();

      const pollFunction = async () => {
          try {
              const recentLogs = await this.getLogs({ page: 1, size: 20 });
              callback(null, recentLogs);
          } catch (error) {
              callback(error, null);
          }
      };

      const intervalId = setInterval(pollFunction, intervalMs);
      this.pollIntervals.set(pollId, intervalId);

      pollFunction();

      return pollId;
  }

  stopPolling(pollId) {
      if (this.pollIntervals.has(pollId)) {
          clearInterval(this.pollIntervals.get(pollId));
          this.pollIntervals.delete(pollId);
          return true;
      }
      return false;
  }

  stopAllPolling() {
      this.pollIntervals.forEach((intervalId) => {
          clearInterval(intervalId);
      });
      this.pollIntervals.clear();
  }

  clearCache() {
      this.cache.clear();
  }

  convertToCSV(records) {
      if (!records || !records.length) return '';

      const headers = [
          'ID', 'Timestamp', 'Event Type', 'Severity', 
          'Actor ID', 'Actor Type', 'Resource ID', 
          'Action Details', 'Cryptographic Hash', 'Previous Hash', 'Is Tampered'
      ];

      const rows = records.map(record => {
          return [
              record.id || '',
              record.timestamp || '',
              record.event_type || '',
              record.severity || '',
              record.actor_id || '',
              record.actor_type || '',
              record.resource_id || '',
              `"${(record.action_details || '').replace(/"/g, '""')}"`,
              record.cryptographic_hash || '',
              record.previous_hash || '',
              record.is_tampered ? 'YES' : 'NO'
          ].join(',');
      });

      return [headers.join(','), ...rows].join('\n');
  }

  downloadJSON(data, filename) {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.setAttribute('hidden', '');
      a.setAttribute('href', url);
      a.setAttribute('download', filename);
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
  }

  downloadCSV(csvString, filename) {
      const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.setAttribute('hidden', '');
      a.setAttribute('href', url);
      a.setAttribute('download', filename);
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
  }
}

window.auditApi = new AuditApiService(window.apiClient);