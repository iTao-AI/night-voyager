"use client";

import type { CollaborationMessage } from "../../lib/collaboration-demo/contracts";
import { presentCode } from "../../lib/presentation/codes";
import { usePresentation } from "../../lib/presentation/context";

export function SharedThread({ messages, loading = false }: { messages: readonly CollaborationMessage[]; loading?: boolean }) {
  const { locale, copy } = usePresentation();
  return (
    <section className="collaboration-panel shared-thread" aria-labelledby="shared-thread-title">
      <p className="overline">{copy("threadOverline")}</p>
      <h2 id="shared-thread-title">{copy("threadTitle")}</h2>
      {loading ? <p role="status">{copy("threadLoading")}</p> : null}
      {!loading && messages.length === 0 ? <p className="empty-state">{copy("threadEmpty")}</p> : null}
      {messages.length > 0 ? (
        <ol className="message-list">
          {messages.map((message) => (
            <li key={message.message_event_id}>
              <p className="message-meta">{presentCode(locale, "role", message.actor_role)} · {copy("messageSequenceLabel")} {message.sequence_no}</p>
              <p>{message.body}</p>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
