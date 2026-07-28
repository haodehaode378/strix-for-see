import { useEffect, useRef, useState } from "react";

import { controlServiceFetch } from "../../shared/api/controlServiceClient";
import type {
  LiveConnectionState,
  ScanEvent,
} from "./contracts";

const MAX_EVENTS = 2_000;
const notifiedEventIds = new Set<string>();

export function useLiveEvents(scanId: string) {
  const [events, setEvents] = useState<ScanEvent[]>([]);
  const [connection, setConnection] =
    useState<LiveConnectionState>("connecting");
  const cursor = useRef<string | null>(null);
  const seen = useRef(new Set<string>());

  useEffect(() => {
    const controller = new AbortController();
    let reconnectAttempt = 0;

    const append = (event: ScanEvent) => {
      if (seen.current.has(event.eventId)) return;
      seen.current.add(event.eventId);
      cursor.current = event.eventId;
      setEvents((current) => [...current, event].slice(-MAX_EVENTS));
      notifyWhenHidden(event);
    };

    const connect = async () => {
      while (!controller.signal.aborted) {
        setConnection(reconnectAttempt === 0 ? "connecting" : "reconnecting");
        try {
          const response = await controlServiceFetch(
            `/api/scans/${scanId}/events${
              cursor.current ? `?after=${encodeURIComponent(cursor.current)}` : ""
            }`,
            {
              headers: { Accept: "text/event-stream" },
              signal: controller.signal,
            },
          );
          if (!response.ok || !response.body) {
            throw new Error(`event stream responded ${response.status}`);
          }
          setConnection("live");
          reconnectAttempt = 0;
          await consumeSse(response.body, append, controller.signal);
          if (!controller.signal.aborted) throw new Error("event stream closed");
        } catch {
          if (controller.signal.aborted) break;
          reconnectAttempt += 1;
          await delay(Math.min(1_000 * reconnectAttempt, 5_000), controller.signal);
        }
      }
    };

    void connect();
    return () => {
      controller.abort();
      setConnection("closed");
    };
  }, [scanId]);

  return { events, connection };
}

async function consumeSse(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: ScanEvent) => void,
  signal: AbortSignal,
) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (!signal.aborted) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (data) {
          try {
            onEvent(JSON.parse(data) as ScanEvent);
          } catch {
            // Unknown or partial frames are ignored; replay restores valid events.
          }
        }
        boundary = buffer.indexOf("\n\n");
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function delay(milliseconds: number, signal: AbortSignal) {
  return new Promise<void>((resolve) => {
    const timeout = window.setTimeout(resolve, milliseconds);
    signal.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timeout);
        resolve();
      },
      { once: true },
    );
  });
}

function notifyWhenHidden(event: ScanEvent) {
  if (
    typeof Notification === "undefined" ||
    Notification.permission !== "granted" ||
    document.visibilityState === "visible"
  ) {
    return;
  }
  if (
    ["scan.completed", "scan.failed"].includes(event.type) ||
    (event.type === "finding.created" && event.payload.severity === "critical")
  ) {
    const notificationId = `${event.scanId}:${event.eventId}`;
    if (notifiedEventIds.has(notificationId)) return;
    notifiedEventIds.add(notificationId);
    new Notification("Strix Console", { body: notificationBody(event) });
  }
}

function notificationBody(event: ScanEvent) {
  if (event.type === "scan.completed") return "Scan completed";
  if (event.type === "scan.failed") return "Scan failed";
  return "Critical finding detected";
}
