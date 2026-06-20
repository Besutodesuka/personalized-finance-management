'use client'
import { useState, useEffect, useCallback } from 'react'
import { Doughnut, Bar } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
} from 'chart.js'
import { api } from '@/lib/api'
import { Dashboard, Wallet, Category, Expense } from '@/lib/types'
import { fmt, pct } from '@/lib/utils'
import Modal from '@/components/Modal'
import WalletTag from '@/components/WalletTag'

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement)

export default function DashboardPage() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [wallets, setWallets] = useState<Wallet[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7))
  const [modal, setModal] = useState<{ open: boolean; type: 'planned' | 'unexpected' }>({
    open: false,
    type: 'planned',
  })
  const [selectedWalletId, setSelectedWalletId] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async (m: string) => {
    setLoading(true)
    try {
      const [w, c, d] = await Promise.all([
        api.get<Wallet[]>('/wallets'),
        api.get<Category[]>('/categories'),
        api.get<Dashboard>(`/dashboard?month=${m}`),
      ])
      setWallets(w)
      setCategories(c)
      setDashboard(d)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load(month) }, [month, load])

  const openModal = (type: 'planned' | 'unexpected') => {
    setSelectedWalletId('')
    setModal({ open: true, type })
  }

  const submitExpense = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    const body: Omit<Expense, 'id'> = {
      date: fd.get('date') as string,
      description: fd.get('description') as string,
      amount: parseFloat(fd.get('amount') as string),
      wallet_id: fd.get('wallet_id') as string,
      category_id: fd.get('category_id') as string,
      type: modal.type,
    }
    await api.post('/expenses', body)
    setModal({ open: false, type: 'planned' })
    load(month)
  }

  const filteredCats = categories.filter(c => !selectedWalletId || c.wallet_id === selectedWalletId)

  if (loading && !dashboard) return <p className="text-gray-500">Loading…</p>
  const d = dashboard

  return (
    <div className="space-y-6">
      {/* Today card */}
      <div className="bg-indigo-600 text-white rounded-xl p-6 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold opacity-80">Today · {new Date().toISOString().slice(0, 10)}</h2>
          <div className="text-4xl font-bold mt-1">฿{fmt(d?.today_spent ?? 0)}</div>
          <div className="opacity-70 text-sm mt-1">
            {d?.today_count ?? 0} transaction{d?.today_count !== 1 ? 's' : ''} today
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn bg-white/20 hover:bg-white/30 text-white" onClick={() => openModal('planned')}>
            + Planned
          </button>
          <button className="btn bg-white/20 hover:bg-white/30 text-white" onClick={() => openModal('unexpected')}>
            ⚡ Unexpected
          </button>
        </div>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <input
          type="month"
          value={month}
          onChange={(e) => setMonth(e.target.value)}
          className="form-input w-auto"
        />
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {[
          { label: 'Total Budget', value: `฿${fmt(d?.total_budget ?? 0)}`, cls: '' },
          { label: 'Spent', value: `฿${fmt(d?.total_spent ?? 0)}`, cls: 'text-red-600' },
          {
            label: 'Remaining',
            value: `฿${fmt(d?.total_remaining ?? 0)}`,
            cls: (d?.total_remaining ?? 0) >= 0 ? 'text-emerald-600' : 'text-red-600',
          },
          { label: 'Daily Avg', value: `฿${fmt(d?.daily_average ?? 0)}`, cls: '' },
          { label: 'Subscriptions', value: `฿${fmt(d?.subscription_total ?? 0)}`, cls: 'text-amber-600' },
          { label: 'Unexpected', value: `${d?.unexpected_count ?? 0} events`, cls: '' },
        ].map(({ label, value, cls }) => (
          <div key={label} className="stat-card">
            <div className="text-sm text-gray-500">{label}</div>
            <div className={`text-xl font-bold mt-1 ${cls}`}>{value}</div>
          </div>
        ))}
      </div>

      {/* Wallet progress + doughnut */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Wallet Progress</h2>
          <div className="space-y-4">
            {d?.wallet_breakdown.map((wb) => (
              <div key={wb.wallet.id}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium">{wb.wallet.icon} {wb.wallet.name}</span>
                  <span className="text-gray-500">฿{fmt(wb.spent)} / ฿{fmt(wb.budget)}</span>
                </div>
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${pct(wb.spent, wb.budget)}%`, background: wb.wallet.color }}
                  />
                </div>
                <div className="flex justify-between text-xs mt-1">
                  <span className={wb.remaining >= 0 ? 'text-emerald-600' : 'text-red-600'}>
                    ฿{fmt(wb.remaining)} left
                  </span>
                  <span className="text-gray-400">{pct(wb.spent, wb.budget)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card flex flex-col">
          <h2 className="text-lg font-semibold mb-4">Spending by Wallet</h2>
          {d && (
            <div className="flex-1 flex items-center justify-center">
              <Doughnut
                data={{
                  labels: d.wallet_breakdown.map((wb) => wb.wallet.name),
                  datasets: [
                    {
                      data: d.wallet_breakdown.some((wb) => wb.spent > 0)
                        ? d.wallet_breakdown.map((wb) => wb.spent)
                        : d.wallet_breakdown.map((wb) => wb.budget),
                      backgroundColor: d.wallet_breakdown.map(
                        (wb) => wb.wallet.color + (d.wallet_breakdown.some((w) => w.spent > 0) ? 'dd' : '44'),
                      ),
                      borderWidth: 2,
                      borderColor: '#fff',
                    },
                  ],
                }}
                options={{ responsive: true, plugins: { legend: { position: 'bottom' } } }}
              />
            </div>
          )}
        </div>
      </div>

      {/* Daily chart + subscriptions */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">
            Daily Spending <span className="badge">{month}</span>
          </h2>
          {d && d.daily_chart.length > 0 && (
            <Bar
              data={{
                labels: d.daily_chart.map((x) => x.date.slice(8)),
                datasets: [
                  {
                    label: 'Daily Spend (฿)',
                    data: d.daily_chart.map((x) => x.amount),
                    backgroundColor: '#6366f144',
                    borderColor: '#6366f1',
                    borderWidth: 1,
                    borderRadius: 4,
                  },
                ],
              }}
              options={{
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, ticks: { callback: (v) => '฿' + Number(v).toLocaleString() } } },
              }}
            />
          )}
          {d && d.daily_chart.length === 0 && (
            <p className="text-gray-400 text-sm">No expenses this month</p>
          )}
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold mb-4">
            Active Subscriptions{' '}
            <span className="badge">฿{fmt(d?.subscription_total ?? 0)}/mo</span>
          </h2>
          {d?.active_subscriptions.length === 0 ? (
            <p className="text-gray-400 text-sm">No subscriptions</p>
          ) : (
            d?.active_subscriptions.map((s) => {
              const w = wallets.find((w) => w.id === s.wallet_id)
              return (
                <div key={s.id} className="list-item">
                  <div>
                    <div className="font-medium text-sm">{s.name}</div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      Day {s.billing_day} · <WalletTag wallet={w} />
                    </div>
                  </div>
                  <div className="font-semibold text-sm">฿{fmt(s.amount)}</div>
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* Recent expenses */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Recent Expenses</h2>
        {d?.recent_expenses.length === 0 ? (
          <p className="text-gray-400 text-sm">No expenses this month</p>
        ) : (
          d?.recent_expenses.map((e) => {
            const cat = categories.find((c) => c.id === e.category_id)
            const w = wallets.find((w) => w.id === e.wallet_id)
            return (
              <div key={e.id} className="list-item">
                <div>
                  <div className="font-medium text-sm">
                    {e.description}{' '}
                    {e.type === 'unexpected' && (
                      <span className="type-tag text-amber-700 bg-amber-50">⚡ unexpected</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {e.date} · {cat?.name ?? '—'} · <WalletTag wallet={w} />
                  </div>
                </div>
                <div className="font-semibold text-sm">฿{fmt(e.amount)}</div>
              </div>
            )
          })
        )}
      </div>

      {/* Add expense modal */}
      <Modal open={modal.open} onClose={() => setModal({ open: false, type: 'planned' })}>
        <h2 className="text-lg font-semibold mb-4">
          {modal.type === 'unexpected' ? '⚡ Unexpected Activity' : '+ Add Planned Expense'}
        </h2>
        <form onSubmit={submitExpense}>
          <div className="form-group">
            <label className="form-label">Date</label>
            <input
              name="date"
              type="date"
              defaultValue={new Date().toISOString().slice(0, 10)}
              required
              className="form-input"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Description</label>
            <input name="description" type="text" placeholder="e.g. Starbucks latte" required autoFocus className="form-input" />
          </div>
          <div className="form-group">
            <label className="form-label">Amount (฿)</label>
            <input name="amount" type="number" placeholder="0" min="0" step="1" required className="form-input" />
          </div>
          <div className="form-group">
            <label className="form-label">Wallet</label>
            <select
              name="wallet_id"
              required
              className="form-input"
              onChange={(e) => setSelectedWalletId(e.target.value)}
            >
              <option value="">— Select wallet —</option>
              {wallets.map((w) => (
                <option key={w.id} value={w.id}>{w.icon} {w.name}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Category</label>
            <select name="category_id" required className="form-input">
              <option value="">— Select category —</option>
              {filteredCats.map((c) => {
                const w = wallets.find((ww) => ww.id === c.wallet_id)
                return (
                  <option key={c.id} value={c.id}>
                    {c.name}{!selectedWalletId ? ` (${w?.name ?? ''})` : ''}
                  </option>
                )
              })}
            </select>
          </div>
          <div className="flex gap-2 justify-end mt-2">
            <button type="button" className="btn btn-secondary" onClick={() => setModal({ open: false, type: 'planned' })}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">Save</button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
