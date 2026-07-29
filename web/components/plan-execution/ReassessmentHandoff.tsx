import type { TimelineReassessment } from "../../lib/plan-execution/contracts";

export function ReassessmentHandoff({
  reassessment,
  labels,
}: {
  reassessment: TimelineReassessment;
  labels: {
    title: string;
    stop: string;
    pending: string;
    whoNext: string;
    blockedTrigger: string;
    deadlineTrigger: string;
  };
}) {
  return (
    <section aria-labelledby="reassessment-handoff-title">
      <h2 id="reassessment-handoff-title">{labels.title}</h2>
      <p>{labels.stop}</p>
      <p>{labels.pending}</p>
      <p>{labels.whoNext}</p>
      <p>{reassessment.trigger === "blocked_attestation"
        ? labels.blockedTrigger
        : labels.deadlineTrigger}</p>
    </section>
  );
}
