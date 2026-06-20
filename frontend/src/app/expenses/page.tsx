'use client'
import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import { Expense, Wallet, Category } from '@/lib/types'
import { fmt } from '@/lib/utils'
import Modal from '@/components/Modal'
import WalletTag from '@/components/WalletTag'

type ModalState =
  | { open: false }
  | { open: true; mode: 'add'; type: 'planned' | 'unexpected' }
  | { open: true; mode: 'edit'; expense: Expense }

export default function ExpensesPage() {
  const [expenses, setExpenses] = useState<Expense[]>([])
  const [wallets, setWallets] = useState<Wallet[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7))
  const [modal, setModal] = useState<ModalState>({ open: false })
  const [selectedWalletId, setSelectedWalletId] = useState('')

  const load = useCallback(async (m: string) => {
    const [e, w, c] = await Promise.all([
      api.get<Expense[]>(`/expenses?month=${m}`),
      api.get<Wallet[]>('/wallets'),
      api.get<Category[]>('/categories'),
    ])
    setExpenses(e)
    setWallets(w)
    setCategories(c)
  }, [])

  useEffect(() => { load(month) }, [month, load])

  const closeModal = () => { setModal({ open: false }); setSelectedWalletId('') }

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    const body = {
      date: fd.get('date') as string,
      description: fd.get('description') as string,
      amount: parseFloat(fd.get('amount') as string),
      wallet_id: fd.get('wallet_id') as string,
      category_id: fd.get('category_id') as string,
      type: modal.open && modal.mode === 'edit' ? modal.expense.type : (modal.open && modal.mode === 'add' ? modal.type : 'planned'),
    }
    if (modal.open && modal.mode === 'edit') {
      await api.put(`/expenses/${modal.expense.id}`, body)
    } else {
      await api.post('/expenses', body)
    }
    closeModal()
    load(month)
  }

  const deleteExpense = async (id: string) => {
    if (!confirm('Delete this expense?')) return
    await api.del(`/expenses/${id}`)
    load(month)
  }

  const sorted = [...expenses].sort((a, b) => b.date.localeCompare(a.date))
  const isEdit = modal.open && modal.mode === 'edit'
  const editExp = isEdit ? (modal as { open: true; mode: 'edit'; expense: Expense }).expense : null
  const modalType = modal.open && modal.mode === 'add' ? modal.type : (editExp?.type ?? 'planned')
  const filteredCats = categories.filter((c) => !selectedWalletId || c.wallet_id === selectedWalletId)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Expenses</h1>
        <div className="flex items-center gap-2">
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="form-input w-auto" />
          <button className="btn btn-secondary" onClick={() => { setSelectedWalletId(''); setModal({ open: true, mode: 'add', type: 'planned' }) }}>
            + Planned
          </button>
          <button className="btn btn-primary" onClick={() => { setSelectedWalletId(''); setModal({ open: true, mode: 'add', type: 'unexpected' }) }}>
            ⚡ Unexpected
          </button>
        </div>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-gray-500 text-left">
              {['Date', 'Description', 'Category', 'Wallet', 'Type', 'Amount', ''].map((h) => (
                <th key={h} className={`pb-3 font-medium ${h === 'Amount' ? 'text-right' : ''}`}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr><td colSpan={7} className="py-8 text-center text-gray-400">No expenses this month</td></tr>
            ) : sorted.map((e) => {
              const cat = categories.find((c) => c.id === e.category_id)
              const w = wallets.find((ww) => ww.id === e.wallet_id)
              return (
                <tr key={e.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-3 pr-4">{e.date}</td>
                  <td className="py-3 pr-4">{e.description}</td>
                  <td className="py-3 pr-4">{cat?.name ?? '—'}</td>
                  <td className="py-3 pr-4"><WalletTag wallet={w} /></td>
                  <td className="py-3 pr-4">
                    <span
                      className="type-tag"
                      style={{
                        background: e.type === 'unexpected' ? '#f59e0b22' : '#6366f122',
                        color: e.type === 'unexpected' ? '#b45309' : '#4338ca',
                      }}
                    >
                      {e.type}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-right font-medium">฿{fmt(e.amount)}</td>
                  <td className="py-3 flex gap-1 justify-end">
                    <button
                      className="btn-icon"
                      onClick={() => {
                        setSelectedWalletId(e.wallet_id)
                        setModal({ open: true, mode: 'edit', expense: e })
                      }}
                    >
                      ✏️
                    </button>
                    <button className="btn-icon" onClick={() => deleteExpense(e.id)}>🗑️</button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <Modal open={modal.open} onClose={closeModal}>
        <h2 className="text-lg font-semibold mb-4">
          {isEdit ? 'Edit Expense' : modalType === 'unexpected' ? '⚡ Unexpected Activity' : '+ Add Planned Expense'}
        </h2>
        <form onSubmit={submit}>
          <div className="form-group">
            <label className="form-label">Date</label>
            <input
              name="date"
              type="date"
              defaultValue={editExp?.date ?? new Date().toISOString().slice(0, 10)}
              required
              className="form-input"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Description</label>
            <input
              name="description"
              type="text"
              defaultValue={editExp?.description ?? ''}
              placeholder="e.g. Starbucks latte"
              required
              autoFocus
              className="form-input"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Amount (฿)</label>
            <input
              name="amount"
              type="number"
              defaultValue={editExp?.amount ?? ''}
              placeholder="0"
              min="0"
              step="1"
              required
              className="form-input"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Wallet</label>
            <select
              name="wallet_id"
              required
              className="form-input"
              defaultValue={editExp?.wallet_id ?? ''}
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
            <select name="category_id" required className="form-input" defaultValue={editExp?.category_id ?? ''}>
              <option value="">— Select category —</option>
              {(isEdit
                ? categories
                : filteredCats
              ).map((c) => {
                const w = wallets.find((ww) => ww.id === c.wallet_id)
                return (
                  <option key={c.id} value={c.id}>
                    {c.name}{isEdit || !selectedWalletId ? ` (${w?.name ?? ''})` : ''}
                  </option>
                )
              })}
            </select>
          </div>
          <div className="flex gap-2 justify-end mt-2">
            <button type="button" className="btn btn-secondary" onClick={closeModal}>Cancel</button>
            <button type="submit" className="btn btn-primary">{isEdit ? 'Update' : 'Save'}</button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
