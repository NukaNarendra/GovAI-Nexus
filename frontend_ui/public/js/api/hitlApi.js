class HitlApiService {
  constructor(apiClient) {
      this.api = apiClient;
      this.basePath = '/hitl';
  }

  async getPendingTasks(params = {}) {
      const defaultParams = {
          page: 1,
          size: 50
      };
      const queryParams = { ...defaultParams, ...params };

      Object.keys(queryParams).forEach(key => {
          if (queryParams[key] === null || queryParams[key] === undefined || queryParams[key] === '') {
              delete queryParams[key];
          }
      });

      return await this.api.get(`${this.basePath}/tasks/pending`, queryParams);
  }

  async getMyAssignments(includeResolved = false, page = 1, size = 50) {
      const params = {
          include_resolved: includeResolved,
          page: page,
          size: size
      };
      return await this.api.get(`${this.basePath}/tasks/my-assignments`, params);
  }

  async getTaskDetails(taskId) {
      if (!taskId) {
          throw new Error('Task ID is required');
      }
      return await this.api.get(`${this.basePath}/tasks/${taskId}`);
  }

  async claimTask(taskId) {
      if (!taskId) {
          throw new Error('Task ID is required');
      }
      return await this.api.post(`${this.basePath}/tasks/${taskId}/claim`);
  }

  async unclaimTask(taskId) {
      if (!taskId) {
          throw new Error('Task ID is required');
      }
      return await this.api.post(`${this.basePath}/tasks/${taskId}/unclaim`);
  }

  async resolveTask(taskId, resolutionStatus, officerNotes, actionTaken, generateAiFeedback = true) {
      if (!taskId) throw new Error('Task ID is required');
      if (!['APPROVED', 'REJECTED'].includes(resolutionStatus)) {
          throw new Error('Invalid resolution status');
      }
      if (!officerNotes || officerNotes.trim().length < 10) {
          throw new Error('Detailed officer notes are required for resolution');
      }

      const payload = {
          resolution_status: resolutionStatus,
          officer_notes: officerNotes,
          action_taken: actionTaken,
          generate_ai_feedback: generateAiFeedback
      };

      return await this.api.post(`${this.basePath}/tasks/${taskId}/resolve`, payload);
  }

  async escalateTask(taskId, escalationReason, targetDepartmentId = null) {
      if (!taskId) throw new Error('Task ID is required');
      if (!escalationReason || escalationReason.trim().length < 10) {
          throw new Error('Detailed escalation reason is required');
      }

      const payload = {
          escalation_reason: escalationReason
      };

      if (targetDepartmentId) {
          payload.target_department_id = targetDepartmentId;
      }

      return await this.api.post(`${this.basePath}/tasks/${taskId}/escalate`, payload);
  }

  async reassignTask(taskId, targetUserId, reassignmentReason) {
      if (!taskId || !targetUserId) throw new Error('Task ID and Target User ID are required');

      const payload = {
          target_user_id: targetUserId,
          reason: reassignmentReason
      };

      return await this.api.post(`${this.basePath}/tasks/${taskId}/reassign`, payload);
  }

  async getMetrics() {
      return await this.api.get(`${this.basePath}/metrics`);
  }

  async getTaskHistory(taskId) {
      if (!taskId) throw new Error('Task ID is required');
      return await this.api.get(`${this.basePath}/tasks/${taskId}/history`);
  }

  async getTaskComments(taskId) {
      if (!taskId) throw new Error('Task ID is required');
      return await this.api.get(`${this.basePath}/tasks/${taskId}/comments`);
  }

  async addTaskComment(taskId, commentText, isInternal = true) {
      if (!taskId) throw new Error('Task ID is required');
      if (!commentText || commentText.trim().length === 0) {
          throw new Error('Comment text cannot be empty');
      }

      const payload = {
          content: commentText,
          is_internal_only: isInternal
      };

      return await this.api.post(`${this.basePath}/tasks/${taskId}/comments`, payload);
  }

  async getRelatedTasks(resourceId) {
      if (!resourceId) throw new Error('Resource ID is required');
      return await this.api.get(`${this.basePath}/tasks/related/${resourceId}`);
  }

  async bulkClaim(taskIds) {
      if (!Array.isArray(taskIds) || taskIds.length === 0) {
          throw new Error('A list of Task IDs is required');
      }
      if (taskIds.length > 50) {
          throw new Error('Cannot claim more than 50 tasks at once');
      }

      const payload = {
          task_ids: taskIds
      };

      return await this.api.post(`${this.basePath}/tasks/bulk/claim`, payload);
  }

  async bulkResolve(resolutions) {
      if (!Array.isArray(resolutions) || resolutions.length === 0) {
          throw new Error('A list of resolutions is required');
      }

      const validResolutions = resolutions.map(res => {
          if (!res.task_id || !res.resolution_status || !res.officer_notes || !res.action_taken) {
              throw new Error('Invalid bulk resolution object format');
          }
          return {
              task_id: res.task_id,
              resolution_status: res.resolution_status,
              officer_notes: res.officer_notes,
              action_taken: res.action_taken,
              generate_ai_feedback: res.generate_ai_feedback !== false
          };
      });

      const payload = {
          resolutions: validResolutions
      };

      return await this.api.post(`${this.basePath}/tasks/bulk/resolve`, payload);
  }

  async getTaskAttachments(taskId) {
      if (!taskId) throw new Error('Task ID is required');
      return await this.api.get(`${this.basePath}/tasks/${taskId}/attachments`);
  }

  async uploadTaskAttachment(taskId, file, description = '') {
      if (!taskId || !file) throw new Error('Task ID and File are required');

      return await this.api.upload(
          `${this.basePath}/tasks/${taskId}/attachments`,
          file,
          'document',
          { description: description }
      );
  }

  async downloadTaskAttachment(taskId, attachmentId) {
      if (!taskId || !attachmentId) throw new Error('Task ID and Attachment ID are required');

      const response = await this.api.get(
          `${this.basePath}/tasks/${taskId}/attachments/${attachmentId}/download`,
          {},
          { responseType: 'blob' }
      );

      return response;
  }

  async exportQueueReport(format = 'csv', filters = {}) {
      const validFormats = ['csv', 'json', 'pdf'];
      if (!validFormats.includes(format.toLowerCase())) {
          throw new Error(`Invalid format. Must be one of: ${validFormats.join(', ')}`);
      }

      const queryParams = { ...filters, format: format.toLowerCase() };

      Object.keys(queryParams).forEach(key => {
          if (queryParams[key] === null || queryParams[key] === undefined || queryParams[key] === '') {
              delete queryParams[key];
          }
      });

      return await this.api.get(`${this.basePath}/reports/export`, queryParams, { responseType: 'blob' });
  }

  async getTaskAuditTrail(taskId) {
      if (!taskId) throw new Error('Task ID is required');
      return await this.api.get(`${this.basePath}/tasks/${taskId}/audit-trail`);
  }

  async updateTaskPriority(taskId, newPriority, justification) {
      if (!taskId || !newPriority) throw new Error('Task ID and new priority are required');

      const payload = {
          priority: newPriority,
          justification: justification || 'Priority updated via dashboard'
      };

      return await this.api.patch(`${this.basePath}/tasks/${taskId}/priority`, payload);
  }

  async getTaskAIFeedbackHistory(taskId) {
      if (!taskId) throw new Error('Task ID is required');
      return await this.api.get(`${this.basePath}/tasks/${taskId}/ai-feedback`);
  }

  async flagForEngineeringReview(taskId, technicalNotes) {
      if (!taskId) throw new Error('Task ID is required');

      const payload = {
          flag_type: 'ENGINEERING_REVIEW',
          technical_notes: technicalNotes
      };

      return await this.api.post(`${this.basePath}/tasks/${taskId}/flag`, payload);
  }
}

window.hitlApi = new HitlApiService(window.apiClient);