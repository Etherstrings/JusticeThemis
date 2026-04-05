import axios from 'axios';
import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  OvernightApiError,
  OvernightBrief,
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
