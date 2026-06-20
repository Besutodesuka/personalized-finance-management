'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api'

const NAV = [
  { href: '/', icon: '📊', label: 'Dashboard' },
  { href: '/expenses', icon: '📋', label: 'Expenses' },
  { href: '/wallets', icon: '👛', label: 'Wallets' },
  { href: '/subscriptions', icon: '🔁', label: 'Subscriptions' },
  { href: '/categories', icon: '🏷️', label: 'Categories' },
  { href: '/chat', icon: '🤖', label: 'AI Chat' },
]

export default function Sidebar() {
  const path = usePathname()
  return (
    <nav className="w-56 shrink-0 bg-white border-r border-gray-100 flex flex-col h-screen sticky top-0">
      <div className="flex items-center gap-2 px-5 py-6 border-b border-gray-100">
        <span className="text-2xl">💸</span>
        <span className="font-bold text-lg text-gray-900">Expense</span>
      </div>
      <ul className="flex-1 p-3 space-y-1 overflow-y-auto">
        {NAV.map(({ href, icon, label }) => {
          const active = href === '/' ? path === '/' : path.startsWith(href)
          return (
            <li key={href}>
              <Link
                href={href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors text-sm font-medium ${
                  active
                    ? 'bg-indigo-100 text-indigo-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <span>{icon}</span>
                <span>{label}</span>
              </Link>
            </li>
          )
        })}
      </ul>
      <div className="p-4 border-t border-gray-100 flex gap-2">
        <a
          href={`${API_BASE}/export/expenses.csv`}
          target="_blank"
          rel="noreferrer"
          className="flex-1 text-center text-xs text-gray-500 hover:text-gray-800 border border-gray-200 rounded-lg py-1.5 transition-colors"
        >
          ↓ CSV
        </a>
        <a
          href={`${API_BASE}/export/data.json`}
          target="_blank"
          rel="noreferrer"
          className="flex-1 text-center text-xs text-gray-500 hover:text-gray-800 border border-gray-200 rounded-lg py-1.5 transition-colors"
        >
          ↓ JSON
        </a>
      </div>
    </nav>
  )
}
