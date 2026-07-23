import { useCallback } from 'react';
import { api } from '../api/client';
import { getSessionId } from '../utils/session';

interface LogEventParams {
  eventType: string;
  objectType?: string;
  objectId?: string;
  metadata?: any;
  durationMs?: number;
}

export function useEventLogger() {
  const logEvent = useCallback((params: LogEventParams) => {
    // Fire and forget
    api.logEvent({
      event_type: params.eventType,
      object_type: params.objectType,
      object_id: params.objectId,
      session_id: getSessionId(),
      metadata: params.metadata,
      duration_ms: params.durationMs,
    }).catch(() => {
      // Swallowed
    });
  }, []);

  return { logEvent };
}
