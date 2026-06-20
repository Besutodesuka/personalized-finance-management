import { Wallet } from '@/lib/types'

interface Props {
  wallet?: Wallet
}

export default function WalletTag({ wallet }: Props) {
  if (!wallet) return null
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
      style={{ background: wallet.color + '22', color: wallet.color }}
    >
      {wallet.icon} {wallet.name}
    </span>
  )
}
