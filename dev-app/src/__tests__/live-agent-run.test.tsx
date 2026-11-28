import React from "react";
import { describe, expect, it, vi, afterEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TasksWorkspace } from "@/components/screens/TasksWorkspace";
import "@/styles/tokens.css";
import { axe } from "@/test/setup";

const BASE_STATE = {
  task_id: "task-live-1",
  goal: "Audit CSP headers",
  status: "awaiting_steps",
  policy: "confirm_mutation",
  plan: [
    { id: "s1", description: "Inspect loopback CSP", status: "pending", observation: null },
    { id: "s2", description: "Patch header", status: "pending", observation: null },
  ],
  pending_approval: null,
  events_count: 1,
  recent_events: [
    { timestamp: 1700000000, event_type: "plan_initialized", data: { steps: 2 } },
  ],
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Builds a fetch mock that routes on the /v1/agent/* path suffix. */
function mockAgentFetch(routes: Record<string, { body: unknown; status?: number }>) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    calls.push({
      url,
      method: init?.method ?? "GET",
      body: init?.body ? JSON.parse(init.body as string) : undefined,
    });
    const path = url.split("?")[0]!;
    const hit = Object.entries(routes).find(([suffix]) => path.endsWith(suffix));
    if (!hit) return jsonResponse({ detail: `unmocked ${path}` }, 404);
    return jsonResponse(hit[1].body, hit[1].status ?? 200);
  });
  return { fetchMock, calls };
}

async function submitPrompt(prompt: string) {
  const user = userEvent.setup();
  const composer = screen.getByRole("textbox", { name: /Ask agent|Instruction|Composer/i });
  await user.click(composer);
  await user.type(composer, prompt);
  fireEvent.keyDown(composer, { key: "Enter", metaKey: true });
}

describe("TasksWorkspace live agent run lane", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("composer submit calls POST /v1/agent/run and hydrates the backend plan", async () => {
    const { fetchMock, calls } = mockAgentFetch({
      "/v1/agent/run": { body: { task_id: "task-live-1", goal: "Audit CSP headers", policy: "confirm_mutation", state: BASE_STATE } },
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<TasksWorkspace taskId="task-ui" taskTitle="UI task" />);
    await submitPrompt("Audit CSP headers");

    await waitFor(() => {
      expect(screen.getByTestId("live-agent-run")).toBeInTheDocument();
    });
    expect(calls.some((c) => c.url.startsWith("/v1/agent/run") && c.method === "POST" && (c.body as Record<string, unknown>).goal === "Audit CSP headers")).toBe(true);
    // Backend plan rows replace the static DEFAULT_PLAN_STEPS.
    expect(screen.getByText(/Inspect loopback CSP/)).toBeInTheDocument();
    expect(screen.getByText(/Patch header/)).toBeInTheDocument();
    expect(screen.getByText(/1 events · policy confirm_mutation/)).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Run step calls POST /v1/agent/step and renders live tool events as receipts", async () => {
    const steppedState = {
      ...BASE_STATE,
      events_count: 3,
      recent_events: [
        ...BASE_STATE.recent_events,
        { timestamp: 1700000001, event_type: "tool_call", data: { tool: "read_file", arguments: { path: "core/main.py" } } },
        { timestamp: 1700000002, event_type: "tool_success", data: { tool: "read_file", arguments: { path: "core/main.py" }, duration_ms: 42, result: { stdout: "app = FastAPI()" } } },
      ],
    };
    const { fetchMock, calls } = mockAgentFetch({
      "/v1/agent/run": { body: { task_id: "task-live-1", goal: "g", policy: "confirm_mutation", state: BASE_STATE } },
      "/v1/agent/step/task-live-1": { body: { step_result: { status: "completed" }, agent_state: steppedState } },
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<TasksWorkspace taskId="task-ui" taskTitle="UI task" />);
    await submitPrompt("Audit CSP headers");
    await waitFor(() => expect(screen.getByTestId("live-agent-run")).toBeInTheDocument());

    const toolSelect = screen.getByLabelText(/Step tool/i);
    fireEvent.change(toolSelect, { target: { value: "read_file" } });
    const argsInput = screen.getByLabelText(/Tool arguments/i);
    fireEvent.change(argsInput, { target: { value: '{"path":"core/main.py"}' } });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Run step/i }));

    await waitFor(() => {
      expect(calls.some((c) => c.url.includes("/v1/agent/step/task-live-1") && c.method === "POST")).toBe(true);
    });
    const stepCall = calls.find((c) => c.url.includes("/v1/agent/step/"));
    expect((stepCall!.body as Record<string, unknown>).tool_name).toBe("read_file");
    await waitFor(() => {
      expect(screen.getByText("Live execution events")).toBeInTheDocument();
      expect(screen.getByText(/read_file succeeded/)).toBeInTheDocument();
    });
    expect(await axe(container)).toHaveNoViolations();
  });

  it("pending_approval maps to a P-10 card and Allow once posts approved:true", async () => {
    const heldState = {
      ...BASE_STATE,
      status: "awaiting_approval",
      pending_approval: {
        task_id: "task-live-1",
        tool_name: "edit_file",
        arguments: { path: "core/main.py", target: "a", replacement: "b" },
        is_mutation: true,
        step_id: "s2",
      },
    };
    const approvedState = { ...heldState, status: "awaiting_steps", pending_approval: null };
    const { fetchMock, calls } = mockAgentFetch({
      "/v1/agent/run": { body: { task_id: "task-live-1", goal: "g", policy: "confirm_mutation", state: heldState } },
      "/v1/agent/approve/task-live-1": { body: { approval_result: { status: "executed" }, agent_state: approvedState } },
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<TasksWorkspace taskId="task-ui" taskTitle="UI task" />);
    await submitPrompt("Audit CSP headers");

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Allow once/i })).toBeInTheDocument();
    });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Allow once/i }));

    await waitFor(() => {
      expect(calls.some((c) => c.url.includes("/v1/agent/approve/task-live-1") && c.method === "POST")).toBe(true);
    });
    const approveCall = calls.find((c) => c.url.includes("/v1/agent/approve/"));
    expect((approveCall!.body as Record<string, unknown>).approved).toBe(true);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Deny posts approved:false to the approve endpoint", async () => {
    const heldState = {
      ...BASE_STATE,
      status: "awaiting_approval",
      pending_approval: {
        task_id: "task-live-1",
        tool_name: "run_command",
        arguments: { command: "rm -rf /" },
        is_mutation: true,
      },
    };
    const deniedState = { ...heldState, status: "awaiting_steps", pending_approval: null };
    const { fetchMock, calls } = mockAgentFetch({
      "/v1/agent/run": { body: { task_id: "task-live-1", goal: "g", policy: "confirm_mutation", state: heldState } },
      "/v1/agent/approve/task-live-1": { body: { approval_result: { status: "denied" }, agent_state: deniedState } },
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<TasksWorkspace taskId="task-ui" taskTitle="UI task" />);
    await submitPrompt("Audit CSP headers");
    await waitFor(() => expect(screen.getByRole("button", { name: /^Deny$/i })).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /^Deny$/i }));

    await waitFor(() => {
      const approveCall = calls.find((c) => c.url.includes("/v1/agent/approve/"));
      expect(approveCall).toBeDefined();
      expect((approveCall!.body as Record<string, unknown>).approved).toBe(false);
    });
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Cancel run calls POST /v1/agent/cancel and reflects cancelled status", async () => {
    const cancelledState = { ...BASE_STATE, status: "cancelled" };
    const { fetchMock, calls } = mockAgentFetch({
      "/v1/agent/run": { body: { task_id: "task-live-1", goal: "g", policy: "confirm_mutation", state: BASE_STATE } },
      "/v1/agent/cancel/task-live-1": { body: { agent_state: cancelledState } },
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<TasksWorkspace taskId="task-ui" taskTitle="UI task" />);
    await submitPrompt("Audit CSP headers");
    await waitFor(() => expect(screen.getByTestId("live-agent-run")).toBeInTheDocument());

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Cancel run/i }));
    await waitFor(() => {
      expect(calls.some((c) => c.url.includes("/v1/agent/cancel/task-live-1") && c.method === "POST")).toBe(true);
      expect(screen.getByText("cancelled")).toBeInTheDocument();
    });
    expect(await axe(container)).toHaveNoViolations();
  });

  it("failed run POST logs an honest error and never shows fabricated state", async () => {
    const { fetchMock } = mockAgentFetch({
      "/v1/agent/run": { body: { detail: "RBAC: runs:write required" }, status: 403 },
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<TasksWorkspace taskId="task-ui" taskTitle="UI task" />);
    await submitPrompt("Audit CSP headers");
    // Live lane must NOT appear on rejection — no fake success.
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByTestId("live-agent-run")).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });
});
