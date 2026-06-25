import { useEffect, useState } from 'react'
import { loadStockIndex } from '@/utils/stockIndexLoader'
import type { StockIndexItem } from '@/types/stockIndex'

let cache: StockIndexItem[] | null = null

/** Tải bộ chỉ mục mã cổ phiếu VN một lần và chia sẻ giữa các component. */
export function useStockIndex() {
  const [items, setItems] = useState<StockIndexItem[]>(cache ?? [])
  const [loading, setLoading] = useState(!cache)

  useEffect(() => {
    if (cache) return
    let mounted = true
    loadStockIndex().then((res) => {
      if (!mounted) return
      cache = res.data
      setItems(res.data)
      setLoading(false)
    })
    return () => {
      mounted = false
    }
  }, [])

  return { items, loading }
}
