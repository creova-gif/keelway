import React, { useId, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";

export interface SlashSkillOption {
  name: string;
  description: string;
}

export const DEFAULT_SLASH_SKILLS: SlashSkillOption[] = [
  { name: "/office-hours", description: "Reframe product scope before writing code" },
  { name: "/review", description: "Pre-landing PR safety & gate integrity review" },
  { name: "/qa", description: "Surface-aware browser, API, and CLI verification" },
  { name: "/investigate", description: "Systematic root-cause debugging" },
  { name: "/ship", description: "Run tests, audit Record chain, and prepare PR" },
];

export interface AgentComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmitPrompt: () => void;
  runtimeReachable: boolean;
  textareaRef?: React.RefObject<HTMLTextAreaElement | null>;
  slashSkills?: SlashSkillOption[];
}

export function AgentComposer({
  value,
  onChange,
  onSubmitPrompt,
  runtimeReachable,
  textareaRef,
  slashSkills = DEFAULT_SLASH_SKILLS,
}: AgentComposerProps): React.JSX.Element {
  const composerId = useId();
  const listboxId = useId();

  const [activeIndex, setActiveIndex] = useState(0);
  const [dismissedForValue, setDismissedForValue] = useState<string | null>(null);

  const slashQuery = useMemo(() => {
    const match = /^\/([^\s]*)$/.exec(value);
    return match ? match[1]!.toLowerCase() : null;
  }, [value]);

  const filteredSkills = useMemo(() => {
    if (slashQuery === null) return [];
    if (slashQuery.length === 0) return slashSkills;
    return slashSkills.filter(
      (item) =>
        item.name.slice(1).toLowerCase().includes(slashQuery) ||
        item.description.toLowerCase().includes(slashQuery),
    );
  }, [slashQuery, slashSkills]);

  const isSlashMenuOpen =
    slashQuery !== null && dismissedForValue !== value && filteredSkills.length > 0;
  const safeActiveIndex =
    filteredSkills.length > 0 ? Math.min(activeIndex, filteredSkills.length - 1) : 0;

  const insertSlashSkill = (skillName: string) => {
    onChange(`${skillName} `);
    setActiveIndex(0);
    setDismissedForValue(null);
    textareaRef?.current?.focus();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && !event.shiftKey && !event.altKey && event.key === "Enter") {
      event.preventDefault();
      event.stopPropagation();
      onSubmitPrompt();
      return;
    }

    if (!isSlashMenuOpen) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((prev) => (prev + 1) % filteredSkills.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((prev) => (prev - 1 + filteredSkills.length) % filteredSkills.length);
    } else if (
      event.key === "Enter" &&
      !event.metaKey &&
      !event.ctrlKey &&
      !event.shiftKey &&
      !event.altKey
    ) {
      event.preventDefault();
      event.stopPropagation();
      const chosen = filteredSkills[safeActiveIndex];
      if (chosen) insertSlashSkill(chosen.name);
    } else if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      setDismissedForValue(value);
    }
  };

  const isSendSoftDisabled = !runtimeReachable || value.trim().length === 0;

  return (
    <div className="relative mt-4 rounded-md border border-border-strong bg-surface p-3">
      {isSlashMenuOpen ? (
        <ul
          id={listboxId}
          role="listbox"
          aria-label="Slash skills"
          className="mb-2 max-h-44 overflow-y-auto rounded-sm border border-border-strong bg-surface-elevated p-1 shadow-popover"
        >
          {filteredSkills.map((skill, idx) => {
            const isSelected = idx === safeActiveIndex;
            return (
              <li
                key={skill.name}
                id={`${listboxId}-opt-${idx}`}
                role="option"
                aria-selected={isSelected}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => insertSlashSkill(skill.name)}
                className={`flex cursor-pointer items-center justify-between gap-2 rounded-xs px-2.5 py-1.5 text-xs ${
                  isSelected
                    ? "bg-teal-surface text-teal-accent"
                    : "text-fg hover:bg-surface"
                }`}
              >
                <code dir="ltr" className="unicode-bidi-isolate font-mono font-semibold">
                  {skill.name}
                </code>
                <span className="truncate text-[11px] text-fg-muted">{skill.description}</span>
              </li>
            );
          })}
        </ul>
      ) : null}

      <label htmlFor={composerId} className="mb-1.5 block text-xs font-medium text-fg-muted">
        Ask agent or follow up in workspace
      </label>
      <textarea
        id={composerId}
        ref={textareaRef}
        rows={2}
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setActiveIndex(0);
          if (dismissedForValue !== null) setDismissedForValue(null);
        }}
        onKeyDown={handleKeyDown}
        placeholder="Describe the change, type / for skills, or cite a file…"
        className="w-full resize-y rounded-sm border border-border-control bg-canvas px-2.5 py-1.5 text-ui text-fg placeholder:text-fg-dim"
      />
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <span className="text-[11px] text-fg-dim">
          ⌘↵ sends prompt only · never approves pending P-10 gates
        </span>
        <Button
          size="sm"
          variant="primary"
          shortcutHint="⌘↵"
          aria-disabled={isSendSoftDisabled ? "true" : undefined}
          onClick={onSubmitPrompt}
        >
          Send
        </Button>
      </div>
    </div>
  );
}
