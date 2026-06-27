'use client'
import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import { Subscription, Wallet } from '@/lib/types'
import { fmt } from '@/lib/utils'
import Modal from '@/components/Modal'
import WalletTag from '@/components/WalletTag'

function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null
  const diff = new Date(dateStr).getTime() - new Date().setHours(0, 0, 0, 0)
  return Math.ceil(diff / 86400000)
}

export default function SubscriptionsPage() {
  const [subs, setSubs] = useState<Subscription[]>([])
  const [wallets, setWallets] = useState<Wallet[]>([])
  const [modal, setModal] = useState<{ open: boolean; sub?: Subscription }>({ open: false })
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly')

  const load = useCallback(async () => {
    const [s, w] = await Promise.all([
      api.get<Subscription[]>('/subscriptions'),
      api.get<Wallet[]>('/wallets'),
    ])
    setSubs(s)
    setWallets(w)
  }, [])

  useEffect(() => { load() }, [load])

  const openModal = (sub?: Subscription) => {
    setBillingCycle(sub?.billing_cycle ?? 'monthly')
    setModal({ open: true, sub })
  }

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    const cycle = fd.get('billing_cycle') as 'monthly' | 'yearly'
    const body: Omit<Subscription, 'id'> = {
      name: fd.get('name') as string,
      amount: parseFloat(fd.get('amount') as string),
      billing_day: cycle === 'monthly' ? parseInt(fd.get('billing_day') as string) : 1,
      billing_cycle: cycle,
      renewal_date: cycle === 'yearly' ? (fd.get('renewal_date') as string) || null : null,
      wallet_id: fd.get('wallet_id') as string,
      active: modal.sub?.active ?? true,
    }
    if (modal.sub) {
      await api.put(`/subscriptions/${modal.sub.id}`, body)
    } else {
      await api.post('/subscriptions', body)
    }
    setModal({ open: false })
    load()
  }

  const toggle = async (sub: Subscription) => {
    await api.put(`/subscriptions/${sub.id}`, { ...sub, active: !sub.active })
    load()
  }

  const del = async (id: string) => {
    if (!confirm('Delete subscription?')) return
    await api.del(`/subscriptions/${id}`)
    load()
  }

  const active = subs.filter((s) => s.active)
  const monthlyActive = active.filter(s => s.billing_cycle === 'monthly')
  const yearlyActive = active.filter(s => s.billing_cycle === 'yearly')
  const monthly = monthlyActive.reduce((a, s) => a + s.amount, 0)
  const yearlyMonthlyEq = yearlyActive.reduce((a, s) => a + s.amount / 12, 0)
  const effectiveMonthly = monthly + yearlyMonthlyEq

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Subscriptions</h1>
        <button className="btn btn-primary" onClick={() => openModal()}>+ Add Subscription</button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Monthly Cost', value: `฿${fmt(monthly)}`, cls: 'text-amber-600' },
          { label: 'Yearly Cost', value: `฿${fmt(yearlyActive.reduce((a, s) => a + s.amount, 0))}`, cls: 'text-violet-600' },
          { label: 'Effective/mo', value: `฿${fmt(effectiveMonthly)}`, cls: '' },
          { label: 'Active', value: String(active.length), cls: '' },
        ].map(({ label, value, cls }) => (
          <div key={label} className="stat-card">
            <div className="text-sm text-gray-500">{label}</div>
            <div className={`text-xl font-bold mt-1 ${cls}`}>{value}</div>
          </div>
        ))}
      </div>

      <div className="card">
        {subs.length === 0 ? (
          <p className="text-gray-400 text-sm">No subscriptions yet</p>
        ) : (
          subs.map((s) => {
            const w = wallets.find((ww) => ww.id === s.wallet_id)
            const days = s.billing_cycle === 'yearly' ? daysUntil(s.renewal_date) : null
            return (
              <div
                key={s.id}
                className={`list-item ${!s.active ? 'opacity-50' : ''}`}
              >
                <div>
                  <div className="font-medium text-sm flex items-center gap-1.5">
                    {s.name}
                    <span className={`type-tag ${s.billing_cycle === 'yearly' ? 'bg-violet-100 text-violet-700' : 'bg-amber-50 text-amber-700'}`}>
                      {s.billing_cycle}
                    </span>
                    {!s.active && (
                      <span className="type-tag bg-gray-100 text-gray-500">paused</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {s.billing_cycle === 'yearly' && s.renewal_date ? (
                      <>
                        Renews {s.renewal_date}
                        {days !== null && (
                          <span className={days <= 30 ? ' text-amber-600 font-medium' : ''}>
                            {' '}({days > 0 ? `in ${days}d` : days === 0 ? 'today' : `${-days}d overdue`})
                          </span>
                        )}
                      </>
                    ) : (
                      <>Bills day {s.billing_day}</>
                    )}
                    {' · '}<WalletTag wallet={w} />
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="text-right">
                    <div className="font-semibold text-sm">
                      ฿{fmt(s.amount)}{s.billing_cycle === 'yearly' ? '/yr' : '/mo'}
                    </div>
                    {s.billing_cycle === 'yearly' && (
                      <div className="text-xs text-gray-400">≈฿{fmt(s.amount / 12)}/mo</div>
                    )}
                  </div>
                  <button className="btn-icon" title={s.active ? 'Pause' : 'Resume'} onClick={() => toggle(s)}>
                    {s.active ? '⏸️' : '▶️'}
                  </button>
                  <button className="btn-icon" onClick={() => openModal(s)}>✏️</button>
                  <button className="btn-icon" onClick={() => del(s.id)}>🗑️</button>
                </div>
              </div>
            )
          })
        )}
      </div>

      <Modal open={modal.open} onClose={() => setModal({ open: false })}>
        <h2 className="text-lg font-semibold mb-4">{modal.sub ? 'Edit Subscription' : 'Add Subscription'}</h2>
        <form onSubmit={submit}>
          <div className="form-group">
            <label className="form-label">Service Name</label>
            <input
              name="name"
              type="text"
              defaultValue={modal.sub?.name ?? ''}
              placeholder="Netflix, Spotify…"
              required
              autoFocus
              className="form-input"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Billing Cycle</label>
            <select
              name="billing_cycle"
              className="form-input"
              value={billingCycle}
              onChange={e => setBillingCycle(e.target.value as 'monthly' | 'yearly')}
            >
              <option value="monthly">Monthly</option>
              <option value="yearly">Yearly</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">
              Amount (฿/{billingCycle === 'yearly' ? 'year' : 'month'})
            </label>
            <input
              name="amount"
              type="number"
              defaultValue={modal.sub?.amount ?? ''}
              placeholder={billingCycle === 'yearly' ? '1990' : '199'}
              min="0"
              step="1"
              required
              className="form-input"
            />
          </div>
          {billingCycle === 'monthly' ? (
            <div className="form-group">
              <label className="form-label">Billing Day (1–31)</label>
              <input
                name="billing_day"
                type="number"
                defaultValue={modal.sub?.billing_day ?? 1}
                min="1"
                max="31"
                required
                className="form-input"
              />
            </div>
          ) : (
            <div className="form-group">
              <label className="form-label">Renewal Date</label>
              <input
                name="renewal_date"
                type="date"
                defaultValue={modal.sub?.renewal_date ?? ''}
                required
                className="form-input"
              />
            </div>
          )}
          <div className="form-group">
            <label className="form-label">Wallet</label>
            <select name="wallet_id" required className="form-input" defaultValue={modal.sub?.wallet_id ?? ''}>
              <option value="">— Select wallet —</option>
              {wallets.map((w) => (
                <option key={w.id} value={w.id}>{w.icon} {w.name}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-2 justify-end mt-2">
            <button type="button" className="btn btn-secondary" onClick={() => setModal({ open: false })}>Cancel</button>
            <button type="submit" className="btn btn-primary">{modal.sub ? 'Update' : 'Add'}</button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
