export interface ReceiptRow {
  id: string;
  action: string;
  target: string;
  route: string;
  state: "sealed" | "awaiting";
}

export function ReceiptTable({ rows, caption }: { rows: ReceiptRow[]; caption: string }) {
  return (
    <figure>
      <div className="overflow-hidden rounded-md border border-border">
        <table className="w-full font-mono text-[12px]">
          <thead>
            <tr className="border-b border-border text-left text-[10px] uppercase tracking-[0.16em] text-fg-muted">
              <th className="px-4 py-2.5 font-medium">ID</th>
              <th className="px-4 py-2.5 font-medium">Action</th>
              <th className="px-4 py-2.5 font-medium">Target</th>
              <th className="px-4 py-2.5 font-medium">Route</th>
              <th className="px-4 py-2.5 text-right font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r) => (
              <tr key={r.id} className="transition-colors hover:bg-surface">
                <td className="px-4 py-2.5 text-fg-muted">{r.id}</td>
                <td className="px-4 py-2.5 text-fg">{r.action}</td>
                <td className="px-4 py-2.5 text-fg">{r.target}</td>
                <td className="px-4 py-2.5 text-fg-muted">{r.route}</td>
                <td className={`px-4 py-2.5 text-right ${r.state === "sealed" ? "text-ok" : "text-accent"}`}>
                  {r.state}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <figcaption className="mt-3 font-mono text-[10px] uppercase tracking-[0.18em] text-fg-muted">
        {caption}
      </figcaption>
    </figure>
  );
}
