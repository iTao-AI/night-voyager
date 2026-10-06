interface IntakeControlQueries<T> {
  getByLabel(name: string, options: { exact: true }): T;
  getByRole(role: "combobox", options: { name: string; exact: true }): T;
}

export function intakeFactControl<T>(queries: IntakeControlQueries<T>): T {
  return queries.getByRole("combobox", { name: "要修改的事实", exact: true });
}
