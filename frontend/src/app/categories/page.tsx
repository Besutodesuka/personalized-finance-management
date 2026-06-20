'use client'
import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import { Category, Wallet } from '@/lib/types'
import Modal from '@/components/Modal'
import WalletTag from '@/components/WalletTag'

const TYPE_COLORS: Record<string, string> = {
  daily: '#10b981',
  subscription: '#6366f1',
  unexpected: '#f59e0b',
}

export default function CategoriesPage() {
  const [categories, setCategories] = useState<Category[]>([])
  const [wallets, setWallets] = useState<Wallet[]>([])
  const [modal, setModal] = useState<{ open: boolean; cat?: Category }>({ open: false })

  const load = useCallback(async () => {
    const [c, w] = await Promise.all([
      api.get<Category[]>('/categories'),
      api.get<Wallet[]>('/wallets'),
    ])
    setCategories(c)
    setWallets(w)
  }, [])

  useEffect(() => { load() }, [load])

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    const body = {
      name: fd.get('name') as string,
      wallet_id: fd.get('wallet_id') as string,
      type: fd.get('type') as string,
    }
    if (modal.cat) {
      await api.put(`/categories/${modal.cat.id}`, body)
    } else {
      await api.post('/categories', body)
    }
    setModal({ open: false })
    load()
  }

  const del = async (id: string) => {
    if (!confirm('Delete category?')) return
    await api.del(`/categories/${id}`)
    load()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Categories</h1>
        <button className="btn btn-primary" onClick={() => setModal({ open: true })}>+ Add Category</button>
      </div>

      <div className="card">
        {categories.length === 0 ? (
          <p className="text-gray-400 text-sm">No categories yet</p>
        ) : (
          categories.map((c) => {
            const w = wallets.find((ww) => ww.id === c.wallet_id)
            const tc = TYPE_COLORS[c.type] ?? '#888'
            return (
              <div key={c.id} className="list-item">
                <div>
                  <div className="font-medium text-sm">{c.name}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <WalletTag wallet={w} />
                    <span
                      className="type-tag"
                      style={{ background: tc + '22', color: tc }}
                    >
                      {c.type}
                    </span>
                  </div>
                </div>
                <div className="flex gap-1">
                  <button className="btn-icon" onClick={() => setModal({ open: true, cat: c })}>✏️</button>
                  <button className="btn-icon" onClick={() => del(c.id)}>🗑️</button>
                </div>
              </div>
            )
          })
        )}
      </div>

      <Modal open={modal.open} onClose={() => setModal({ open: false })}>
        <h2 className="text-lg font-semibold mb-4">{modal.cat ? 'Edit Category' : 'Add Category'}</h2>
        <form onSubmit={submit}>
          <div className="form-group">
            <label className="form-label">Name</label>
            <input
              name="name"
              type="text"
              defaultValue={modal.cat?.name ?? ''}
              placeholder="e.g. Cafe, Taxi, Gym"
              required
              autoFocus
              className="form-input"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Default Wallet</label>
            <select name="wallet_id" required className="form-input" defaultValue={modal.cat?.wallet_id ?? ''}>
              <option value="">— Select wallet —</option>
              {wallets.map((w) => (
                <option key={w.id} value={w.id}>{w.icon} {w.name}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Type</label>
            <select name="type" className="form-input" defaultValue={modal.cat?.type ?? 'daily'}>
              <option value="daily">Daily</option>
              <option value="subscription">Subscription</option>
              <option value="unexpected">Unexpected</option>
            </select>
          </div>
          <div className="flex gap-2 justify-end mt-2">
            <button type="button" className="btn btn-secondary" onClick={() => setModal({ open: false })}>Cancel</button>
            <button type="submit" className="btn btn-primary">{modal.cat ? 'Update' : 'Add'}</button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
