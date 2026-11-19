---
name: kstack/schedule-ops
version: 1.0.0
role: automation_operator
description: List, create, and audit scheduled automations — cron and webhook triggers bound to governed KFlow executions.
permissions:
  - read
  - execute_restricted
inputs:
  action: list or create
  spec: Schedule definition for create (trigger, cadence, target workflow)
outputs:
  schedules: Registered schedule inventory on list
  schedule_id: Persisted schedule identifier on create
---

# KStack Schedule Ops Skill (Automation Operator Role)

## Overview
Operates `/v1/schedules` — listing registered cron and webhook triggers and creating new schedules bound to governed workflow executions.

## Execution Rules
1. A schedule that mutates workspace state runs under the same P-10 policy as a manual run — automation does not bypass the gate.
2. Webhook triggers are an egress surface; creating one against an unverified endpoint is a finding, not a convenience.
3. Report the persisted `schedule_id` verbatim on create; an unacknowledged create is reported as unconfirmed.
4. Inventory reads reflect the live registry — never answer from a cached list when asked for current schedules.
