import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

export function Analytics() {
  const posts = useQuery({ queryKey: ["an-posts"], queryFn: () => api.get("/api/analytics/posts") });
  const replies = useQuery({ queryKey: ["an-replies"], queryFn: () => api.get("/api/analytics/replies") });
  const followers = useQuery({ queryKey: ["an-followers"], queryFn: () => api.get("/api/analytics/followers") });
  const rate = useQuery({ queryKey: ["an-rate"], queryFn: () => api.get("/api/analytics/approval-rate") });
  const series: any[] = followers.data?.series ?? [];
  return (
    <div className="max-w-3xl space-y-5">
      <section>
        <div className="text-sm text-muted mb-2">Post performance (M-02)</div>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-muted border-b border-rule">
            <th className="py-1">post</th><th>kind</th><th>len</th><th>likes</th><th>views</th></tr></thead>
          <tbody>
            {(posts.data ?? []).map((p: any) => (
              <tr key={p.x_post_id} className="border-b border-rule">
                <td className="py-1.5 max-w-xs truncate">{p.text}</td>
                <td>{p.kind}</td><td>{p.length}</td><td>{p.likes}</td><td>{p.views}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section>
        <div className="text-sm text-muted mb-2">Reply outcomes by angle (M-03)</div>
        <ul className="text-sm space-y-1">
          {(replies.data ?? []).map((r: any, i: number) => (
            <li key={i} className="text-muted">{r.angle}: {r.count ?? 0} sent</li>
          ))}
        </ul>
      </section>
      <section>
        <div className="text-sm text-muted mb-2">Followers (M-04) · approval rate (L-05)</div>
        <div className="text-sm">latest followers: <b>{series.at(-1)?.count ?? "—"}</b></div>
        <div className="text-sm text-muted">approval-rate points: {(rate.data?.series ?? []).length}</div>
      </section>
    </div>
  );
}
