import { useEffect, useState } from "react";
import { api } from "../../api";
import type { Goal, Paginated } from "../../types";

/** the company's goals + the set of task ids under them, refreshed on an interval */
export function useCompanyScope(companyId: string, everyMs = 5000) {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api<Paginated<Goal>>(`/goals/?company=${companyId}&limit=200`)
        .then((d) => {
          if (!alive) return;
          setGoals(d.results);
          setReady(true);
        })
        .catch(() => {});
    load();
    const t = setInterval(load, everyMs);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [companyId, everyMs]);

  const taskIds = new Set(goals.flatMap((g) => g.tasks.map((t) => t.id)));
  const goalIds = new Set(goals.map((g) => g.id));
  return { goals, taskIds, goalIds, ready };
}
