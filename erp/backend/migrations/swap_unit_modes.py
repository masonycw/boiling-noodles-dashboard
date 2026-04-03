"""
Migration: swap base ↔ secondary in order_unit_mode and stocktake_unit_mode
for items that had their unit ↔ secondary_unit swapped.

Before swap: unit=罐(base/small), secondary_unit=箱(secondary/big)
  - order_unit_mode='secondary' meant "only big unit (箱)"
  - order_unit_mode='base' meant "only small unit (罐)"

After swap: unit=箱(base/big), secondary_unit=罐(secondary/small)
  - order_unit_mode='secondary' now means "only small unit (罐)" ← WRONG
  - order_unit_mode='base' now means "only big unit (箱)" ← correct interpretation

Fix: swap 'base' ↔ 'secondary' so the UI shows the correct unit.
Only affects items where secondary_unit is not null (dual-unit items).
"""

import sys
sys.path.insert(0, '/home/mason_ycw/boiling-noodles-dashboard')

from erp.backend.db.session import engine
from sqlalchemy import text

def run():
    with engine.begin() as conn:
        # 先查看現在狀態
        result = conn.execute(text("""
            SELECT id, name, unit, secondary_unit, order_unit_mode, stocktake_unit_mode
            FROM erp_items
            WHERE secondary_unit IS NOT NULL AND secondary_unit != ''
            ORDER BY id
        """))
        rows = result.fetchall()
        print(f"找到 {len(rows)} 筆雙單位品項需要更新 mode：")
        for r in rows:
            print(f"  id={r[0]} {r[1]}: unit={r[2]}, secondary={r[3]}, order_mode={r[4]}, stocktake_mode={r[5]}")

        # 對調 base ↔ secondary
        conn.execute(text("""
            UPDATE erp_items
            SET
                order_unit_mode = CASE order_unit_mode
                    WHEN 'base' THEN 'secondary'
                    WHEN 'secondary' THEN 'base'
                    ELSE order_unit_mode
                END,
                stocktake_unit_mode = CASE stocktake_unit_mode
                    WHEN 'base' THEN 'secondary'
                    WHEN 'secondary' THEN 'base'
                    ELSE stocktake_unit_mode
                END
            WHERE secondary_unit IS NOT NULL AND secondary_unit != ''
        """))

        # 確認結果
        result2 = conn.execute(text("""
            SELECT id, name, unit, secondary_unit, order_unit_mode, stocktake_unit_mode
            FROM erp_items
            WHERE secondary_unit IS NOT NULL AND secondary_unit != ''
            ORDER BY id
        """))
        print("\n對調後結果：")
        for r in result2.fetchall():
            print(f"  id={r[0]} {r[1]}: unit={r[2]}, secondary={r[3]}, order_mode={r[4]}, stocktake_mode={r[5]}")

        print("\n✓ mode 對調完成")

if __name__ == '__main__':
    run()
