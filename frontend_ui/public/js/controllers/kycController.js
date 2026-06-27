class KycController {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        if (!this.container) return;
        this.api = window.kycApi;
        this.utils = window.domUtils;
        this.init();
    }

    async init() {
        this.buildLayout();
        await this.loadData();
    }

    buildLayout() {
        this.utils.clearChildren(this.container);
        this.elements = {};
        this.elements.mainWrapper = this.utils.createElement('div', {
            className: 'p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto space-y-6'
        });
        
        const header = this.utils.createElement('div', {
            className: 'flex justify-between items-center bg-white p-6 rounded-xl shadow-sm border border-gray-200'
        });
        header.innerHTML = `
            <div>
                <h1 class="text-2xl font-black text-gray-900 tracking-tight">KYC Profiles Directory</h1>
                <p class="text-sm text-gray-500 font-medium mt-1">Enterprise client identity verification and risk assessment</p>
            </div>
            <button class="px-4 py-2 bg-blue-600 text-white rounded-md shadow-sm hover:bg-blue-700 font-bold text-sm" onclick="location.reload()">Refresh Data</button>
        `;

        this.elements.tableContainer = this.utils.createElement('div', { className: 'bg-white rounded-xl shadow-sm border border-gray-200 min-h-[500px]' });
        
        this.elements.mainWrapper.appendChild(header);
        this.elements.mainWrapper.appendChild(this.elements.tableContainer);
        this.container.appendChild(this.elements.mainWrapper);
    }

    async loadData() {
        this.elements.tableContainer.innerHTML = '<div class="p-12 flex justify-center"><div class="animate-spin w-8 h-8 border-4 border-gray-900 border-t-transparent rounded-full"></div></div>';
        try {
            const data = await this.api.getProfiles();
            this.renderTable(data.items || []);
        } catch (error) {
            this.elements.tableContainer.innerHTML = `<div class="p-6 text-red-600 bg-red-50">${error.message}</div>`;
        }
    }

    renderTable(data) {
        this.elements.tableContainer.innerHTML = '';
        const columns = [
            { key: 'id', label: 'Profile ID', render: val => `<span class="font-mono text-xs text-gray-600">${val}</span>` },
            { key: 'entity_name', label: 'Entity Name', render: val => `<span class="font-bold text-gray-900">${val}</span>` },
            { key: 'jurisdiction', label: 'Jurisdiction' },
            { 
                key: 'risk_score', 
                label: 'Risk Score', 
                align: 'center',
                render: val => {
                    const color = val > 80 ? 'text-red-600' : val > 50 ? 'text-orange-600' : 'text-green-600';
                    return `<span class="font-bold ${color}">${val}/100</span>`;
                }
            },
            { 
                key: 'status', 
                label: 'Status', 
                align: 'center',
                render: val => {
                    const colors = { 'CLEARED': 'bg-green-100 text-green-800', 'HIGH_RISK': 'bg-red-100 text-red-800', 'UNDER_REVIEW': 'bg-yellow-100 text-yellow-800', 'PENDING': 'bg-gray-100 text-gray-800' };
                    return `<span class="px-2 py-0.5 text-xs font-bold rounded ${colors[val] || colors.PENDING}">${val.replace('_', ' ')}</span>`;
                }
            },
            { key: 'last_reviewed', label: 'Last Reviewed', render: val => `<span class="text-xs text-gray-500">${val.split('T')[0]}</span>` }
        ];

        this.dataTable = new window.DataTable(this.elements.tableContainer, {
            columns: columns,
            data: data,
            pageSize: 10,
            searchable: true
        });
    }
}
