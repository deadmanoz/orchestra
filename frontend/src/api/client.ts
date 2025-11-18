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
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private workflowId: string | null = null;

  connect(workflowId: string) {
    this.workflowId = workflowId;
    const wsUrl = `ws://${window.location.host}/ws/${workflowId}`;
    console.log('[WebSocket] Connecting to:', wsUrl);
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('[WebSocket] Connection opened');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log('[WebSocket] Message received:', message);
        const listeners = this.listeners.get(message.type) || new Set();
        listeners.forEach(listener => listener(message));
      } catch (error) {
        console.error('[WebSocket] Failed to parse message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error);
    };

    this.ws.onclose = (event) => {
      console.log('[WebSocket] Connection closed:', event.code, event.reason);

      // Attempt to reconnect if not a normal closure
      if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        console.log(`[WebSocket] Reconnecting... (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        setTimeout(() => {
          if (this.workflowId) {
            this.connect(this.workflowId);
          }
        }, 2000 * this.reconnectAttempts);
      }
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
