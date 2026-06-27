class DashboardController {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        if (!this.container) return;

        this.api = window.dashboardApi;
        this.store = window.authStore;
        this.utils = window.domUtils;
        this.formatters = window.formatters;

        this.state = {
            isLoading: true,
            data: null,
            error: null,
            autoRefresh: true
        };

        this.elements = {
            mainWrapper: null,
            kpiGrid: null,
            healthSection: null,
            alertsSection: null,
            chartsSection: null,
            refreshBtn: null
        };

        this.init();
    }

    async init() {
        this.store.enforceAuth();
        this.buildLayout();
        await this.loadData();

        if (this.state.autoRefresh) {
            this.api.startDashboardPolling(30000, 1);
            this.api.subscribe('metrics', (data) => {
                this.state.data = data;
                this.render();
            });
        }
    }

    buildLayout() {
        this.utils.clearChildren(this.container);

        this.elements.mainWrapper = this.utils.createElement('div', {
            className: 'p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto space-y-6'
        });

        const headerRow = this.utils.createElement('div', {
            className: 'flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6'
        });

        const titleWrapper = this.utils.createElement('div');
        titleWrapper.appendChild(this.utils.createElement('h1', {
            className: 'text-2xl font-bold text-gray-900',
            textContent: 'Enterprise Governance Dashboard'
        }));
        titleWrapper.appendChild(this.utils.createElement('p', {
            className: 'text-sm text-gray-500 mt-1',
            textContent: 'Real-time system telemetry and compliance queue overview'
        }));

        const controlsWrapper = this.utils.createElement('div', {
            className: 'flex items-center gap-3'
        });

        this.elements.refreshBtn = this.utils.createElement('button', {
            className: 'flex items-center gap-2 px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none transition-colors',
            innerHTML: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg> Refresh',
            onclick: () => this.handleManualRefresh()
        });

        controlsWrapper.appendChild(this.elements.refreshBtn);
        headerRow.appendChild(titleWrapper);
        headerRow.appendChild(controlsWrapper);

        this.elements.kpiGrid = this.utils.createElement('div', {
            className: 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4'
        });

        const middleRow = this.utils.createElement('div', {
            className: 'grid grid-cols-1 lg:grid-cols-3 gap-6'
        });

        this.elements.healthSection = this.utils.createElement('div', {
            className: 'col-span-1 lg:col-span-2 space-y-6'
        });

        this.elements.alertsSection = this.utils.createElement('div', {
            className: 'col-span-1 space-y-6'
        });

        middleRow.appendChild(this.elements.healthSection);
        middleRow.appendChild(this.elements.alertsSection);

        this.elements.chartsSection = this.utils.createElement('div', {
            className: 'grid grid-cols-1 lg:grid-cols-2 gap-6'
        });

        this.elements.mainWrapper.appendChild(headerRow);
        this.elements.mainWrapper.appendChild(this.elements.kpiGrid);
        this.elements.mainWrapper.appendChild(middleRow);
        this.elements.mainWrapper.appendChild(this.elements.chartsSection);

        this.container.appendChild(this.elements.mainWrapper);
    }

    async loadData() {
        this.setLoadingState(true);
        try {
            this.state.data = await this.api.getAggregateDashboardData(1);
            this.state.error = null;
        } catch (err) {
            this.state.error = err.message;
            if (window.toastManager) window.toastManager.error('Failed to load dashboard telemetry');
        } finally {
            this.setLoadingState(false);
            this.render();
        }
    }

    async handleManualRefresh() {
        const icon = this.elements.refreshBtn.querySelector('svg');
        if (icon) icon.classList.add('animate-spin');

        try {
            this.api.clearCache();
            this.state.data = await this.api.getAggregateDashboardData(1);
            this.render();
            if (window.toastManager) window.toastManager.success('Dashboard synchronized');
        } catch (err) {
            if (window.toastManager) window.toastManager.error('Synchronization failed');
        } finally {
            if (icon) icon.classList.remove('animate-spin');
        }
    }

    setLoadingState(isLoading) {
        if (isLoading) {
            this.utils.clearChildren(this.elements.kpiGrid);
            for (let i = 0; i < 4; i++) {
                this.elements.kpiGrid.appendChild(this.buildSkeletonCard());
            }
            this.utils.clearChildren(this.elements.healthSection);
            this.elements.healthSection.appendChild(this.buildSkeletonCard(300));
        }
    }

    buildSkeletonCard(height = 120) {
        return this.utils.createElement('div', {
            className: 'bg-white rounded-xl shadow-sm border border-gray-200 p-6 animate-pulse',
            style: { height: `${height}px` }
        }, [
            this.utils.createElement('div', { className: 'h-4 bg-gray-200 rounded w-1/3 mb-4' }),
            this.utils.createElement('div', { className: 'h-8 bg-gray-200 rounded w-1/2' })
        ]);
    }

    render() {
        if (this.state.error) return this.renderError();
        if (!this.state.data) return;

        this.renderKPIs();
        this.renderHealth();
        this.renderAlerts();
        this.renderCharts();
    }

    renderError() {
        this.utils.clearChildren(this.elements.kpiGrid);
        const errorCard = this.utils.createElement('div', {
            className: 'col-span-full bg-red-50 rounded-xl border border-red-200 p-6 flex items-center gap-4 text-red-700'
        });
        errorCard.innerHTML = `
            <svg class="w-8 h-8 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
            <div>
                <h3 class="text-lg font-bold">Telemetry Outage</h3>
                <p class="text-sm mt-1">${this.utils.sanitizeHTML(this.state.error)}</p>
            </div>
        `;
        this.elements.kpiGrid.appendChild(errorCard);
    }

    renderKPIs() {
        this.utils.clearChildren(this.elements.kpiGrid);
        const hitl = this.state.data.humanInTheLoop;
        const ai = this.state.data.aiOrchestration;

        const kpis = [
            {
                title: 'Pending Approvals',
                value: hitl.total_pending || 0,
                subtitle: 'Tasks in HITL queue',
                icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path>',
                color: 'blue'
            },
            {
                title: 'Critical Risk Items',
                value: (hitl.pending_risk_distribution && hitl.pending_risk_distribution['CRITICAL']) || 0,
                subtitle: 'Requires immediate action',
                icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>',
                color: 'red',
                alert: (hitl.pending_risk_distribution && hitl.pending_risk_distribution['CRITICAL']) > 0
            },
            {
                title: 'SLA Breaches',
                value: hitl.active_sla_breaches || 0,
                subtitle: 'Tasks exceeding time limits',
                icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>',
                color: 'orange',
                alert: hitl.active_sla_breaches > 0
            },
            {
                title: 'AI Interventions',
                value: ai.total_ai_actions || 0,
                subtitle: 'Automated decisions (24h)',
                icon: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>',
                color: 'green'
            }
        ];

        kpis.forEach(kpi => {
            const card = this.utils.createElement('div', {
                className: `bg-white rounded-xl shadow-sm border ${kpi.alert ? 'border-red-300 ring-1 ring-red-100' : 'border-gray-200'} p-6 relative overflow-hidden`
            });

            if (kpi.alert) {
                card.appendChild(this.utils.createElement('div', {
                    className: 'absolute top-0 right-0 w-2 h-full bg-red-500'
                }));
            }

            const header = this.utils.createElement('div', { className: 'flex justify-between items-start' });

            const textWrap = this.utils.createElement('div');
            textWrap.appendChild(this.utils.createElement('p', {
                className: 'text-sm font-medium text-gray-500',
                textContent: kpi.title
            }));
            textWrap.appendChild(this.utils.createElement('h3', {
                className: 'text-3xl font-bold text-gray-900 mt-2',
                textContent: kpi.value.toLocaleString()
            }));

            const iconWrap = this.utils.createElement('div', {
                className: `p-3 rounded-lg bg-${kpi.color}-50 text-${kpi.color}-600`,
                innerHTML: `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">${kpi.icon}</svg>`
            });

            header.appendChild(textWrap);
            header.appendChild(iconWrap);
            card.appendChild(header);

            card.appendChild(this.utils.createElement('p', {
                className: `text-xs mt-4 ${kpi.alert ? 'text-red-600 font-medium' : 'text-gray-400'}`,
                textContent: kpi.subtitle
            }));

            this.elements.kpiGrid.appendChild(card);
        });
    }

    renderHealth() {
        this.utils.clearChildren(this.elements.healthSection);
        const health = this.state.data.systemHealth;

        const wrapper = this.utils.createElement('div', {
            className: 'bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden'
        });

        const header = this.utils.createElement('div', {
            className: 'px-6 py-4 border-b border-gray-200 flex justify-between items-center bg-gray-50'
        });

        header.appendChild(this.utils.createElement('h2', {
            className: 'text-lg font-bold text-gray-900',
            textContent: 'System Diagnostics'
        }));

        const globalStatusBadge = this.utils.createElement('span', {
            className: `px-3 py-1 text-xs font-bold rounded-full ${
                health.global_status === 'OPERATIONAL' ? 'bg-green-100 text-green-800' :
                health.global_status === 'DEGRADED' ? 'bg-orange-100 text-orange-800' : 'bg-red-100 text-red-800'
            }`,
            textContent: health.global_status
        });
        header.appendChild(globalStatusBadge);
        wrapper.appendChild(header);

        const list = this.utils.createElement('ul', { className: 'divide-y divide-gray-100' });

        if (health.components && Array.isArray(health.components)) {
            health.components.forEach(comp => {
                const li = this.utils.createElement('li', { className: 'p-6 hover:bg-gray-50 transition-colors' });

                const topRow = this.utils.createElement('div', { className: 'flex justify-between items-center mb-2' });

                const nameWrap = this.utils.createElement('div', { className: 'flex items-center gap-3' });
                const statusDot = this.utils.createElement('div', {
                    className: `w-3 h-3 rounded-full ${
                        comp.status === 'OPERATIONAL' ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]' :
                        comp.status === 'DEGRADED' ? 'bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.6)]' : 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]'
                    }`
                });
                nameWrap.appendChild(statusDot);
                nameWrap.appendChild(this.utils.createElement('span', { className: 'font-semibold text-gray-900', textContent: comp.name }));

                topRow.appendChild(nameWrap);

                const metricsWrap = this.utils.createElement('div', { className: 'flex items-center gap-4 text-sm' });
                metricsWrap.appendChild(this.utils.createElement('span', {
                    className: 'text-gray-500 font-mono bg-gray-100 px-2 py-1 rounded',
                    textContent: `${comp.latency_ms} ms`
                }));
                topRow.appendChild(metricsWrap);

                li.appendChild(topRow);

                li.appendChild(this.utils.createElement('p', {
                    className: `text-sm ${comp.status === 'OPERATIONAL' ? 'text-gray-600' : 'text-red-600 font-medium'}`,
                    textContent: comp.message
                }));

                if (comp.metadata && Object.keys(comp.metadata).length > 0) {
                    const metaDiv = this.utils.createElement('div', { className: 'mt-3 flex flex-wrap gap-2' });
                    for (const [k, v] of Object.entries(comp.metadata)) {
                        if (typeof v !== 'object') {
                            metaDiv.appendChild(this.utils.createElement('span', {
                                className: 'text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded border border-blue-100',
                                textContent: `${k}: ${v}`
                            }));
                        }
                    }
                    if (metaDiv.children.length > 0) li.appendChild(metaDiv);
                }

                list.appendChild(li);
            });
        }

        wrapper.appendChild(list);

        if (health.metrics) {
            const footer = this.utils.createElement('div', {
                className: 'px-6 py-4 bg-gray-900 text-gray-300 text-xs grid grid-cols-2 sm:grid-cols-4 gap-4'
            });

            const addMetric = (label, value) => {
                const d = this.utils.createElement('div');
                d.appendChild(this.utils.createElement('span', { className: 'block text-gray-500 mb-1', textContent: label }));
                d.appendChild(this.utils.createElement('span', { className: 'font-mono text-white', textContent: value }));
                footer.appendChild(d);
            };

            addMetric('Uptime', this.formatters.formatDuration(health.metrics.uptime_seconds * 1000));
            addMetric('Memory', `${health.metrics.memory_usage_mb} MB`);
            addMetric('CPU', `${health.metrics.cpu_percent_simulated}%`);
            addMetric('Threads', health.metrics.active_threads);

            wrapper.appendChild(footer);
        }

        this.elements.healthSection.appendChild(wrapper);
    }

    renderAlerts() {
        this.utils.clearChildren(this.elements.alertsSection);
        const alerts = this.state.data.criticalAlerts || [];

        const wrapper = this.utils.createElement('div', {
            className: 'bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden h-full flex flex-col'
        });

        const header = this.utils.createElement('div', {
            className: 'px-6 py-4 border-b border-gray-200 bg-gray-50'
        });
        header.appendChild(this.utils.createElement('h2', {
            className: 'text-lg font-bold text-gray-900 flex items-center gap-2',
            innerHTML: '<svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path></svg> Action Required'
        }));
        wrapper.appendChild(header);

        const list = this.utils.createElement('div', { className: 'p-4 flex-1 overflow-y-auto space-y-3' });

        if (alerts.length === 0) {
            list.innerHTML = `
                <div class="h-full flex flex-col items-center justify-center text-gray-400 py-12">
                    <svg class="w-12 h-12 mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    <p class="text-sm">No critical alerts detected.</p>
                </div>
            `;
        } else {
            alerts.forEach(alert => {
                const item = this.utils.createElement('div', {
                    className: `p-4 rounded-lg border-l-4 ${alert.severity === 'CRITICAL' ? 'bg-red-50 border-red-500' : 'bg-orange-50 border-orange-500'}`
                });
                item.appendChild(this.utils.createElement('span', {
                    className: `text-[10px] font-bold uppercase tracking-wider ${alert.severity === 'CRITICAL' ? 'text-red-600' : 'text-orange-600'}`,
                    textContent: `${alert.type} • ${alert.source}`
                }));
                item.appendChild(this.utils.createElement('p', {
                    className: 'text-sm text-gray-900 mt-1 font-medium',
                    textContent: alert.message
                }));
                list.appendChild(item);
            });
        }

        wrapper.appendChild(list);
        this.elements.alertsSection.appendChild(wrapper);
    }

    renderCharts() {
        this.utils.clearChildren(this.elements.chartsSection);

        const riskChartCard = this.buildCustomBarChart(
            'Risk Distribution', 
            this.state.data.humanInTheLoop?.pending_risk_distribution || {}
        );

        const eventChartCard = this.buildCustomBarChart(
            'AI Event Breakdown', 
            this.state.data.aiOrchestration?.events_breakdown || {}
        );

        this.elements.chartsSection.appendChild(riskChartCard);
        this.elements.chartsSection.appendChild(eventChartCard);
    }

    buildCustomBarChart(title, dataObj) {
        const wrapper = this.utils.createElement('div', {
            className: 'bg-white rounded-xl shadow-sm border border-gray-200 p-6'
        });

        wrapper.appendChild(this.utils.createElement('h2', {
            className: 'text-lg font-bold text-gray-900 mb-6',
            textContent: title
        }));

        const entries = Object.entries(dataObj);
        if (entries.length === 0) {
            wrapper.appendChild(this.utils.createElement('p', {
                className: 'text-sm text-gray-500 text-center py-8',
                textContent: 'No data available for this metric.'
            }));
            return wrapper;
        }

        const maxValue = Math.max(...entries.map(e => e[1])) || 1;
        const chartContainer = this.utils.createElement('div', { className: 'space-y-4' });

        entries.forEach(([key, value]) => {
            const row = this.utils.createElement('div');

            const labelRow = this.utils.createElement('div', { className: 'flex justify-between text-sm mb-1' });
            labelRow.appendChild(this.utils.createElement('span', { 
                className: 'font-medium text-gray-700', 
                textContent: key.replace(/_/g, ' ') 
            }));
            labelRow.appendChild(this.utils.createElement('span', { 
                className: 'text-gray-900 font-bold', 
                textContent: value.toLocaleString() 
            }));
            row.appendChild(labelRow);

            const barBg = this.utils.createElement('div', { className: 'w-full bg-gray-100 rounded-full h-2.5 overflow-hidden' });
            const percentage = (value / maxValue) * 100;

            let colorClass = 'bg-blue-500';
            if (key.includes('CRITICAL') || key.includes('REJECTED')) colorClass = 'bg-red-500';
            else if (key.includes('HIGH') || key.includes('FLAG')) colorClass = 'bg-orange-500';
            else if (key.includes('LOW') || key.includes('CLEARED') || key.includes('APPROVED')) colorClass = 'bg-green-500';

            const barFill = this.utils.createElement('div', {
                className: `h-full ${colorClass} rounded-full transition-all duration-1000 ease-out`,
                style: { width: '0%' }
            });

            setTimeout(() => { barFill.style.width = `${percentage}%`; }, 100);

            barBg.appendChild(barFill);
            row.appendChild(barBg);
            chartContainer.appendChild(row);
        });

        wrapper.appendChild(chartContainer);
        return wrapper;
    }
}