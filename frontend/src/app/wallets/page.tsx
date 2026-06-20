'use client'
import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import { Wallet, WalletBreakdown } from '@/lib/types'
import { fmt, pct } from '@/lib/utils'
import Modal from '@/components/Modal'

export default function WalletsPage() {
  const [wallets, setWallets] = useState<Wallet[]>([])
  const [breakdown, setBreakdown] = useState<WalletBreakdown[]>([])
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7))
  const [modal, setModal] = useState<{ open: boolean; wallet?: Wallet }>({ open: false })

  const load = useCallback(async (m: string) => {
    const [w, d] = await Promise.all([
      api.get<Wallet[]>('/wallets'),
      api.get<{ wallet_breakdown: WalletBreakdown[] }>(`/dashboard?month=${m}`),
    ])
    setWallets(w)
    setBreakdown(d.wallet_breakdown)
  }, [])

  useEffect(() => { load(month) }, [month, load])

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    const body = {
      name: fd.get('name') as string,
      budget: parseFloat(fd.get('budget') as string),
      icon: fd.get('icon') as string,
      color: fd.get('color') as string,
    }
    if (modal.wallet) {
      await api.put(`/wallets/${modal.wallet.id}`, body)
    } else {
      await api.post('/wallets', body)
    }
    setModal({ open: false })
    load(month)
  }

  const deleteWallet = async (id: string) => {
    if (!confirm('Delete wallet? Expenses assigned to it will remain.')) return
    await api.del(`/wallets/${id}`)
    load(month)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Wallets</h1>
        <div className="flex items-center gap-2">
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="form-input w-auto" />
          <button className="btn btn-primary" onClick={() => setModal({ open: true })}>+ Add Wallet</button>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        {wallets.map((w) => {
          const wb = breakdown.find((x) => x.wallet.id === w.id)
          const spent = wb?.spent ?? 0
          const remaining = wb?.remaining ?? w.budget
          return (
            <div
              key={w.id}
              className="card"
              style={{ borderTop: `4px solid ${w.color}` }}
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-3xl">{w.icon}</span>
                <div className="flex gap-1">
                  <button className="btn-icon" onClick={() => setModal({ open: true, wallet: w })}>✏️</button>
                  <button className="btn-icon" onClick={() => deleteWallet(w.id)}>🗑️</button>
                </div>
              </div>
              <h3 className="font-semibold text-lg">{w.name}</h3>
              <p className="text-sm text-gray-500 mb-3">Monthly Budget: ฿{fmt(w.budget)}</p>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{ width: `${pct(spent, w.budget)}%`, background: w.color }}
                />
              </div>
              <div className="flex justify-between text-sm mt-2">
                <span className="text-gray-500">Spent ฿{fmt(spent)}</span>
                <span className={remaining >= 0 ? 'text-emerald-600 font-medium' : 'text-red-600 font-medium'}>
                  ฿{fmt(remaining)} left
                </span>
              </div>
            </div>
          )
        })}
      </div>

      <Modal open={modal.open} onClose={() => setModal({ open: false })}>
        <h2 className="text-lg font-semibold mb-4">{modal.wallet ? 'Edit Wallet' : 'Add Wallet'}</h2>
        <form onSubmit={submit}>
          <div className="form-group">
            <label className="form-label">Name</label>
            <input
              name="name"
              type="text"
              defaultValue={modal.wallet?.name ?? ''}
              placeholder="e.g. Food & Dining"
              required
              autoFocus
              className="form-input"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Monthly Budget (฿)</label>
            <input
              name="budget"
              type="number"
              defaultValue={modal.wallet?.budget ?? ''}
              placeholder="5000"
              min="0"
              step="100"
              required
              className="form-input"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Icon (emoji)</label>
            <input
              name="icon"
              type="text"
              defaultValue={modal.wallet?.icon ?? '💰'}
              maxLength={4}
              className="form-input"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Color</label>
            <input
              name="color"
              type="color"
              defaultValue={modal.wallet?.color ?? '#6366f1'}
              className="form-input h-10 cursor-pointer"
            />
          </div>
          <div className="flex gap-2 justify-end mt-2">
            <button type="button" className="btn btn-secondary" onClick={() => setModal({ open: false })}>Cancel</button>
            <button type="submit" className="btn btn-primary">{modal.wallet ? 'Update' : 'Create'}</button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
