class DataTable {
  constructor(containerSelector, options = {}) {
      this.container = document.querySelector(containerSelector);
      if (!this.container) throw new Error('DataTable container not found');

      this.options = {
          columns: [],
          data: [],
          pageSize: 10,
          pageSizes: [10, 25, 50, 100, 500],
          searchable: true,
          sortable: true,
          selectable: false,
          striped: true,
          hoverable: true,
          bordered: true,
          emptyMessage: 'No records found',
          loadingMessage: 'Loading data...',
          exportable: true,
          onRowClick: null,
          onSelectionChange: null,
          customRowClass: null,
          ...options
      };

      this.state = {
          data: [...this.options.data],
          filteredData: [...this.options.data],
          currentPage: 1,
          sortColumn: null,
          sortDirection: 'asc',
          searchQuery: '',
          selectedRows: new Set(),
          isLoading: false,
          expandedRows: new Set()
      };

      this.elements = {
          wrapper: null,
          header: null,
          tableContainer: null,
          table: null,
          thead: null,
          tbody: null,
          footer: null,
          paginationInfo: null,
          paginationControls: null,
          searchInput: null
      };

      this.init();
  }

  init() {
      this.buildDOMStructure();
      this.render();
      this.attachGlobalListeners();
  }

  buildDOMStructure() {
      this.container.innerHTML = '';

      this.elements.wrapper = window.domUtils.createElement('div', {
          className: 'dt-wrapper flex flex-col w-full bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden'
      });

      this.buildHeaderControls();

      this.elements.tableContainer = window.domUtils.createElement('div', {
          className: 'dt-table-container w-full overflow-x-auto relative'
      });

      this.elements.table = window.domUtils.createElement('table', {
          className: `dt-table w-full text-left text-sm text-gray-700 ${this.options.bordered ? 'divide-y divide-gray-200' : ''}`
      });

      this.elements.thead = window.domUtils.createElement('thead', {
          className: 'dt-thead bg-gray-50 text-xs uppercase text-gray-500 font-semibold tracking-wider sticky top-0 z-10'
      });

      this.elements.tbody = window.domUtils.createElement('tbody', {
          className: `dt-tbody divide-y divide-gray-100 bg-white ${this.options.striped ? 'dt-striped' : ''} ${this.options.hoverable ? 'dt-hoverable' : ''}`
      });

      this.elements.table.appendChild(this.elements.thead);
      this.elements.table.appendChild(this.elements.tbody);
      this.elements.tableContainer.appendChild(this.elements.table);

      this.buildFooterControls();

      this.elements.wrapper.appendChild(this.elements.header);
      this.elements.wrapper.appendChild(this.elements.tableContainer);
      this.elements.wrapper.appendChild(this.elements.footer);
      this.container.appendChild(this.elements.wrapper);
  }

  buildHeaderControls() {
      this.elements.header = window.domUtils.createElement('div', {
          className: 'dt-header-controls flex flex-col sm:flex-row justify-between items-center p-4 border-b border-gray-200 gap-4 bg-white'
      });

      const leftSection = window.domUtils.createElement('div', { className: 'flex items-center gap-2 w-full sm:w-auto' });

      if (this.options.searchable) {
          const searchWrapper = window.domUtils.createElement('div', { className: 'relative w-full sm:w-64' });

          const searchIcon = window.domUtils.createElement('span', {
              className: 'absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400',
              innerHTML: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>'
          });

          this.elements.searchInput = window.domUtils.createElement('input', {
              type: 'text',
              placeholder: 'Search records...',
              className: 'w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm transition-shadow'
          });

          searchWrapper.appendChild(searchIcon);
          searchWrapper.appendChild(this.elements.searchInput);
          leftSection.appendChild(searchWrapper);
      }

      const rightSection = window.domUtils.createElement('div', { className: 'flex items-center gap-3 w-full sm:w-auto justify-end' });

      if (this.options.exportable) {
          const exportBtn = window.domUtils.createElement('button', {
              className: 'flex items-center gap-2 px-3 py-2 bg-white border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 text-sm font-medium transition-colors',
              onclick: () => this.exportToCSV()
          }, [
              window.domUtils.createElement('span', { innerHTML: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>' }),
              'Export'
          ]);
          rightSection.appendChild(exportBtn);
      }

      this.elements.header.appendChild(leftSection);
      this.elements.header.appendChild(rightSection);
  }

  buildFooterControls() {
      this.elements.footer = window.domUtils.createElement('div', {
          className: 'dt-footer flex flex-col sm:flex-row justify-between items-center p-4 border-t border-gray-200 bg-gray-50 gap-4'
      });

      this.elements.paginationInfo = window.domUtils.createElement('div', {
          className: 'text-sm text-gray-600'
      });

      const paginationRight = window.domUtils.createElement('div', {
          className: 'flex items-center gap-4'
      });

      const pageSizeWrapper = window.domUtils.createElement('div', {
          className: 'flex items-center gap-2 text-sm text-gray-600'
      });

      pageSizeWrapper.appendChild(window.domUtils.createElement('span', { textContent: 'Rows per page:' }));

      const sizeSelect = window.domUtils.createElement('select', {
          className: 'border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white text-sm',
          onchange: (e) => this.setPageSize(parseInt(e.target.value, 10))
      });

      this.options.pageSizes.forEach(size => {
          const option = window.domUtils.createElement('option', {
              value: size,
              textContent: size
          });
          if (size === this.options.pageSize) option.selected = true;
          sizeSelect.appendChild(option);
      });

      pageSizeWrapper.appendChild(sizeSelect);

      this.elements.paginationControls = window.domUtils.createElement('div', {
          className: 'flex items-center gap-1'
      });

      paginationRight.appendChild(pageSizeWrapper);
      paginationRight.appendChild(this.elements.paginationControls);

      this.elements.footer.appendChild(this.elements.paginationInfo);
      this.elements.footer.appendChild(paginationRight);
  }

  attachGlobalListeners() {
      if (this.elements.searchInput) {
          this.elements.searchInput.addEventListener('input', window.domUtils.debounce((e) => {
              this.setSearchQuery(e.target.value);
          }, 300));
      }
  }

  updateData(newData) {
      this.options.data = newData;
      this.state.data = [...newData];
      this.state.selectedRows.clear();
      this.applyFiltersAndSort();
  }

  setLoading(isLoading) {
      this.state.isLoading = isLoading;
      this.renderBody();
  }

  setSearchQuery(query) {
      this.state.searchQuery = query.trim().toLowerCase();
      this.state.currentPage = 1;
      this.applyFiltersAndSort();
  }

  setPageSize(size) {
      this.options.pageSize = size;
      this.state.currentPage = 1;
      this.render();
  }

  goToPage(page) {
      const totalPages = Math.ceil(this.state.filteredData.length / this.options.pageSize);
      if (page < 1 || page > totalPages) return;
      this.state.currentPage = page;
      this.renderBody();
      this.renderPagination();
  }

  handleSort(columnKey) {
      if (!this.options.sortable) return;

      const colDef = this.options.columns.find(c => c.key === columnKey);
      if (colDef && colDef.sortable === false) return;

      if (this.state.sortColumn === columnKey) {
          this.state.sortDirection = this.state.sortDirection === 'asc' ? 'desc' : 'asc';
      } else {
          this.state.sortColumn = columnKey;
          this.state.sortDirection = 'asc';
      }

      this.applyFiltersAndSort();
      this.renderHeader();
  }

  applyFiltersAndSort() {
      let result = [...this.state.data];

      if (this.state.searchQuery) {
          result = result.filter(row => {
              return this.options.columns.some(col => {
                  const val = this.getNestedValue(row, col.key);
                  if (val === null || val === undefined) return false;
                  return String(val).toLowerCase().includes(this.state.searchQuery);
              });
          });
      }

      if (this.state.sortColumn) {
          const colDef = this.options.columns.find(c => c.key === this.state.sortColumn);
          const dir = this.state.sortDirection === 'asc' ? 1 : -1;

          result.sort((a, b) => {
              let valA = this.getNestedValue(a, this.state.sortColumn);
              let valB = this.getNestedValue(b, this.state.sortColumn);

              if (colDef && typeof colDef.sortMethod === 'function') {
                  return colDef.sortMethod(valA, valB) * dir;
              }

              if (valA === null || valA === undefined) valA = '';
              if (valB === null || valB === undefined) valB = '';

              if (typeof valA === 'number' && typeof valB === 'number') {
                  return (valA - valB) * dir;
              }

              return String(valA).localeCompare(String(valB)) * dir;
          });
      }

      this.state.filteredData = result;

      const totalPages = Math.ceil(this.state.filteredData.length / this.options.pageSize);
      if (this.state.currentPage > totalPages && totalPages > 0) {
          this.state.currentPage = totalPages;
      } else if (totalPages === 0) {
          this.state.currentPage = 1;
      }

      this.renderBody();
      this.renderPagination();
  }

  getNestedValue(obj, path) {
      return path.split('.').reduce((o, p) => (o && o[p] !== undefined) ? o[p] : null, obj);
  }

  toggleSelectAll(checked) {
      const pageData = this.getCurrentPageData();
      if (checked) {
          pageData.forEach(row => {
              const id = row.id || JSON.stringify(row);
              this.state.selectedRows.add(id);
          });
      } else {
          pageData.forEach(row => {
              const id = row.id || JSON.stringify(row);
              this.state.selectedRows.delete(id);
          });
      }

      if (typeof this.options.onSelectionChange === 'function') {
          this.options.onSelectionChange(Array.from(this.state.selectedRows));
      }

      this.renderBody();
      this.renderHeader();
  }

  toggleRowSelection(rowId) {
      if (this.state.selectedRows.has(rowId)) {
          this.state.selectedRows.delete(rowId);
      } else {
          this.state.selectedRows.add(rowId);
      }

      if (typeof this.options.onSelectionChange === 'function') {
          this.options.onSelectionChange(Array.from(this.state.selectedRows));
      }

      this.renderHeader();
  }

  getCurrentPageData() {
      const start = (this.state.currentPage - 1) * this.options.pageSize;
      const end = start + this.options.pageSize;
      return this.state.filteredData.slice(start, end);
  }

  render() {
      this.renderHeader();
      this.renderBody();
      this.renderPagination();
  }

  renderHeader() {
      window.domUtils.clearChildren(this.elements.thead);
      const tr = window.domUtils.createElement('tr');

      if (this.options.selectable) {
          const th = window.domUtils.createElement('th', {
              className: 'px-6 py-3 w-12'
          });

          const pageData = this.getCurrentPageData();
          const allSelected = pageData.length > 0 && pageData.every(row => {
              const id = row.id || JSON.stringify(row);
              return this.state.selectedRows.has(id);
          });
          const someSelected = pageData.some(row => {
              const id = row.id || JSON.stringify(row);
              return this.state.selectedRows.has(id);
          });

          const checkbox = window.domUtils.createElement('input', {
              type: 'checkbox',
              className: 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 cursor-pointer',
              checked: allSelected,
              onchange: (e) => this.toggleSelectAll(e.target.checked)
          });

          if (someSelected && !allSelected) {
              checkbox.indeterminate = true;
          }

          th.appendChild(checkbox);
          tr.appendChild(th);
      }

      this.options.columns.forEach(col => {
          const thProps = {
              className: `px-6 py-3 font-semibold ${col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'} whitespace-nowrap`,
              style: col.width ? { width: col.width, minWidth: col.width } : {}
          };

          const isSortable = this.options.sortable && col.sortable !== false;

          if (isSortable) {
              thProps.className += ' cursor-pointer hover:bg-gray-100 select-none group transition-colors';
              thProps.onclick = () => this.handleSort(col.key);
          }

          const th = window.domUtils.createElement('th', thProps);
          const contentWrapper = window.domUtils.createElement('div', {
              className: `flex items-center gap-2 ${col.align === 'right' ? 'justify-end' : col.align === 'center' ? 'justify-center' : 'justify-start'}`
          });

          contentWrapper.appendChild(window.domUtils.createElement('span', { textContent: col.label }));

          if (isSortable) {
              const iconWrapper = window.domUtils.createElement('span', {
                  className: `text-gray-400 ${this.state.sortColumn === col.key ? 'text-blue-600' : 'opacity-0 group-hover:opacity-100 transition-opacity'}`
              });

              if (this.state.sortColumn === col.key) {
                  iconWrapper.innerHTML = this.state.sortDirection === 'asc' 
                      ? '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"></path></svg>'
                      : '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>';
              } else {
                  iconWrapper.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"></path></svg>';
              }
              contentWrapper.appendChild(iconWrapper);
          }

          th.appendChild(contentWrapper);
          tr.appendChild(th);
      });

      this.elements.thead.appendChild(tr);
  }

  renderBody() {
      window.domUtils.clearChildren(this.elements.tbody);

      if (this.state.isLoading) {
          const tr = window.domUtils.createElement('tr');
          const td = window.domUtils.createElement('td', {
              colSpan: this.options.columns.length + (this.options.selectable ? 1 : 0),
              className: 'px-6 py-12 text-center'
          });
          td.appendChild(window.domUtils.createLoader('large'));
          const text = window.domUtils.createElement('p', {
              className: 'mt-4 text-gray-500 font-medium text-sm',
              textContent: this.options.loadingMessage
          });
          td.appendChild(text);
          tr.appendChild(td);
          this.elements.tbody.appendChild(tr);
          return;
      }

      const pageData = this.getCurrentPageData();

      if (pageData.length === 0) {
          const tr = window.domUtils.createElement('tr');
          const td = window.domUtils.createElement('td', {
              colSpan: this.options.columns.length + (this.options.selectable ? 1 : 0),
              className: 'px-6 py-12 text-center text-gray-500 bg-gray-50'
          });

          const emptyIcon = window.domUtils.createElement('div', {
              className: 'mx-auto w-12 h-12 text-gray-300 mb-3',
              innerHTML: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path></svg>'
          });

          td.appendChild(emptyIcon);
          td.appendChild(window.domUtils.createElement('p', { className: 'text-sm', textContent: this.state.searchQuery ? `No results matching "${this.state.searchQuery}"` : this.options.emptyMessage }));
          tr.appendChild(td);
          this.elements.tbody.appendChild(tr);
          return;
      }

      pageData.forEach((row, index) => {
          const rowId = row.id || JSON.stringify(row);
          const isSelected = this.state.selectedRows.has(rowId);

          let rowClass = 'transition-colors ';
          if (this.options.hoverable && !this.options.striped) rowClass += 'hover:bg-gray-50 ';
          if (this.options.striped && index % 2 !== 0) rowClass += 'bg-gray-50 ';
          if (isSelected) rowClass += 'bg-blue-50 hover:bg-blue-100 ';

          if (typeof this.options.customRowClass === 'function') {
              rowClass += this.options.customRowClass(row) || '';
          }

          const trProps = { className: rowClass.trim() };
          if (typeof this.options.onRowClick === 'function' && !this.options.selectable) {
              trProps.className += ' cursor-pointer';
              trProps.onclick = (e) => {
                  if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'BUTTON' && e.target.tagName !== 'A') {
                      this.options.onRowClick(row, e);
                  }
              };
          }

          const tr = window.domUtils.createElement('tr', trProps);

          if (this.options.selectable) {
              const td = window.domUtils.createElement('td', { className: 'px-6 py-4 whitespace-nowrap w-12' });
              const checkbox = window.domUtils.createElement('input', {
                  type: 'checkbox',
                  className: 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 cursor-pointer',
                  checked: isSelected,
                  onchange: () => this.toggleRowSelection(rowId)
              });
              td.appendChild(checkbox);
              tr.appendChild(td);
          }

          this.options.columns.forEach(col => {
              const td = window.domUtils.createElement('td', {
                  className: `px-6 py-4 ${col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'} text-sm text-gray-900 ${col.wrap ? '' : 'whitespace-nowrap'}`
              });

              const rawValue = this.getNestedValue(row, col.key);

              if (typeof col.render === 'function') {
                  const rendered = col.render(rawValue, row, td);
                  if (rendered instanceof Node) {
                      td.appendChild(rendered);
                  } else if (rendered !== undefined && rendered !== null) {
                      td.innerHTML = rendered;
                  }
              } else if (col.format) {
                  if (col.format === 'currency') td.textContent = window.formatters?.formatCurrency(rawValue) || rawValue;
                  else if (col.format === 'date') td.textContent = window.formatters?.formatDate(rawValue) || rawValue;
                  else if (col.format === 'relativeTime') td.textContent = window.formatters?.formatRelativeTime(rawValue) || rawValue;
                  else td.textContent = rawValue !== null && rawValue !== undefined ? rawValue : '-';
              } else {
                  td.textContent = rawValue !== null && rawValue !== undefined ? rawValue : '-';
              }

              tr.appendChild(td);
          });

          this.elements.tbody.appendChild(tr);
      });
  }

  renderPagination() {
      const totalRecords = this.state.filteredData.length;
      const totalPages = Math.ceil(totalRecords / this.options.pageSize);
      const currentStart = totalRecords === 0 ? 0 : ((this.state.currentPage - 1) * this.options.pageSize) + 1;
      const currentEnd = Math.min(this.state.currentPage * this.options.pageSize, totalRecords);

      this.elements.paginationInfo.innerHTML = `Showing <span class="font-medium text-gray-900">${currentStart}</span> to <span class="font-medium text-gray-900">${currentEnd}</span> of <span class="font-medium text-gray-900">${totalRecords}</span> results`;

      window.domUtils.clearChildren(this.elements.paginationControls);

      if (totalPages <= 1) return;

      const createBtn = (content, disabled, onClick, isActive = false) => {
          return window.domUtils.createElement('button', {
              className: `relative inline-flex items-center px-3 py-1 border text-sm font-medium rounded-md transition-colors 
                          ${disabled ? 'border-gray-200 text-gray-400 bg-gray-50 cursor-not-allowed' : 
                            isActive ? 'z-10 bg-blue-50 border-blue-500 text-blue-600' : 
                            'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'}`,
              disabled: disabled,
              onclick: disabled ? null : onClick,
              innerHTML: content
          });
      };

      const prevBtn = createBtn('<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>', this.state.currentPage === 1, () => this.goToPage(this.state.currentPage - 1));
      this.elements.paginationControls.appendChild(prevBtn);

      let startPage = Math.max(1, this.state.currentPage - 2);
      let endPage = Math.min(totalPages, startPage + 4);

      if (endPage - startPage < 4) {
          startPage = Math.max(1, endPage - 4);
      }

      if (startPage > 1) {
          this.elements.paginationControls.appendChild(createBtn('1', false, () => this.goToPage(1)));
          if (startPage > 2) {
              this.elements.paginationControls.appendChild(window.domUtils.createElement('span', { className: 'px-2 text-gray-400 text-sm', textContent: '...' }));
          }
      }

      for (let i = startPage; i <= endPage; i++) {
          this.elements.paginationControls.appendChild(createBtn(i.toString(), false, () => this.goToPage(i), this.state.currentPage === i));
      }

      if (endPage < totalPages) {
          if (endPage < totalPages - 1) {
              this.elements.paginationControls.appendChild(window.domUtils.createElement('span', { className: 'px-2 text-gray-400 text-sm', textContent: '...' }));
          }
          this.elements.paginationControls.appendChild(createBtn(totalPages.toString(), false, () => this.goToPage(totalPages)));
      }

      const nextBtn = createBtn('<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>', this.state.currentPage === totalPages, () => this.goToPage(this.state.currentPage + 1));
      this.elements.paginationControls.appendChild(nextBtn);
  }

  exportToCSV(filename = 'export.csv') {
      const exportData = this.state.filteredData;
      if (!exportData || exportData.length === 0) return;

      const headers = this.options.columns.filter(c => c.exportable !== false).map(c => `"${c.label.replace(/"/g, '""')}"`).join(',');

      const rows = exportData.map(row => {
          return this.options.columns.filter(c => c.exportable !== false).map(col => {
              let val = this.getNestedValue(row, col.key);
              if (val === null || val === undefined) val = '';
              else if (typeof val === 'object') val = JSON.stringify(val);
              else val = String(val);
              return `"${val.replace(/"/g, '""')}"`;
          }).join(',');
      });

      const csvContent = [headers, ...rows].join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);

      link.setAttribute('href', url);
      link.setAttribute('download', filename);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
  }
}
window.DataTable = DataTable;