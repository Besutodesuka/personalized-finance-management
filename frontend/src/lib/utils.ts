export const fmt = (n: number) =>
  (n ?? 0).toLocaleString('th-TH', { minimumFractionDigits: 0, maximumFractionDigits: 0 })

export const pct = (spent: number, budget: number) =>
  budget ? Math.min(100, Math.round((spent / budget) * 100)) : 0
