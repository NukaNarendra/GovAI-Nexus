class DashboardApiService {
  constructor(apiClient) {
      this.api = apiClient;
      this.healthBasePath = '/health';
      this.metricsBasePath = '/hitl/metrics';
      this.auditMetricsBasePath = '/audit/ai-metrics';

      this.cache = new Map();
      this.pollingJobs = new Map();
      this.defaultCacheTTL = 60000;
      this.isPollingActive = false;

      this.subscribers = {
          health: new Set(),
          metrics: new Set(),
          alerts: new Set()
      };
  }

  async getLiveness() {
      return await this.api.get(`${this.healthBasePath}/liveness`);
  }

  async getReadiness() {
      return await this.api.get(`${this.healthBasePath}/readiness`);
  }

  async getDeepHealth(forceRefresh = false) {
      const cacheKey = 'deep_health';

      if (!forceRefresh && this.cache.has(cacheKey)) {
          const cached = this.cache.get(cacheKey);
          if (Date.now() - cached.timestamp < this.defaultCacheTTL) {
              return cached.data;
          }
      }

      try {
          const data = await this.api.get(`${this.healthBasePath}/deep`);
          this.cache.set(cacheKey, { timestamp: Date.now(), data: data });
          this._notifySubscribers('health', data);
          return data;
      } catch (error) {
          const errorPayload = {
              global_status: 'OUTAGE',
              timestamp: new Date().toISOString(),
              components: [],
              metrics: { uptime_seconds: 0, cpu_percent_simulated: 0, memory_usage_mb: 0 },
              error: error.message
          };
          this._notifySubscribers('health', errorPayload);
          throw error;
      }
  }

  async getHitlMetrics(forceRefresh = false) {
      const cacheKey = 'hitl_metrics';

      if (!forceRefresh && this.cache.has(cacheKey)) {
          const cached = this.cache.get(cacheKey);
          if (Date.now() - cached.timestamp < this.defaultCacheTTL) {
              return cached.data;
          }
      }

      try {
          const data = await this.api.get(this.metricsBasePath);
          this.cache.set(cacheKey, { timestamp: Date.now(), data: data });
          return data;
      } catch (error) {
          throw error;
      }
  }

  async getAiExecutionMetrics(daysBack = 1, forceRefresh = false) {
      const cacheKey = `ai_metrics_${daysBack}`;

      if (!forceRefresh && this.cache.has(cacheKey)) {
          const cached = this.cache.get(cacheKey);
          if (Date.now() - cached.timestamp < this.defaultCacheTTL) {
              return cached.data;
          }
      }

      try {
          const data = await this.api.get(`${this.auditMetricsBasePath}?days_back=${daysBack}`);
          this.cache.set(cacheKey, { timestamp: Date.now(), data: data });
          return data;
      } catch (error) {
          throw error;
      }
  }

  async getAggregateDashboardData(daysBack = 1) {
      try {
          const [healthData, hitlData, aiData] = await Promise.all([
              this.getDeepHealth().catch(e => ({ global_status: 'UNKNOWN', error: true })),
              this.getHitlMetrics().catch(e => ({ total_pending: 0, status_counts: {} })),
              this.getAiExecutionMetrics(daysBack).catch(e => ({ total_ai_actions: 0, events_breakdown: {} }))
          ]);

          const aggregated = {
              timestamp: new Date().toISOString(),
              systemHealth: healthData,
              humanInTheLoop: hitlData,
              aiOrchestration: aiData,
              criticalAlerts: this._extractCriticalAlerts(healthData, hitlData)
          };

          this._notifySubscribers('metrics', aggregated);
          if (aggregated.criticalAlerts.length > 0) {
              this._notifySubscribers('alerts', aggregated.criticalAlerts);
          }

          return aggregated;
      } catch (error) {
          throw new Error(`Failed to aggregate dashboard data: ${error.message}`);
      }
  }

  _extractCriticalAlerts(healthData, hitlData) {
      const alerts = [];

      if (healthData.global_status === 'OUTAGE' || healthData.global_status === 'DEGRADED') {
          if (healthData.components) {
              healthData.components.forEach(comp => {
                  if (comp.status !== 'OPERATIONAL') {
                      alerts.push({
                          type: 'INFRASTRUCTURE',
                          severity: comp.status === 'OUTAGE' ? 'CRITICAL' : 'HIGH',
                          source: comp.name,
                          message: comp.message
                      });
                  }
              });
          }
      }

      if (hitlData.active_sla_breaches && hitlData.active_sla_breaches > 0) {
          alerts.push({
              type: 'COMPLIANCE_SLA',
              severity: 'HIGH',
              source: 'HITL Queue',
              message: `${hitlData.active_sla_breaches} tasks have breached their SLA deadlines.`
          });
      }

      if (hitlData.pending_risk_distribution && hitlData.pending_risk_distribution['CRITICAL'] > 0) {
          alerts.push({
              type: 'RISK_THRESHOLD',
              severity: 'CRITICAL',
              source: 'Risk Engine',
              message: `${hitlData.pending_risk_distribution['CRITICAL']} critical risk items awaiting review.`
          });
      }

      return alerts;
  }

  formatChartDataForHitlStatus(hitlData) {
      if (!hitlData || !hitlData.status_counts) return { labels: [], datasets: [] };

      const labels = Object.keys(hitlData.status_counts).map(key => key.replace(/_/g, ' '));
      const data = Object.values(hitlData.status_counts);

      return {
          labels: labels,
          datasets: [{
              data: data,
              backgroundColor: [
                  '#3b82f6', '#f59e0b', '#10b981', '#ef4444', '#6366f1', '#8b5cf6'
              ],
              borderWidth: 0
          }]
      };
  }

  formatChartDataForRiskDistribution(hitlData) {
      if (!hitlData || !hitlData.pending_risk_distribution) return { labels: [], datasets: [] };

      const distribution = hitlData.pending_risk_distribution;
      const labels = ['KYC Anomaly', 'AML Flag', 'Sanctions Match', 'High Value', 'Velocity', 'System Anomaly'];
      const mappedKeys = [
          'KYC_ANOMALY', 'AML_FLAG', 'SANCTIONS_MATCH', 
          'HIGH_VALUE_TRANSFER', 'UNUSUAL_VELOCITY', 'SYSTEM_ANOMALY'
      ];

      const data = mappedKeys.map(key => distribution[key] || 0);

      return {
          labels: labels,
          datasets: [{
              label: 'Pending Risk Distribution',
              data: data,
              backgroundColor: '#3b82f6',
              borderRadius: 4
          }]
      };
  }

  formatChartDataForAiEvents(aiData) {
      if (!aiData || !aiData.events_breakdown) return { labels: [], datasets: [] };

      const labels = Object.keys(aiData.events_breakdown).map(key => key.replace(/_/g, ' '));
      const data = Object.values(aiData.events_breakdown);

      return {
          labels: labels,
          datasets: [{
              label: 'AI Executions',
              data: data,
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              fill: true,
              tension: 0.4
          }]
      };
  }

  subscribe(topic, callback) {
      if (!this.subscribers[topic]) {
          throw new Error(`Unknown subscription topic: ${topic}`);
      }
      this.subscribers[topic].add(callback);
      return () => this.subscribers[topic].delete(callback);
  }

  _notifySubscribers(topic, data) {
      if (this.subscribers[topic]) {
          this.subscribers[topic].forEach(callback => {
              try {
                  callback(data);
              } catch (e) {
                  console.error(`Error in subscriber callback for ${topic}:`, e);
              }
          });
      }
  }

  startDashboardPolling(intervalMs = 30000, daysBack = 1) {
      if (this.isPollingActive) return;

      this.isPollingActive = true;

      const pollTask = async () => {
          if (!this.isPollingActive) return;
          try {
              await this.getAggregateDashboardData(daysBack);
          } catch (e) {
              console.error("Dashboard polling cycle failed", e);
          }
      };

      pollTask();

      const intervalId = setInterval(pollTask, intervalMs);
      this.pollingJobs.set('dashboard_aggregate', intervalId);
  }

  stopDashboardPolling() {
      this.isPollingActive = false;
      if (this.pollingJobs.has('dashboard_aggregate')) {
          clearInterval(this.pollingJobs.get('dashboard_aggregate'));
          this.pollingJobs.delete('dashboard_aggregate');
      }
  }

  clearCache() {
      this.cache.clear();
  }
}

window.dashboardApi = new DashboardApiService(window.apiClient);