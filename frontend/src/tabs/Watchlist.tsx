import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../lib/api";

export function Watchlist() {
  const qc = useQueryClient();
  const accts = useQuery({ queryKey: ["accounts"], queryFn: () => api.get("/api/accounts") });
  const [handle, setHandle] = useState("");
  const [tier, setTier] = useState("B");
  const add = useMutation({ mutationFn: () => api.post("/api/accounts", { handle, tier }),
    onSuccess: () => { setHandle(""); qc.invalidateQueries({ queryKey: ["accounts"] }); } });
  const setMode = useMutation({
    mutationFn: (b: { id: number; mode: string }) => api.post(`/api/accounts/${b.id}/mode`, { mode: b.mode }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
    onError: (e: any) => alert(e.message),
  });
  const list: any[] = accts.data ?? [];
  return (
    <div className="max-w-3xl space-y-3">
      <div className="flex gap-2 text-sm">
        <input value={handle} onChange={(e) => setHandle(e.target.value)} placeholder="handle"
          className="flex-1 px-2 py-1.5 border border-rule bg-transparent" />
        <select value={tier} onChange={(e) => setTier(e.target.value)} className="border border-rule bg-transparent px-2">
          <option>A</option><option>B</option><option>C</option>
        </select>
        <button onClick={() => add.mutate()} className="px-3 border border-rule">watch</button>
      </div>
      <table className="w-full text-sm">
        <thead><tr className="text-left text-muted border-b border-rule">
          <th className="py-1">handle</th><th>tier</th><th>mode</th><th>drafts</th></tr></thead>
        <tbody>
          {list.map((a) => (
            <tr key={a.id} className="border-b border-rule">
              <td className="py-2">@{a.handle}</td>
              <td>{a.tier}</td>
              <td>
                <select value={a.mode} onChange={(e) => {
                  if (e.target.value === "auto" && !a.shadow_complete) {
                    if (!confirm("Auto requires the shadow period complete. Caps: 4 auto replies/day. Continue?")) return;
                  }
                  setMode.mutate({ id: a.id, mode: e.target.value });
                }} className="border border-rule bg-transparent px-1 py-0.5">
                  <option value="shadow">shadow</option>
                  <option value="assisted">assisted</option>
                  <option value="auto" disabled={!a.shadow_complete}>auto{a.shadow_complete ? "" : " (locked)"}</option>
                </select>
              </td>
              <td>{a.draft_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
