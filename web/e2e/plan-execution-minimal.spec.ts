import { expect, test, type Page, type Response } from "@playwright/test";

const scenario = "governed-plan-execution-v1";
const minimalProof = process.env.PLAN_EXECUTION_MINIMAL_PROOF === "1";

type Receipt = {
  schema_version: number;
  result_id: string;
  execution_id: string;
};

type ExecutionView = {
  schema_version: number;
  execution: { execution_id: string; state: string };
  latest_attestation: { attestation_id: string } | null;
  latest_verification: { verification_id: string } | null;
};

async function clickMutationAndRead(
  page: Page,
  buttonName: string,
  mutationPath: string,
  resultField: "execution" | "attestation" | "verification",
): Promise<ExecutionView> {
  const button = page.getByRole("button", { name: buttonName, exact: true });
  await expect(button).toBeEnabled();

  const responseOrder: string[] = [];
  const observe = (response: Response) => {
    const request = response.request();
    if (request.method() === "POST" && response.url().includes(mutationPath)) {
      responseOrder.push("receipt");
    }
    if (
      request.method() === "GET"
      && response.url().includes("/api/demo/cases/")
      && response.url().endsWith("/timeline-execution")
    ) {
      responseOrder.push("fresh-read");
    }
  };
  page.on("response", observe);
  const receiptResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST"
      && response.url().includes(mutationPath),
  );
  const readResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "GET"
      && response.url().includes("/api/demo/cases/")
      && response.url().endsWith("/timeline-execution"),
  );
  await button.click();
  const [receiptHttp, readHttp] = await Promise.all([
    receiptResponse,
    readResponse,
  ]);
  expect(receiptHttp.status()).toBe(200);
  expect(readHttp.status()).toBe(200);
  await expect.poll(() => responseOrder).toEqual(["receipt", "fresh-read"]);
  page.off("response", observe);

  const receipt = (await receiptHttp.json()) as Receipt;
  const view = (await readHttp.json()) as ExecutionView;
  expect(receipt.schema_version).toBe(1);
  expect(view.schema_version).toBe(1);
  expect(view.execution.execution_id).toBe(receipt.execution_id);
  if (resultField === "execution") {
    expect(receipt.result_id).toBe(view.execution.execution_id);
  } else if (resultField === "attestation") {
    expect(view.latest_attestation?.attestation_id).toBe(receipt.result_id);
  } else {
    expect(view.latest_verification?.verification_id).toBe(receipt.result_id);
  }
  return view;
}

async function expectCheckpoint(
  page: Page,
  milestone: string,
  dueDate: string,
  role: "Student" | "Parent",
) {
  const authoritySummary = page.locator("[data-plan-authority-summary]");
  await expect(authoritySummary).toBeVisible();
  await expect(authoritySummary).toContainText(milestone);
  await expect(authoritySummary).toContainText(dueDate);
  await expect(authoritySummary).toContainText(role);
}

async function expectLiveAndVisibleCopy(page: Page, message: string) {
  await expect(page.getByRole("status")).toHaveText(message);
  await expect(page.locator("[data-frame-slot='work'] .workspace-status-copy")).toHaveText(message);
}

test("minimal governed plan execution reaches completed through one bilingual journey", async ({
  page,
}) => {
  test.skip(!minimalProof, "runs only in the dedicated minimal execution lane");
  await page.goto("/demo/plan");
  await expect(page.locator(".advisor-workspace-shell")).toHaveAttribute(
    "data-proof-segment",
    "independent_execution_scenario",
  );
  await expect(page.locator("[data-frame-slot='top-band']")).toContainText(
    /独立演示场景，不沿用当前客户档案。|Independent demo scenario; it does not reuse the current client case\./,
  );
  await expect(page.getByRole("heading", { name: "当前行动" })).toBeVisible();
  await page.getByRole("button", { name: "学生", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "开始执行行动计划", exact: true }),
  ).toBeEnabled();

  await page.getByRole("button", { name: "English", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Current action" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Start the action plan", exact: true }),
  ).toBeEnabled();

  const contextResponse = await page.request.get("/api/demo/plan-execution-context");
  expect(contextResponse.status()).toBe(200);
  expect((await contextResponse.json()).scenario).toBe(scenario);

  await clickMutationAndRead(
    page,
    "Start the action plan",
    "/api/demo/timeline-plans/",
    "execution",
  );

  const checkpoints = [
    ["Documents", "2026-09-01", "Student"],
    ["Application", "2026-10-15", "Student"],
    ["Visa", "2026-12-15", "Student"],
    ["Arrival", "2027-01-20", "Parent"],
  ] as const;
  for (const [index, [milestone, dueDate, role]] of checkpoints.entries()) {
    if (index > 0) {
      await page.getByRole("button", {
        name: role,
        exact: true,
      }).click();
    }
    await expectCheckpoint(page, milestone, dueDate, role);
    await clickMutationAndRead(
      page,
      "Submit completion to advisor",
      "/checkpoint-attestations",
      "attestation",
    );
    await expectLiveAndVisibleCopy(
      page,
      "Family view: waiting for the assigned advisor to verify.",
    );

    await page.getByRole("button", { name: "Advisor", exact: true }).click();
    const view = await clickMutationAndRead(
      page,
      "Verify and continue",
      "/checkpoint-verifications",
      "verification",
    );
    if (index < checkpoints.length - 1) {
      expect(view.execution.state).toBe("active");
    } else {
      expect(view.execution.state).toBe("completed");
    }
  }

  await expectLiveAndVisibleCopy(page, "The action plan is complete.");
  await expect(page.getByText("There is no current checkpoint.")).toBeVisible();
});
