import axios from 'axios';
import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  OvernightApiError,
  OvernightBrief,
  OvernightBriefDeltaResponse,
  OvernightBriefHistoryResponse,
  OvernightEventHistoryResponse,
  OvernightFeedbackCreateRequest,
  OvernightFeedbackListResponse,
  OvernightFeedbackResponse,
  OvernightEventDetail,
  OvernightHealthResponse,
  OvernightSourceListResponse,
  OvernightTopicHistoryResponse,
} from '../types/overnight';

export class OvernightBriefUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'OvernightBriefUnavailableError';
  }
}

function readApiErrorMessage(data: unknown, fallback: string): string {
  if (!data || typeof data !== 'object') {
    return fallback;
  }

  const { message } = data as Partial<OvernightApiError>;
  return typeof message === 'string' && message.trim() ? message : fallback;
}

export const overnightApi = {
  getLatestBrief: async (): Promise<OvernightBrief> => {
    try {
      const response = await apiClient.get<Record<string, unknown>>('/api/v1/overnight/brief/latest');
      return toCamelCase<OvernightBrief>(response.data);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        throw new OvernightBriefUnavailableError(
          readApiErrorMessage(error.response.data, 'No overnight brief is available yet.')
        );
      }
      throw error;
    }
  },

  getBriefById: async (briefId: string): Promise<OvernightBrief> => {
    try {
      const response = await apiClient.get<Record<string, unknown>>(`/api/v1/overnight/briefs/${briefId}`);
      return toCamelCase<OvernightBrief>(response.data);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        throw new OvernightBriefUnavailableError(
          readApiErrorMessage(error.response.data, 'Overnight brief not found.')
        );
      }
      throw error;
    }
  },

  getLatestBriefDelta: async (): Promise<OvernightBriefDeltaResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/overnight/brief/latest/delta');
    return toCamelCase<OvernightBriefDeltaResponse>(response.data);
  },

  getBriefDeltaById: async (briefId: string): Promise<OvernightBriefDeltaResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/overnight/briefs/${briefId}/delta`);
    return toCamelCase<OvernightBriefDeltaResponse>(response.data);
  },

  getHistory: async (page = 1, limit = 6, q?: string): Promise<OvernightBriefHistoryResponse> => {
    try {
      const response = await apiClient.get<Record<string, unknown>>('/api/v1/overnight/history', {
        params: { page, limit, q },
      });
      return toCamelCase<OvernightBriefHistoryResponse>(response.data);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return {
          total: 0,
          page,
          limit,
          items: [],
        };
      }
      throw error;
    }
  },

  getEventHistory: async (page = 1, limit = 20, q?: string): Promise<OvernightEventHistoryResponse> => {
    try {
      const response = await apiClient.get<Record<string, unknown>>('/api/v1/overnight/history/events', {
        params: { page, limit, q },
      });
      return toCamelCase<OvernightEventHistoryResponse>(response.data);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return {
          total: 0,
          page,
          limit,
          items: [],
        };
      }
      throw error;
    }
  },

  getTopicHistory: async (page = 1, limit = 20, q?: string): Promise<OvernightTopicHistoryResponse> => {
    try {
      const response = await apiClient.get<Record<string, unknown>>('/api/v1/overnight/history/topics', {
        params: { page, limit, q },
      });
      return toCamelCase<OvernightTopicHistoryResponse>(response.data);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return {
          total: 0,
          page,
          limit,
          items: [],
        };
      }
      throw error;
    }
  },

  getEventDetail: async (eventId: string, briefId?: string): Promise<OvernightEventDetail | null> => {
    try {
      const response = await apiClient.get<Record<string, unknown>>(`/api/v1/overnight/events/${eventId}`, {
        params: briefId ? { brief_id: briefId } : undefined,
      });
      return toCamelCase<OvernightEventDetail>(response.data);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  },

  getSources: async (): Promise<OvernightSourceListResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/overnight/sources');
    return toCamelCase<OvernightSourceListResponse>(response.data);
  },

  getHealth: async (): Promise<OvernightHealthResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/overnight/health');
    return toCamelCase<OvernightHealthResponse>(response.data);
  },

  submitFeedback: async (payload: OvernightFeedbackCreateRequest): Promise<OvernightFeedbackResponse> => {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/overnight/feedback', payload);
    return toCamelCase<OvernightFeedbackResponse>(response.data);
  },

  getFeedback: async (
    page = 1,
    limit = 20,
    targetType?: 'brief' | 'event',
    status?: string
  ): Promise<OvernightFeedbackListResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/overnight/feedback', {
      params: {
        page,
        limit,
        target_type: targetType,
        status,
      },
    });
    return toCamelCase<OvernightFeedbackListResponse>(response.data);
  },

  updateFeedbackStatus: async (
    feedbackId: number,
    status: 'pending_review' | 'reviewed' | 'dismissed'
  ): Promise<OvernightFeedbackResponse> => {
    const response = await apiClient.patch<Record<string, unknown>>(`/api/v1/overnight/feedback/${feedbackId}`, {
      status,
    });
    return toCamelCase<OvernightFeedbackResponse>(response.data);
  },
};
