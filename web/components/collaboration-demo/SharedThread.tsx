import type { CollaborationMessage } from "../../lib/collaboration-demo/contracts";

function roleLabel(role: CollaborationMessage["actor_role"]): string {
  return role === "parent" ? "Parent" : role === "student" ? "Student" : "Advisor";
}

export function SharedThread({ messages, loading = false }: { messages: readonly CollaborationMessage[]; loading?: boolean }) {
  return (
    <section className="collaboration-panel shared-thread" aria-labelledby="shared-thread-title">
      <p className="overline">Shared communication record</p>
      <h2 id="shared-thread-title">Shared Case thread</h2>
      {loading ? <p role="status">Loading the server-owned thread…</p> : null}
      {!loading && messages.length === 0 ? <p className="empty-state">No participant messages yet.</p> : null}
      {messages.length > 0 ? (
        <ol className="message-list">
          {messages.map((message) => (
            <li key={message.message_event_id}>
              <p className="message-meta">{roleLabel(message.actor_role)} · message {message.sequence_no}</p>
              <p>{message.body}</p>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
