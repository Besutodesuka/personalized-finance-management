export interface Wallet {
  id: string
  name: string
  budget: number
  color: string
  icon: string
}

export interface Category {
  id: string
  name: string
  wallet_id: string
  type: 'daily' | 'subscription' | 'unexpected'
}

export interface Expense {
  id: string
  date: string
  amount: number
  description: string
  category_id: string
  wallet_id: string
  type: 'planned' | 'unexpected'
}

export interface Subscription {
  id: string
  name: string
  amount: number
  billing_day: number
  billing_cycle: 'monthly' | 'yearly'
  renewal_date: string | null
  wallet_id: string
  active: boolean
}

export interface MasterWallet {
  balance: number
}

export interface RefillResult {
  ok: boolean
  deducted: number
  new_balance: number
  distributions: { wallet: string; amount: number }[]
}

export interface WalletBreakdown {
  wallet: Wallet
  spent: number
  budget: number
  remaining: number
  pct: number
}

export interface Dashboard {
  month: string
  total_budget: number
  total_spent: number
  total_remaining: number
  daily_average: number
  wallet_breakdown: WalletBreakdown[]
  subscription_total: number
  active_subscriptions: Subscription[]
  unexpected_count: number
  today_spent: number
  today_count: number
  recent_expenses: Expense[]
  daily_chart: { date: string; amount: number }[]
}
