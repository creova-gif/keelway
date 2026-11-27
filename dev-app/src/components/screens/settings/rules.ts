import type { ApprovalRuleItem } from "@/lib/types";

export const CURRENT_PROMPT_VERSION = "p-14";

export function isRuleDrifted(
  rule: ApprovalRuleItem,
  activeModelId: string | undefined,
  currentPromptVersion: string,
): boolean {
  if (rule.boundPromptVersion && rule.boundPromptVersion !== currentPromptVersion) return true;
  return Boolean(rule.boundModelId && activeModelId && rule.boundModelId !== activeModelId);
}
