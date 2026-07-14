import { expect, it } from "vitest";

import { loadRecoveryMetadata, saveRecoveryMetadata } from "../../lib/connected-demo/session-storage";

it("fails closed when recovery metadata is missing or inconsistent", () => {
  expect(loadRecoveryMetadata()).toBeNull();
  sessionStorage.setItem("night-voyager:m5", JSON.stringify({ role: "parent" }));
  expect(loadRecoveryMetadata()).toBeNull();
});

it("stores only same-tab display and mutation recovery metadata", () => {
  saveRecoveryMetadata({
    role: "advisor",
    csrf: "csrf",
    caseId: "40000000-0000-0000-0000-000000000002",
    taskId: null,
    briefId: null,
    cursor: 0,
  });
  expect(loadRecoveryMetadata()?.role).toBe("advisor");
  expect(localStorage.length).toBe(0);
});
