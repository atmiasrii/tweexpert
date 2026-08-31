import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../lib/api";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function Schedule() {
  const qc = useQueryClient();
  const s = useQuery({ queryKey: ["schedule"], queryFn: () => api.get("/api/schedule") });
  const [hour, setHour] = useState(9);
  const [wd, setWd] = useState(0);
  const addSlot = useMutation({
    mutationFn: () => api.post("/api/schedule/slots", { weekday: wd, hour, minute: 0, category: "" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedule"] }),
  });
  const slots: any[] = s.data?.slots ?? [];
  const queued: any[] = s.data?.queued ?? [];
  return (
    <div className="max-w-3xl space-y-4">
      <section>
        <div className="text-sm text-muted mb-2">Weekly slots (C-04)</div>
        <div className="grid grid-cols-7 gap-1 text-xs">
          {DAYS.map((d, i) => (
            <div key={d} className="border border-rule p-1 min-h-16">
              <div className="text-muted mb-1">{d}</div>
              {slots.filter((sl) => sl.weekday === i).map((sl) => (
                <div key={sl.id} className="bg-accent text-white px-1 mb-0.5">{String(sl.hour).padStart(2, "0")}:{String(sl.minute).padStart(2, "0")}</div>
              ))}
            </div>
          ))}
        </div>
        <div className="flex gap-2 mt-2 text-sm items-center">
          <select value={wd} onChange={(e) => setWd(+e.target.value)} className="border border-rule bg-transparent px-2 py-1">
            {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
          </select>
          <input type="number" min={0} max={23} value={hour} onChange={(e) => setHour(+e.target.value)}
            className="w-16 border border-rule bg-transparent px-2 py-1" />
          <button onClick={() => addSlot.mutate()} className="px-3 py-1 border border-rule">add slot</button>
        </div>
      </section>
      <section>
        <div className="text-sm text-muted mb-2">Queued posts · evergreen pulled when slots run dry (C-06)</div>
        <ul className="space-y-1">
          {queued.map((q) => (
            <li key={q.id} className="border border-rule bg-[var(--surface)] p-2 text-sm flex justify-between">
              <span className="tweet">{q.text}</span>
              <span className="text-muted text-xs ml-2">{q.evergreen ? "evergreen" : q.category || "—"}</span>
            </li>
          ))}
          {queued.length === 0 && <li className="text-muted text-sm">nothing queued</li>}
        </ul>
      </section>
    </div>
  );
}
