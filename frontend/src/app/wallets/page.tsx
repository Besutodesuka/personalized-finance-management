'use client'
import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import { Wallet, WalletBreakdown, MasterWallet, RefillResult } from '@/lib/types'
import { fmt, pct } from '@/lib/utils'
import Modal from '@/components/Modal'

export default function WalletsPage() {
  const [wallets, setWallets] = useState<Wallet[]>([])
  const [breakdown, setBreakdown] = useState<WalletBreakdown[]>([])
  const [master, setMaster] = useState<MasterWallet>({ balance: 0 })
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7))
  const [modal, setModal] = useState<{ open: boolean; wallet?: Wallet }>({ open: false })
  const [adjustAmount, setAdjustAmount] = useState('')
  const [adjustError, setAdjustError] = useState('')
  const [refillMsg, setRefillMsg] = useState('')
  const [editBudget, setEditBudget] = useState<{ id: string; value: string } | null>(null)

  const load = useCallback(async (m: string) => {
    const [w, d, mw] = await Promise.all([
      api.get<Wallet[]>('/wallets'),
      api.get<{ wallet_breakdown: WalletBreakdown[] }>(`/dashboard?month=${m}`),
      api.get<MasterWallet>('/master-wallet'),
    ])
    setWallets(w)
    setBreakdown(d.wallet_breakdown)
    setMaster(mw)
  }, [])

  useEffect(() => { load(month) }, [month, load])

  const submitWallet = async (e: React.FormEvent<HTMLFormElement>) => {
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

  const applyAdjust = async (sign: 1 | -1) => {
    const val = parseFloat(adjustAmount)
    if (isNaN(val) || val <= 0) { setAdjustError('Enter a positive amount'); return }
    setAdjustError('')
    const mw = await api.post<MasterWallet>('/master-wallet/adjust', { amount: sign * val })
    setMaster(mw)
    setAdjustAmount('')
  }

  const refill = async () => {
    const total = wallets.reduce((a, w) => a + w.budget, 0)
    if (!confirm(`Deduct ฿${fmt(total)} from master wallet to refill all wallets?`)) return
    setRefillMsg('')
    try {
      const r = await api.post<RefillResult>('/master-wallet/refill', {})
      setMaster({ balance: r.new_balance })
      setRefillMsg(`Refilled ฿${fmt(r.deducted)} → new master balance ฿${fmt(r.new_balance)}`)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setRefillMsg(msg)
    }
  }

  const saveBudget = async (walletId: string) => {
    if (!editBudget) return
    const val = parseFloat(editBudget.value)
    if (isNaN(val) || val < 0) { setEditBudget(null); return }
    const w = wallets.find(x => x.id === walletId)!
    await api.put(`/wallets/${walletId}`, { ...w, budget: val })
    setEditBudget(null)
    load(month)
  }

  const totalAllocation = wallets.reduce((a, w) => a + w.budget, 0)

  return (
    <div className="space-y-6">
      {/* Master Wallet */}
      <div className="card border-2 border-indigo-200 bg-indigo-50/50">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-lg font-bold text-indigo-800">🏦 Master Wallet</h2>
            <p className="text-sm text-indigo-600">Top-up here, then refill wallets monthly</p>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-indigo-700">฿{fmt(master.balance)}</div>
            <div className="text-xs text-indigo-500 mt-0.5">
              Total allocation: ฿{fmt(totalAllocation)}/mo
              {master.balance >= totalAllocation
                ? <span className="ml-1 text-emerald-600">✓ covered</span>
                : <span className="ml-1 text-red-500">⚠ short ฿{fmt(totalAllocation - master.balance)}</span>}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 items-end">
          <div className="flex-1 min-w-[160px]">
            <label className="text-xs text-gray-500 mb-1 block">Amount (฿)</label>
            <input
              type="number"
              value={adjustAmount}
              onChange={e => { setAdjustAmount(e.target.value); setAdjustError('') }}
              placeholder="e.g. 5000"
              min="0"
              step="100"
              className="form-input"
              onKeyDown={e => e.key === 'Enter' && applyAdjust(1)}
            />
            {adjustError && <p className="text-xs text-red-500 mt-1">{adjustError}</p>}
          </div>
          <button className="btn bg-emerald-600 text-white hover:bg-emerald-700" onClick={() => applyAdjust(1)}>
            + Add
          </button>
          <button className="btn bg-red-500 text-white hover:bg-red-600" onClick={() => applyAdjust(-1)}>
            − Subtract
          </button>
          <button
            className="btn btn-primary"
            onClick={refill}
            disabled={master.balance < totalAllocation}
            title={master.balance < totalAllocation ? `Need ฿${fmt(totalAllocation)} to refill` : 'Distribute monthly budgets'}
          >
            ↓ Refill Wallets (฿{fmt(totalAllocation)})
          </button>
        </div>
        {refillMsg && (
          <p className={`text-sm mt-2 ${refillMsg.includes('฿') ? 'text-emerald-700' : 'text-red-600'}`}>
            {refillMsg}
          </p>
        )}
      </div>

      {/* Wallet list header */}
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
          const isEditingBudget = editBudget?.id === w.id
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

              {/* Inline budget edit */}
              <div className="flex items-center gap-1 mb-3">
                <span className="text-xs text-gray-500">Monthly Budget:</span>
                {isEditingBudget ? (
                  <>
                    <input
                      type="number"
                      value={editBudget.value}
                      autoFocus
                      min="0"
                      step="100"
                      onChange={e => setEditBudget({ id: w.id, value: e.target.value })}
                      onBlur={() => saveBudget(w.id)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') saveBudget(w.id)
                        if (e.key === 'Escape') setEditBudget(null)
                      }}
                      className="form-input py-0.5 text-sm w-28"
                    />
                    <span className="text-xs text-gray-400">Enter to save</span>
                  </>
                ) : (
                  <button
                    className="text-sm font-medium text-gray-700 hover:text-indigo-600 underline decoration-dotted"
                    onClick={() => setEditBudget({ id: w.id, value: String(w.budget) })}
                    title="Click to edit budget"
                  >
                    ฿{fmt(w.budget)}
                  </button>
                )}
              </div>

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
        <form onSubmit={submitWallet}>
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
