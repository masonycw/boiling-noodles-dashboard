/**
 * 智能解譯雙單位數量 (箱/罐)
 * @param {number|string} qty - 總數量 (以基準單位計算的總數，如 77 罐)
 * @param {Object} item - 品項設定物件
 * @returns {string} - 如 `3 箱 5 罐` 或 `77 罐`
 */
export function formatDualUnit(qty, item) {
  if (qty == null || qty === '') return ''
  const q = parseFloat(qty)

  if (!item || !item.secondary_unit || !item.secondary_unit_ratio) {
    return `${q} ${item?.unit || item?.adhoc_unit || ''}`.trim()
  }

  const ratio = parseFloat(item.secondary_unit_ratio)
  if (!ratio || ratio <= 0) {
    return `${q} ${item.unit || item.adhoc_unit || ''}`.trim()
  }

  // 防呆：如果比例如 1箱=24個，那 q 必須是大於等於一箱的數量
  const secondaryCount = Math.floor(q / ratio)
  const baseCount = q % ratio

  let str = ''
  if (secondaryCount > 0) {
    str += `${secondaryCount} ${item.secondary_unit} `
  }
  // 顯示基準單位的條件：有餘數，或者連一箱都不到，或是剛好0
  if (baseCount > 0 || (secondaryCount === 0 && baseCount === 0)) {
    // 為了避免浮點數誤差，取到小數第二位
    const displayBase = Number(baseCount.toFixed(2))
    str += `${displayBase} ${item.unit || ''}`
  }

  return str.trim()
}
