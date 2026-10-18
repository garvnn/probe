'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, type Schemas } from './api';
import { asObj } from './utils';
export type StreamStatus = 'idle' | 'connecting' | 'streaming' | 'done' | 'paused' | 'error';
export type RoundEvent = Schemas['RoundEvent'];
/** EventSource transport + buffered replay. Pausing does not drop server events. */
export function useForgerStream(runId: string | null) {
  const [rounds, setRounds] = useState<RoundEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [replayIndex, setReplayIndex] = useState(0);
  const buffer = useRef<RoundEvent[]>([]); const paused = useRef(false); const streamDone = useRef(false);
  useEffect(() => {
    buffer.current = []; paused.current = false; streamDone.current = false;
    setRounds([]); setReplayIndex(0); setError(null);
    if (!runId) { setStatus('idle'); return; }
    setStatus('connecting');
    const source = new EventSource(api.fakeDataStreamUrl(runId));
    const ingest = (event: MessageEvent) => {
      try {
        const payload: unknown = JSON.parse(event.data);
        const item = asObj(payload);
        if (item.event === 'done' || item.type === 'done' || item.status === 'done') {
          streamDone.current = true; if (!paused.current) setStatus('done'); source.close(); return;
        }
        if (item.event === 'error' || item.type === 'error') { setError(String(item.message || 'Stream error')); setStatus('error'); source.close(); return; }
        // Ignore heartbeats; never add non-round messages to the replay.
        if (item.round === undefined && item.scores === undefined && item.checks === undefined) return;
        buffer.current.push(payload as RoundEvent);
        if (!paused.current) { setRounds([...buffer.current]); setReplayIndex(buffer.current.length); setStatus('streaming'); }
      } catch { setError('Unparseable stream event'); setStatus('error'); }
    };
    source.onopen = () => setStatus(s => s === 'connecting' ? 'streaming' : s);
    source.onmessage = ingest;
    source.addEventListener('round', ingest as EventListener);
    source.addEventListener('done', () => { streamDone.current = true; source.close(); if (!paused.current) setStatus('done'); });
    source.onerror = () => { if (streamDone.current) return; setError('Stream disconnected. Previous rounds remain available.'); setStatus('error'); source.close(); };
    return () => source.close();
  }, [runId]);
  const pause = useCallback(() => { paused.current = true; setStatus('paused'); }, []);
  const resume = useCallback(() => { paused.current = false; setRounds([...buffer.current]); setReplayIndex(buffer.current.length); setStatus(streamDone.current ? 'done' : 'streaming'); }, []);
  const restart = useCallback(() => { paused.current = true; setRounds([]); setReplayIndex(0); setStatus('paused'); }, []);
  const step = useCallback(() => { paused.current = true; setReplayIndex(i => { const next = Math.min(buffer.current.length, i + 1); setRounds(buffer.current.slice(0, next)); return next; }); setStatus('paused'); }, []);
  return { rounds, status, error, pause, resume, restart, step, replayIndex, buffered: buffer.current.length };
}
