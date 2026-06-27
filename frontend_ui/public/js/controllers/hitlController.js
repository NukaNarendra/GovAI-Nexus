class HitlController {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        if (!this.container) return;

        this.api = window.hitlApi;
        this.store = window.authStore;
        this.utils = window.domUtils;
        this.formatters = window.formatters;

        this.state = {
            currentTab: 'PENDING',
            selectedTaskId: null,
            detailData: null,
            isProcessing: false
        };

        this.elements = {
            mainWrapper: null,
            tableContainer: null,
            tabsContainer: null,
            detailPanel: null
        };

        this.dataTable = null;

        // FIX: Expose this instance globally so dynamically generated table buttons can call it directly
        window.__hitlController = this;

        this.init();
    }

    async init() {
        this.store.enforcePermission('VIEW_HITL');
        this.buildLayout();
        await this.loadTableData();
    }

    buildLayout() {
        this.utils.clearChildren(this.container);

        this.elements.mainWrapper = this.utils.createElement('div', {
            className: 'p-4 sm:p-6 lg:p-8 max-w-[1600px] mx-auto h-full flex flex-col'
        });

        const header = this.utils.createElement('div', {
            className: 'flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6 shrink-0'
        });

        const titleWrapper = this.utils.createElement('div');
        titleWrapper.appendChild(this.utils.createElement('h1', {
            className: 'text-2xl font-bold text-gray-900',
            textContent: 'Human-In-The-Loop Review'
        }));
        titleWrapper.appendChild(this.utils.createElement('p', {
            className: 'text-sm text-gray-500 mt-1',
            textContent: 'Review and resolve escalated AI governance decisions'
        }));

        header.appendChild(titleWrapper);

        this.elements.tabsContainer = this.utils.createElement('div', {
            className: 'flex bg-gray-100 p-1 rounded-lg shrink-0'
        });

        this.buildTabs();
        header.appendChild(this.elements.tabsContainer);

        this.elements.tableContainer = this.utils.createElement('div', {
            className: 'flex-1 min-h-[500px] relative transition-all duration-300',
            id: 'hitl-table-mount'
        });

        // FIX: Removed the buggy event delegation listener from here entirely.

        this.elements.mainWrapper.appendChild(header);
        this.elements.mainWrapper.appendChild(this.elements.tableContainer);
        this.container.appendChild(this.elements.mainWrapper);
    }

    buildTabs() {
        this.utils.clearChildren(this.elements.tabsContainer);

        const tabs = [
            { id: 'PENDING', label: 'Global Queue' },
            { id: 'ASSIGNED', label: 'My Assignments' }
        ];

        tabs.forEach(tab => {
            const btn = this.utils.createElement('button', {
                className: `px-4 py-2 text-sm font-medium rounded-md transition-all ${
                    this.state.currentTab === tab.id 
                    ? 'bg-white text-blue-600 shadow-sm ring-1 ring-black ring-opacity-5' 
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200'
                }`,
                textContent: tab.label,
                onclick: () => {
                    this.state.currentTab = tab.id;
                    this.buildTabs();
                    this.loadTableData();
                }
            });
            this.elements.tabsContainer.appendChild(btn);
        });
    }

    async loadTableData() {
        if (this.dataTable) {
            this.dataTable.setLoading(true);
        } else {
            this.elements.tableContainer.innerHTML = '<div class="flex justify-center p-12"><div class="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full"></div></div>';
        }

        try {
            let response;
            if (this.state.currentTab === 'PENDING') {
                response = await this.api.getPendingTasks({ size: 100 });
            } else {
                response = await this.api.getMyAssignments(false, 1, 100);
            }

            this.renderTable(response.items || []);
        } catch (error) {
            if (window.toastManager) window.toastManager.error('Failed to fetch queue data');
            this.elements.tableContainer.innerHTML = `<div class="p-6 text-red-600 bg-red-50 rounded-lg border border-red-200">${this.utils.sanitizeHTML(error.message)}</div>`;
        }
    }

    renderTable(data) {
        if (!this.dataTable) {
            this.elements.tableContainer.innerHTML = '';

            const columns = [
                {
                    key: 'resource_id',
                    label: 'Reference ID',
                    render: (val, row) => `<div class="font-mono text-xs text-blue-600 font-medium">${val}</div><div class="text-xs text-gray-400 mt-1">${row.resource_type.replace(/_/g, ' ')}</div>`
                },
                {
                    key: 'risk_category',
                    label: 'Risk Vector',
                    render: (val) => {
                        const fmt = this.formatters.formatStatusBadge(val);
                        return `<span class="px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider rounded-full bg-orange-100 text-orange-800 border border-orange-200">${val.replace(/_/g, ' ')}</span>`;
                    }
                },
                {
                    key: 'priority',
                    label: 'Priority',
                    align: 'center',
                    render: (val) => {
                        const map = {1: 'LOW', 2: 'MED', 3: 'HIGH', 4: 'CRIT'};
                        const colors = {1: 'bg-gray-100 text-gray-600', 2: 'bg-blue-100 text-blue-700', 3: 'bg-orange-100 text-orange-700', 4: 'bg-red-100 text-red-700 animate-pulse'};
                        return `<span class="px-2 py-1 text-[10px] font-bold rounded ${colors[val]}">${map[val]}</span>`;
                    }
                },
                {
                    key: 'ai_confidence_score',
                    label: 'AI Confidence',
                    align: 'center',
                    render: (val) => {
                        const color = val < 0.85 ? 'text-red-600' : 'text-green-600';
                        return `<span class="font-mono font-medium ${color}">${(val * 100).toFixed(1)}%</span>`;
                    }
                },
                {
                    key: 'created_at',
                    label: 'Time in Queue',
                    render: (val) => `<span class="text-xs font-medium text-gray-600">${this.formatters.formatRelativeTime(val)}</span>`
                },
                {
                    key: 'actions',
                    label: '',
                    align: 'right',
                    sortable: false,
                    render: (val, row) => {
                        // FIX: Use inline onclick bound to our global instance!
                        if (this.state.currentTab === 'PENDING') {
                            return `<button type="button" class="px-3 py-1 bg-blue-50 text-blue-700 hover:bg-blue-100 hover:text-blue-800 text-xs font-bold rounded transition-colors" onclick="window.__hitlController.handleClaimTask('${row.id}')">CLAIM TASK</button>`;
                        }
                        return `<button type="button" class="px-3 py-1 bg-green-50 text-green-700 hover:bg-green-100 text-xs font-bold rounded transition-colors" onclick="window.__hitlController.openTaskDetail('${row.id}')">REVIEW</button>`;
                    }
                }
            ];

            this.dataTable = new window.DataTable('#hitl-table-mount', {
                columns: columns,
                data: data,
                pageSize: 25,
                searchable: true,
                exportable: false,
                emptyMessage: 'Queue is currently empty. All clear!'
            });
        } else {
            this.dataTable.updateData(data);
            this.dataTable.setLoading(false);
        }
    }

    async handleClaimTask(taskId) {
        if (!this.store.hasPermission('APPROVE_HITL')) {
            if (window.toastManager) window.toastManager.error('Insufficient permissions to claim tasks');
            return;
        }

        try {
            if (window.toastManager) window.toastManager.show({ type: 'loading', message: 'Claiming task...', duration: 500, id: 'claim_loader' });

            await this.api.claimTask(taskId);

            if (window.toastManager) window.toastManager.success('Task claimed successfully');

            this.state.currentTab = 'ASSIGNED';
            this.buildTabs();
            await this.loadTableData();
            this.openTaskDetail(taskId);
        } catch (err) {
            if (window.toastManager) window.toastManager.error(err.message || 'Failed to claim task');
            this.loadTableData(); 
        }
    }

    async openTaskDetail(taskId) {
        if (window.toastManager) window.toastManager.show({ type: 'loading', message: 'Loading task details...', duration: 500, id: 'loader' });

        try {
            const data = await this.api.getTaskDetails(taskId);
            this.state.selectedTaskId = taskId;
            this.state.detailData = data;
            this.buildDetailModal(data);
        } catch (err) {
            if (window.toastManager) window.toastManager.error('Failed to load task details');
        }
    }

    buildDetailModal(task) {
        const payloadStr = JSON.stringify(task.transaction_context, null, 2);
        let featureAttrs = null;
        if (task.compliance_flags && task.compliance_flags.feature_attribution) {
            featureAttrs = task.compliance_flags.feature_attribution;
            delete task.compliance_flags.feature_attribution;
        }

        const rulesStr = JSON.stringify(task.compliance_flags, null, 2);

        const content = this.utils.createElement('div', { className: 'space-y-6' });

        const headerRow = this.utils.createElement('div', { className: 'flex justify-between items-start bg-gray-50 p-4 rounded-lg border border-gray-200' });
        headerRow.innerHTML = `
            <div>
                <p class="text-xs text-gray-500 font-bold uppercase tracking-wider mb-1">Resource Context</p>
                <p class="text-lg font-mono text-gray-900">${this.utils.sanitizeHTML(task.resource_id)}</p>
                <p class="text-sm text-blue-600 font-medium">${this.utils.sanitizeHTML(task.resource_type)}</p>
            </div>
            <div class="text-right">
                <p class="text-xs text-gray-500 font-bold uppercase tracking-wider mb-1">AI Confidence</p>
                <p class="text-2xl font-black ${task.ai_confidence_score < 0.85 ? 'text-red-600' : 'text-green-600'}">${(task.ai_confidence_score * 100).toFixed(1)}%</p>
            </div>
        `;
        content.appendChild(headerRow);

        const aiReasoningBox = this.utils.createElement('div', { className: 'bg-orange-50 border-l-4 border-orange-500 p-4 rounded-r-lg' });
        aiReasoningBox.innerHTML = `
            <h4 class="text-sm font-bold text-orange-900 mb-2 flex items-center gap-2">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                AI Reasoning & Escalation Cause
            </h4>
            <p class="text-sm text-orange-800 leading-relaxed">${this.utils.sanitizeHTML(task.ai_reasoning)}</p>
        `;
        content.appendChild(aiReasoningBox);

        const grid = this.utils.createElement('div', { className: 'grid grid-cols-1 md:grid-cols-2 gap-4' });

        const buildCodeBox = (title, jsonStr) => {
            const box = this.utils.createElement('div', { className: 'border border-gray-200 rounded-lg overflow-hidden flex flex-col' });
            box.innerHTML = `
                <div class="bg-gray-100 px-3 py-2 border-b border-gray-200 text-xs font-bold text-gray-700 uppercase tracking-wider">${title}</div>
                <div class="p-0 flex-1 bg-gray-900">
                    <pre class="text-[11px] text-green-400 font-mono p-4 overflow-x-auto m-0 h-48 custom-scrollbar"><code>${this.utils.sanitizeHTML(jsonStr)}</code></pre>
                </div>
            `;
            return box;
        };

        grid.appendChild(buildCodeBox('Raw Context Payload', payloadStr));
        grid.appendChild(buildCodeBox('Governance Engine Flags', rulesStr));
        
        if (featureAttrs) {
            const attrBox = this.utils.createElement('div', { className: 'bg-white border border-gray-200 p-4 rounded-lg mt-4' });
            let barsHtml = '';
            for (const [feat, weight] of Object.entries(featureAttrs)) {
                barsHtml += `
                    <div class="mb-3 last:mb-0">
                        <div class="flex justify-between text-xs mb-1">
                            <span class="text-gray-700 font-bold uppercase tracking-wider">${feat.replace(/_/g, ' ')}</span>
                            <span class="text-gray-900 font-black">${weight}%</span>
                        </div>
                        <div class="w-full bg-gray-200 rounded-full h-2">
                            <div class="bg-blue-600 h-2 rounded-full" style="width: ${weight}%"></div>
                        </div>
                    </div>
                `;
            }
            attrBox.innerHTML = `
                <h4 class="text-sm font-black text-gray-900 mb-4 flex items-center gap-2">
                    <svg class="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                    Deterministic Risk Attribution (Explainability Engine)
                </h4>
                ${barsHtml}
            `;
            content.appendChild(attrBox);
        }

        content.appendChild(grid);

        const formArea = this.utils.createElement('div', { className: 'mt-6 pt-6 border-t border-gray-200' });
        formArea.innerHTML = `
            <label class="block text-sm font-bold text-gray-900 mb-2">Resolution Audit Notes <span class="text-red-500">*</span></label>
            <textarea id="resolution_notes" rows="4" class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm transition-shadow resize-none" placeholder="Provide detailed reasoning for approval or rejection. These notes will be written to the WORM ledger and used to retrain the AI models..."></textarea>
            <div class="mt-3 flex items-center gap-2">
                <input type="checkbox" id="gen_feedback" checked class="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500">
                <label for="gen_feedback" class="text-sm text-gray-700">Generate AI Feedback Loop (Improves future autonomous decisions)</label>
            </div>
        `;
        content.appendChild(formArea);

        const modal = new window.Modal({
            title: `Review Task: ${task.id.split('-')[0]}`,
            content: content,
            size: 'xl',
            closeOnBackdrop: false,
            buttons: [
                { text: 'Cancel', type: 'default', onClick: (m) => m.close() },
                { text: 'Reject & Block', type: 'danger', onClick: (m) => this.submitResolution(m, 'REJECTED') },
                { text: 'Approve & Execute', type: 'primary', onClick: (m) => this.submitResolution(m, 'APPROVED') }
            ]
        });

        modal.open();
    }

    async submitResolution(modalInstance, status) {
        if (this.state.isProcessing) return;

        const notesInput = modalInstance.elements.body.querySelector('#resolution_notes');
        const feedbackCheck = modalInstance.elements.body.querySelector('#gen_feedback');

        const notes = notesInput.value.trim();
        if (notes.length < 10) {
            notesInput.classList.add('border-red-500', 'ring-1', 'ring-red-500');
            if (window.toastManager) window.toastManager.warning('Please provide detailed audit notes (min 10 chars)');
            return;
        }

        this.state.isProcessing = true;
        const actionTaken = status === 'APPROVED' ? 'MANUAL_APPROVAL_GRANTED' : 'MANUAL_REJECTION_ENFORCED';

        const buttons = modalInstance.elements.footer.querySelectorAll('button');
        buttons.forEach(b => b.disabled = true);

        if (window.toastManager) window.toastManager.show({ type: 'loading', message: 'Sealing cryptographic audit log...', duration: 0, id: 'resolve_loader' });

        let hasTimeout = false;
        try {
            await this.api.resolveTask(
                this.state.selectedTaskId,
                status,
                notes,
                actionTaken,
                feedbackCheck.checked
            );

            if (window.toastManager) {
                window.toastManager.dismiss('resolve_loader');
                window.toastManager.success(`Task successfully ${status.toLowerCase()}`);
            }

            modalInstance.close();
        } catch (err) {
            if (err && err.message && err.message.includes('timed out')) {
                hasTimeout = true;
            }
            if (window.toastManager) {
                window.toastManager.dismiss('resolve_loader');
                window.toastManager.error(err.message || 'Failed to resolve task');
            }
            buttons.forEach(b => b.disabled = false);
        } finally {
            this.state.isProcessing = false;
            if (hasTimeout) {
                modalInstance.close();
            }
            this.loadTableData();
        }
    }
}