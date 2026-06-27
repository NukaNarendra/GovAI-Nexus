class AuditController {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        if (!this.container) return;

        this.api = window.auditApi;
        this.store = window.authStore;
        this.utils = window.domUtils;
        this.formatters = window.formatters;

        this.state = {
            filters: { page: 1, size: 50 },
            isVerifying: false,
            isExporting: false
        };

        this.elements = {
            mainWrapper: null,
            tableContainer: null,
            filterForm: null,
            verifyBtn: null,
            exportBtn: null
        };

        this.dataTable = null;
        this.init();
    }

    async init() {
        this.store.enforcePermission('VIEW_AUDIT');
        this.buildLayout();
        await this.loadTableData();
    }

    buildLayout() {
        this.utils.clearChildren(this.container);

        this.elements.mainWrapper = this.utils.createElement('div', {
            className: 'p-4 sm:p-6 lg:p-8 max-w-[1600px] mx-auto space-y-6'
        });

        const header = this.utils.createElement('div', {
            className: 'flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-xl shadow-sm border border-gray-200'
        });

        const titleWrapper = this.utils.createElement('div', { className: 'flex items-start gap-4' });
        titleWrapper.innerHTML = `
            <div class="w-12 h-12 rounded-lg bg-gray-900 flex items-center justify-center text-white flex-shrink-0 shadow-lg">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
            </div>
            <div>
                <h1 class="text-2xl font-black text-gray-900 tracking-tight">WORM Immutable Ledger</h1>
                <p class="text-sm text-gray-500 font-medium mt-1">Cryptographically sealed enterprise compliance and audit records</p>
            </div>
        `;

        const controlsWrapper = this.utils.createElement('div', { className: 'flex flex-wrap items-center gap-3 w-full md:w-auto' });

        this.elements.verifyBtn = this.utils.createElement('button', {
            className: 'flex-1 md:flex-none flex items-center justify-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-lg shadow hover:bg-gray-800 transition-colors font-bold text-sm focus:ring-2 focus:ring-offset-2 focus:ring-gray-900',
            innerHTML: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg> Verify Chain',
            onclick: () => this.handleChainVerification()
        });

        this.elements.exportBtn = this.utils.createElement('button', {
            className: 'flex-1 md:flex-none flex items-center justify-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors font-bold text-sm focus:ring-2 focus:ring-offset-2 focus:ring-blue-500',
            innerHTML: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg> Export Certified',
            onclick: () => this.handleExportLedger()
        });

        if (this.store.hasPermission('EXPORT_AUDIT')) {
            controlsWrapper.appendChild(this.elements.exportBtn);
        }
        controlsWrapper.appendChild(this.elements.verifyBtn);

        header.appendChild(titleWrapper);
        header.appendChild(controlsWrapper);

        this.buildFilterBar();

        this.elements.tableContainer = this.utils.createElement('div', {
            id: 'audit-table-mount',
            className: 'transition-all duration-300 min-h-[600px]'
        });

        this.elements.mainWrapper.appendChild(header);
        this.elements.mainWrapper.appendChild(this.elements.filterForm);
        this.elements.mainWrapper.appendChild(this.elements.tableContainer);
        this.container.appendChild(this.elements.mainWrapper);
    }

    buildFilterBar() {
        this.elements.filterForm = this.utils.createElement('form', {
            className: 'bg-white p-4 rounded-xl shadow-sm border border-gray-200 flex flex-wrap gap-4 items-end'
        });

        const buildSelect = (name, label, options) => {
            const wrap = this.utils.createElement('div', { className: 'flex-1 min-w-[150px]' });
            wrap.innerHTML = `<label class="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">${label}</label>`;
            const select = this.utils.createElement('select', {
                name: name,
                className: 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-gray-900 focus:border-gray-900 text-sm bg-gray-50'
            });
            select.innerHTML = `<option value="">All</option>` + options.map(o => `<option value="${o.value}">${o.label}</option>`).join('');
            wrap.appendChild(select);
            return wrap;
        };

        const eventOptions = Object.keys(this.api.eventTypes).map(k => ({ value: k, label: k.replace(/_/g, ' ') }));
        const severityOptions = Object.keys(this.api.severities).map(k => ({ value: k, label: k }));

        this.elements.filterForm.appendChild(buildSelect('event_type', 'Event Type', eventOptions));
        this.elements.filterForm.appendChild(buildSelect('severity', 'Severity', severityOptions));

        const submitBtn = this.utils.createElement('button', {
            type: 'submit',
            className: 'px-4 py-2 bg-blue-600 text-white rounded-md shadow-sm hover:bg-blue-700 transition-colors font-bold text-sm h-[38px]',
            textContent: 'Apply Filters'
        });

        this.elements.filterForm.appendChild(submitBtn);

        this.elements.filterForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const values = this.utils.getFormValues(e.target);
            this.state.filters = { page: 1, size: 50 };
            if (values.event_type) this.state.filters.event_type = values.event_type;
            if (values.severity) this.state.filters.severity = values.severity;
            this.loadTableData();
        });
    }

    async loadTableData() {
        if (this.dataTable) {
            this.dataTable.setLoading(true);
        } else {
            this.elements.tableContainer.innerHTML = '<div class="flex justify-center p-12"><div class="animate-spin w-8 h-8 border-4 border-gray-900 border-t-transparent rounded-full"></div></div>';
        }

        try {
            const response = await this.api.getLogs(this.state.filters);
            this.renderTable(response.items || []);
        } catch (error) {
            if (window.toastManager) window.toastManager.error('Failed to fetch audit logs');
            this.elements.tableContainer.innerHTML = `<div class="p-6 text-red-600 bg-red-50 rounded-lg border border-red-200 font-medium">${this.utils.sanitizeHTML(error.message)}</div>`;
        }
    }

    renderTable(data) {
        if (!this.dataTable) {
            this.elements.tableContainer.innerHTML = '';

            const columns = [
                {
                    key: 'timestamp',
                    label: 'Timestamp (UTC)',
                    render: (val) => `<span class="font-mono text-xs text-gray-600">${val.replace('T', ' ').substring(0, 19)}</span>`
                },
                {
                    key: 'event_type',
                    label: 'Event Type',
                    render: (val) => `<span class="font-bold text-xs text-gray-800 tracking-tight">${val.replace(/_/g, ' ')}</span>`
                },
                {
                    key: 'severity',
                    label: 'Severity',
                    align: 'center',
                    render: (val) => {
                        const colors = {
                            'CRITICAL': 'bg-red-600 text-white animate-pulse',
                            'HIGH': 'bg-orange-500 text-white',
                            'MEDIUM': 'bg-yellow-400 text-gray-900',
                            'LOW': 'bg-blue-100 text-blue-800',
                            'INFO': 'bg-gray-100 text-gray-600'
                        };
                        return `<span class="px-2 py-0.5 text-[10px] font-black rounded ${colors[val] || colors.INFO}">${val}</span>`;
                    }
                },
                {
                    key: 'actor_type',
                    label: 'Actor',
                    render: (val, row) => {
                        const icon = val === 'AI_AGENT' 
                            ? '<svg class="w-3 h-3 inline mr-1 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>'
                            : '<svg class="w-3 h-3 inline mr-1 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>';
                        return `<div>${icon}<span class="text-xs font-bold text-gray-700">${val.replace('_', ' ')}</span></div><div class="text-[10px] text-gray-400 font-mono mt-0.5 truncate max-w-[120px] hover:max-w-none" title="${row.actor_id}">${row.actor_id}</div>`;
                    }
                },
                {
                    key: 'cryptographic_hash',
                    label: 'SHA-256 Hash',
                    render: (val, row) => {
                        if (row.is_tampered) {
                            return `<span class="text-xs font-mono text-red-600 font-bold bg-red-50 px-1 rounded border border-red-200">TAMPERED DATA</span>`;
                        }
                        return `<span class="text-[10px] font-mono text-gray-400 bg-gray-50 px-1 rounded border border-gray-200" title="${val}">${val.substring(0, 12)}...</span>`;
                    }
                }
            ];

            this.dataTable = new window.DataTable('#audit-table-mount', {
                columns: columns,
                data: data,
                pageSize: 50,
                searchable: true,
                exportable: false,
                striped: false,
                customRowClass: (row) => row.is_tampered ? 'bg-red-50 hover:bg-red-100 ' : 'hover:bg-gray-50 border-b border-gray-100 ',
                emptyMessage: 'No audit logs found matching criteria.',
                onRowClick: (row) => this.openLogDetail(row.id)
            });
        } else {
            this.dataTable.updateData(data);
            this.dataTable.setLoading(false);
        }
    }

    async openLogDetail(logId) {
        if (window.toastManager) window.toastManager.show({ type: 'loading', message: 'Fetching secure record...', duration: 500, id: 'audit_loader' });

        try {
            const data = await this.api.getLogById(logId);
            this.buildDetailModal(data);
        } catch (err) {
            if (window.toastManager) window.toastManager.error('Failed to load secure record');
        }
    }

    buildDetailModal(log) {
        const content = this.utils.createElement('div', { className: 'space-y-6' });

        const header = this.utils.createElement('div', { className: `p-4 rounded-lg border ${log.is_tampered ? 'bg-red-50 border-red-500' : 'bg-gray-900 border-gray-800'} flex items-start gap-4` });

        header.innerHTML = `
            <div class="flex-shrink-0 pt-1 ${log.is_tampered ? 'text-red-500' : 'text-green-400'}">
                <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    ${log.is_tampered 
                        ? '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>' 
                        : '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>'
                    }
                </svg>
            </div>
            <div class="flex-1">
                <h3 class="text-lg font-black ${log.is_tampered ? 'text-red-700' : 'text-white'} tracking-tight">${log.event_type.replace(/_/g, ' ')}</h3>
                <p class="${log.is_tampered ? 'text-red-600' : 'text-gray-400'} text-sm mt-1">${this.utils.sanitizeHTML(log.action_details)}</p>
                <div class="mt-4 grid grid-cols-2 gap-4 text-xs">
                    <div><span class="${log.is_tampered ? 'text-red-500' : 'text-gray-500'} font-bold">ACTOR:</span> <span class="font-mono ${log.is_tampered ? 'text-red-800' : 'text-gray-300'} break-all">${log.actor_id}</span></div>
                    <div><span class="${log.is_tampered ? 'text-red-500' : 'text-gray-500'} font-bold">RESOURCE:</span> <span class="font-mono ${log.is_tampered ? 'text-red-800' : 'text-gray-300'} break-all">${log.resource_id || 'N/A'}</span></div>
                </div>
            </div>
        `;
        content.appendChild(header);

        const cryptoBox = this.utils.createElement('div', { className: 'bg-gray-50 p-4 rounded-lg border border-gray-200' });
        cryptoBox.innerHTML = `
            <h4 class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Cryptographic Chain Data</h4>
            <div class="space-y-2 font-mono text-[10px]">
                <div class="flex"><span class="text-gray-400 w-24">RECORD ID:</span><span class="text-gray-900">${log.id}</span></div>
                <div class="flex"><span class="text-gray-400 w-24">THIS HASH:</span><span class="text-blue-600 break-all">${log.cryptographic_hash}</span></div>
            </div>
        `;
        content.appendChild(cryptoBox);

        const modal = new window.Modal({
            title: `Audit Record Inspection`,
            content: content,
            size: 'lg',
            buttons: [
                { text: 'Close', type: 'default', onClick: (m) => m.close() }
            ]
        });

        modal.open();
    }

    async handleChainVerification() {
        if (this.state.isVerifying) return;
        this.state.isVerifying = true;

        const btnIcon = this.elements.verifyBtn.querySelector('svg');
        if (btnIcon) btnIcon.classList.add('animate-spin');

        let toast;
        if (window.toastManager) {
            toast = window.toastManager.show({ type: 'loading', message: 'Verifying mathematical proofs...', duration: 0, dismissible: false });
        }

        try {
            const result = await this.api.verifyChainIntegrity(7);

            if (toast) toast.dismiss();

            if (result.status === 'valid') {
                window.Modal.alert('Verification Successful', 
                    `<div class="text-green-700 font-medium">The cryptographic chain is intact.</div>
                     <div class="text-sm mt-2 text-gray-600">Scanned and verified ${result.scanned_records} sequential records using SHA-256 HMAC proofs. No tampering detected.</div>`
                );
            } else {
                window.Modal.alert('CRITICAL: Verification Failed', 
                    `<div class="text-red-700 font-bold">WORM Storage Compromised.</div>
                     <div class="text-sm mt-2 text-gray-800">Mathematical proofs failed for ${result.corrupted_ids.length} records. The audit chain is broken. Initiate incident response immediately.</div>`,
                    { isDanger: true }
                );
            }
        } catch (error) {
            if (toast) toast.dismiss();
            if (window.toastManager) window.toastManager.error('Chain verification process failed to execute');
        } finally {
            this.state.isVerifying = false;
            if (btnIcon) btnIcon.classList.remove('animate-spin');
        }
    }

    async handleExportLedger() {
        if (this.state.isExporting) return;

        const now = new Date();
        const lastWeek = new Date(now.getTime() - (7 * 24 * 60 * 60 * 1000));

        this.state.isExporting = true;
        let toast;
        if (window.toastManager) {
            toast = window.toastManager.show({ type: 'loading', message: 'Generating certified ledger export...', duration: 0, dismissible: false });
        }

        try {
            await this.api.exportLedger(lastWeek.toISOString(), now.toISOString(), 'csv');
            if (toast) toast.dismiss();
            if (window.toastManager) window.toastManager.success('Ledger exported successfully');
        } catch (error) {
            if (toast) toast.dismiss();
            window.Modal.alert('Export Failed', 
                error.status === 409 
                ? 'Cannot export certified ledger because cryptographic verification failed. The chain must be clean to generate a certified export.'
                : 'An unexpected error occurred during export generation.',
                { isDanger: error.status === 409 }
            );
        } finally {
            this.state.isExporting = false;
        }
    }
}