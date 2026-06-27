class KycApiService {
  constructor(apiClient) {
      this.api = apiClient;
      this.basePath = '/kyc';
  }

  async getProfiles() {
      const url = `${this.basePath}/profiles`;
      return await this.api.get(url);
  }
}

window.kycApi = new KycApiService(window.apiClient);
