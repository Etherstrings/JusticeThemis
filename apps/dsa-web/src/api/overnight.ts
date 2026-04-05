import axios from 'axios';
import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  OvernightApiError,
  OvernightBrief,
  OvernightBriefHistoryResponse,
  OvernightEventDetail,
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

  getHistory: async (page = 1, limit = 6): Promise<OvernightBriefHistoryResponse> => {
    try {
      const response = await apiClient.get<Record<string, unknown>>('/api/v1/overnight/history', {
        params: { page, limit },
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

  getEventDetail: async (eventId: string): Promise<OvernightEventDetail | null> => {
    try {
      const response = await apiClient.get<Record<string, unknown>>(`/api/v1/overnight/events/${eventId}`);
      return toCamelCase<OvernightEventDetail>(response.data);
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  },
};
