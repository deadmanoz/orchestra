import axios from 'axios';
import { QueryClient } from '@tanstack/react-query';
import type {
  WorkflowCreate,
  WorkflowStateSnapshot,
  CheckpointResolution
} from '../types';

// Axios instance configured for backend API
export const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// TanStack Query client with sensible defaults
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5000,
    },
  },
});

// API functions
export const workflowApi = {
  create: async (data: WorkflowCreate) => {
    const response = await api.post('/workflows', data);
    return response.data;
  },

  get: async (workflowId: string): Promise<WorkflowStateSnapshot> => {
    const response = await api.get(`/workflows/${workflowId}`);
    return response.data;
  },

  resume: async (workflowId: string, resolution: CheckpointResolution) => {
    const response = await api.post(`/workflows/${workflowId}/resume`, resolution);
    return response.data;
  },
};

// WebSocket connection manager
export class WorkflowWebSocket {
  private ws: WebSocket | null = null;
  private listeners: Map<string, Set<(data: any) => void>> = new Map();

  connect(workflowId: string) {
    const wsUrl = `ws://${window.location.host}/ws/${workflowId}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      const listeners = this.listeners.get(message.type) || new Set();
      listeners.forEach(listener => listener(message));
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return this;
  }

  on(eventType: string, callback: (data: any) => void) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType)!.add(callback);
  }

  off(eventType: string, callback: (data: any) => void) {
    const listeners = this.listeners.get(eventType);
    if (listeners) {
      listeners.delete(callback);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.listeners.clear();
  }
}
