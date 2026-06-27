class AmlApiService {
  constructor(apiClient) {
      this.api = apiClient;
      this.basePath = '/aml';
  }

  async getWatchlists() {
      const url = `${this.basePath}/watchlists`;
      return await this.api.get(url);
  }
}

window.amlApi = new AmlApiService(window.apiClient);
