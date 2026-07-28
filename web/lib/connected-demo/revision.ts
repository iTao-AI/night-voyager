import type {
  ConfirmedFactAdvisor,
  ConfirmedFactParticipant,
  MemoryCandidateAdvisor,
  MemoryCandidateParticipant,
} from "../collaboration-demo/contracts";
import type { Country } from "./contracts";

export const REVISED_PREFERRED_COUNTRIES: readonly Country[] = ["australia", "japan"];
export const REVISION_PROPOSAL_MESSAGE =
  "For this synthetic planning revision, I propose Australia and Japan as my preferred countries.";

export function preferredCountriesFact(
  facts: readonly (ConfirmedFactAdvisor | ConfirmedFactParticipant)[],
): ConfirmedFactAdvisor | ConfirmedFactParticipant | null {
  const matches = facts.filter((fact) => fact.fact_key === "student.preferred_countries");
  return matches.length === 1 ? matches[0] : null;
}

export function pendingPreferredCountriesCandidate(
  candidates: readonly (MemoryCandidateAdvisor | MemoryCandidateParticipant)[],
): MemoryCandidateAdvisor | MemoryCandidateParticipant | null {
  const matches = candidates.filter(
    (candidate) =>
      candidate.fact_key === "student.preferred_countries"
      && candidate.state === "pending"
      && JSON.stringify(candidate.value) === JSON.stringify(REVISED_PREFERRED_COUNTRIES),
  );
  return matches.length === 1 ? matches[0] : null;
}
