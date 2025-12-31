/**
 * Export Config File Fetching
 * Handles automatic fetching of DET config files from CommCare HQ API
 */

class ExportConfigFetcher {
  constructor(options) {
    this.apiUrl = options.apiUrl;
    this.accountSelect = document.querySelector('#id_account');
    this.projectSelect = document.querySelector('#id_project');
    this.projectCheckboxes = document.querySelectorAll('input[name="projects"]');
    this.configSelect = document.querySelector('#id_config_file_select');
    this.detConfigUrlInput = document.querySelector('#id_det_config_url');
    this.loadingMessage = document.querySelector('#config-loading-message');
    this.errorMessage = document.querySelector('#config-error-message');

    this.isMultiProject = this.projectCheckboxes.length > 0;

    this.init();
  }

  init() {
    this.attachEventListeners();
    this.initialFetch();
  }

  getSelectedProjectIds() {
    if (this.isMultiProject) {
      return Array.from(this.projectCheckboxes)
        .filter(cb => cb.checked)
        .map(cb => cb.value);
    } else if (this.projectSelect) {
      return this.projectSelect.value ? [this.projectSelect.value] : [];
    }
    return [];
  }

  fetchAvailableConfigs() {
    const accountId = this.accountSelect ? this.accountSelect.value : null;
    const projectIds = this.getSelectedProjectIds();

    this.configSelect.disabled = true;
    this.detConfigUrlInput.value = '';
    this.errorMessage.style.display = 'none';

    if (!accountId || projectIds.length === 0) {
      this.configSelect.innerHTML = '<option value="">Select account and project(s) first...</option>';
      this.loadingMessage.style.display = 'none';
      return;
    }

    this.configSelect.innerHTML = '<option value="">Loading...</option>';
    this.loadingMessage.style.display = 'block';

    const url = `${this.apiUrl}?account_id=${accountId}&project_ids=${projectIds.join(',')}`;

    fetch(url)
      .then(response => {
        if (!response.ok) {
          throw new Error('Failed to fetch configs');
        }
        return response.json();
      })
      .then(data => {
        this.loadingMessage.style.display = 'none';

        if (data.error) {
          throw new Error(data.error);
        }

        const configs = data.configs || [];

        if (configs.length === 0) {
          this.configSelect.innerHTML = '<option value="">No configs available</option>';
          this.errorMessage.textContent = 'No export configs found for the selected account and project(s).';
          this.errorMessage.style.display = 'block';
        } else {
          this.configSelect.innerHTML = '<option value="">Select a config file...</option>';
          configs.forEach(config => {
            const option = document.createElement('option');
            option.value = config.det_config_url;
            option.textContent = this.isMultiProject
              ? `${config.name} (${config.domain})`
              : config.name;
            this.configSelect.appendChild(option);
          });
          this.configSelect.disabled = false;
        }
      })
      .catch(error => {
        this.loadingMessage.style.display = 'none';
        this.configSelect.innerHTML = '<option value="">Error loading configs</option>';
        this.errorMessage.textContent = `Error: ${error.message}`;
        this.errorMessage.style.display = 'block';
      });
  }

  attachEventListeners() {
    // Update hidden field when config is selected
    this.configSelect.addEventListener('change', () => {
      this.detConfigUrlInput.value = this.configSelect.value;
    });

    // Listen for account/project changes
    if (this.accountSelect) {
      this.accountSelect.addEventListener('change', () => {
        this.fetchAvailableConfigs();
      });
    }

    if (this.projectSelect) {
      this.projectSelect.addEventListener('change', () => {
        this.fetchAvailableConfigs();
      });
    }

    if (this.isMultiProject) {
      this.projectCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', () => {
          this.fetchAvailableConfigs();
        });
      });
    }
  }

  initialFetch() {
    // Initial fetch if account and project are already selected (e.g., when editing)
    if (this.accountSelect && this.accountSelect.value && this.getSelectedProjectIds().length > 0) {
      this.fetchAvailableConfigs();
    }
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    const apiUrl = document.querySelector('#export-config-form')?.dataset.fetchConfigUrl;
    if (apiUrl) {
      new ExportConfigFetcher({ apiUrl });
    }
  });
} else {
  const apiUrl = document.querySelector('#export-config-form')?.dataset.fetchConfigUrl;
  if (apiUrl) {
    new ExportConfigFetcher({ apiUrl });
  }
}
