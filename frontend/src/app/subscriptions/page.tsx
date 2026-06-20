'use client'
import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import { Subscription, Wallet } from '@/lib/types'
import { fmt } from '@/lib/utils'
import Modal from '@/components/Modal'
import WalletTag from '@/components/WalletTag'

export default function SubscriptionsPage() {
  const [subs, setSubs] = useState<Subscription[]>([])
  const [wallets, setWallets] = useState<Wallet[]>([])
  const [modal, setModal] = useState<{ open: boolean; sub?: Subscription }>({ open: false })

  const load = useCallback(async () => {
    const [s, w] = await Promise.all([
      api.get<Subscription[]>('/subscriptions'),
      api.get<Wallet[]>('/wallets'),
    ])
    setSubs(s)
    setWallets(w)
  }, [])

  useEffect(() => { load() }, [load])

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    const body = {
      name: fd.get('name') as string,
      amount: parseFloat(fd.get('amount') as string),
      billing_day: parseInt(fd.get('billing_day') as string),
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
  const monthly = active.reduce((a, s) => a + s.amount, 0)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Subscriptions</h1>
        <button className="btn btn-primary" onClick={() => setModal({ open: true })}>+ Add Subscription</button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Monthly', value: `฿${fmt(monthly)}`, cls: 'text-amber-600' },
          { label: 'Annual', value: `฿${fmt(monthly * 12)}`, cls: '' },
          { label: 'Active', value: String(active.length), cls: '' },
          { label: 'Paused', value: String(subs.length - active.length), cls: '' },
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
            return (
              <div
                key={s.id}
                className={`list-item ${!s.active ? 'opacity-50' : ''}`}
              >
                <div>
                  <div className="font-medium text-sm">
                    {s.name}{' '}
                    {!s.active && (
                      <span className="type-tag bg-gray-100 text-gray-500">paused</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    Bills day {s.billing_day} · <WalletTag wallet={w} />
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm">฿{fmt(s.amount)}/mo</span>
                  <button className="btn-icon" title={s.active ? 'Pause' : 'Resume'} onClick={() => toggle(s)}>
                    {s.active ? '⏸️' : '▶️'}
                  </button>
                  <button className="btn-icon" onClick={() => setModal({ open: true, sub: s })}>✏️</button>
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
            <label className="form-label">Amount (฿/month)</label>
            <input
              name="amount"
              type="number"
              defaultValue={modal.sub?.amount ?? ''}
              placeholder="199"
              min="0"
              step="1"
              required
              className="form-input"
            />
          </div>
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
