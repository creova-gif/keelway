import React, { useId } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Button } from "@/components/ui/Button";
import type { MintedScopedApiKeyResult } from "@/lib/types";

const AVAILABLE_SCOPES = ["audit:read", "models:read", "routing:explain", "eval:run"] as const;

export interface SettingsKeyMintModalProps {
  open: boolean;
  onOpen: () => void;
  onRequestClose: () => void;
  keyLabel: string;
  onKeyLabelChange: (val: string) => void;
  selectedScopes: string[];
  onSelectedScopesChange: React.Dispatch<React.SetStateAction<string[]>>;
  keySpendCap: number;
  onKeySpendCapChange: (val: number) => void;
  minting: boolean;
  mintedResult: MintedScopedApiKeyResult | null;
  savedKeyChecked: boolean;
  onSavedKeyCheckedChange: (checked: boolean) => void;
  copiedSecret: boolean;
  onCopySecret: () => void;
  onSubmitMint: (event: React.FormEvent) => void;
}

export function SettingsKeyMintModal({
  open,
  onOpen,
  onRequestClose,
  keyLabel,
  onKeyLabelChange,
  selectedScopes,
  onSelectedScopesChange,
  keySpendCap,
  onKeySpendCapChange,
  minting,
  mintedResult,
  savedKeyChecked,
  onSavedKeyCheckedChange,
  copiedSecret,
  onCopySecret,
  onSubmitMint,
}: SettingsKeyMintModalProps): React.JSX.Element {
  const mintDescId = useId();
  const keyLabelId = useId();
  const keyCapId = useId();
  const savedKeyId = useId();
  const doneHelperId = useId();

  const isDismissBlocked = minting || Boolean(mintedResult && !savedKeyChecked);

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          if (!isDismissBlocked) onRequestClose();
        } else {
          onOpen();
        }
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <Dialog.Content
          aria-describedby={mintDescId}
          onEscapeKeyDown={(e) => {
            if (isDismissBlocked) e.preventDefault();
          }}
          onPointerDownOutside={(e) => {
            if (isDismissBlocked) e.preventDefault();
          }}
          onInteractOutside={(e) => {
            if (isDismissBlocked) e.preventDefault();
          }}
          className="fixed start-1/2 top-[12%] z-50 flex w-full max-w-lg -translate-x-1/2 flex-col overflow-hidden rounded-md border border-border-strong bg-surface text-fg shadow-modal rtl:translate-x-1/2"
        >
          <div className="border-b border-border bg-chrome px-4 py-3">
            <Dialog.Title className="text-sm font-semibold text-fg">
              Mint scoped key
            </Dialog.Title>
            <Dialog.Description id={mintDescId} className="mt-0.5 text-xs text-fg-muted">
              {mintedResult
                ? "One-time secret reveal — copy and confirm before closing."
                : "Issue a least-privilege tenant key with a dedicated USD spend cap."}
            </Dialog.Description>
          </div>

          {!mintedResult ? (
            <form onSubmit={onSubmitMint} className="space-y-3.5 p-4 text-xs">
              <div className="space-y-1">
                <label htmlFor={keyLabelId} className="block font-medium text-fg">
                  Key label
                </label>
                <input
                  id={keyLabelId}
                  type="text"
                  value={keyLabel}
                  onChange={(e) => onKeyLabelChange(e.target.value)}
                  className="min-h-ctrl-sm w-full rounded-xs border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg"
                />
              </div>

              <fieldset className="space-y-1.5">
                <legend className="font-medium text-fg">Allowed scopes</legend>
                <div className="grid grid-cols-2 gap-2 rounded-sm border border-border bg-canvas p-2.5">
                  {AVAILABLE_SCOPES.map((scope) => {
                    const checked = selectedScopes.includes(scope);
                    return (
                      <label key={scope} className="flex items-center gap-2 font-mono text-xs text-fg">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => {
                            onSelectedScopesChange((prev) =>
                              e.target.checked
                                ? [...prev, scope]
                                : prev.filter((s) => s !== scope),
                            );
                          }}
                          className="h-3.5 w-3.5 accent-teal-accent"
                        />
                        <code dir="ltr" className="unicode-bidi-isolate">
                          {scope}
                        </code>
                      </label>
                    );
                  })}
                </div>
              </fieldset>

              <div className="space-y-1">
                <label htmlFor={keyCapId} className="block font-medium text-fg">
                  Spend cap ($ USD)
                </label>
                <input
                  id={keyCapId}
                  type="number"
                  min={1}
                  step="any"
                  value={keySpendCap}
                  onChange={(e) => onKeySpendCapChange(Math.max(1, Number(e.target.value) || 1))}
                  className="min-h-ctrl-sm w-40 rounded-xs border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs tabular-nums text-fg"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={minting}
                  onClick={() => {
                    if (!isDismissBlocked) onRequestClose();
                  }}
                >
                  Cancel
                </Button>
                <Button type="submit" size="sm" variant="primary" loading={minting}>
                  Generate scoped key
                </Button>
              </div>
            </form>
          ) : (
            <div className="space-y-3.5 p-4 text-xs">
              <p className="rounded-sm border border-warning bg-warning-subtle px-3 py-2 text-fg">
                {mintedResult.oneTimeWarning}
              </p>

              <div className="flex items-center justify-between gap-2 rounded-sm border border-border-strong bg-code p-2.5">
                <code
                  dir="ltr"
                  data-testid="minted-plaintext-secret"
                  className="unicode-bidi-isolate break-all font-mono text-xs font-semibold text-teal-accent"
                >
                  {mintedResult.plaintextSecret}
                </code>
                <Button size="sm" variant="secondary" onClick={onCopySecret}>
                  {copiedSecret ? "Copied" : "Copy key"}
                </Button>
              </div>

              <div className="flex items-center gap-2 rounded-sm border border-border bg-canvas px-3 py-2">
                <input
                  id={savedKeyId}
                  type="checkbox"
                  checked={savedKeyChecked}
                  onChange={(e) => onSavedKeyCheckedChange(e.target.checked)}
                  className="h-4 w-4 accent-teal-accent"
                />
                <label htmlFor={savedKeyId} className="font-medium text-fg">
                  I have saved this key
                </label>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                <span id={doneHelperId} className="text-[11px] text-fg-muted">
                  {savedKeyChecked
                    ? "Secret saved confirmation recorded."
                    : "Confirm you have saved this key before closing"}
                </span>
                <Button
                  size="sm"
                  variant="primary"
                  aria-disabled={!savedKeyChecked}
                  aria-describedby={doneHelperId}
                  onClick={() => {
                    if (!savedKeyChecked) return;
                    onRequestClose();
                  }}
                >
                  Done
                </Button>
              </div>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
