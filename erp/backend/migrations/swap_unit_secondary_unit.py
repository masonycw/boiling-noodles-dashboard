"""
Migration: swap unit ↔ secondary_unit for items that have both fields set.

Before: unit='罐' (小單位), secondary_unit='箱' (大單位)
After:  unit='箱' (主單位), secondary_unit='罐' (盤點小單位)

Only affects items where BOTH unit and secondary_unit are non-empty.
Items with only one unit are left unchanged.
"""

import sys
import os
sys.path.insert(0, '/home/mason_ycw/boiling-noodles-dashboard')

from erp.backend.db.session import engine
from sqlalchemy import text

def run():
    with engine.begin() as conn:
        # 先查一下有多少筆會被影響
        result = conn.execute(text("""
            SELECT id, name, unit, secondary_unit, secondary_unit_ratio
            FROM erp_items
            WHERE unit IS NOT NULL AND unit != ''
              AND secondary_unit IS NOT NULL AND secondary_unit != ''
            ORDER BY id
        """))
        rows = result.fetchall()
        print(f"找到 {len(rows)} 筆有雙單位的品項需要對調：")
        for r in rows:
            print(f"  id={r[0]} {r[1]}: unit='{r[2]}' ↔ secondary_unit='{r[3]}' (ratio={r[4]})")

        if not rows:
            print("沒有需要對調的品項，結束。")
            return

        # 對調 unit ↔ secondary_unit（ratio 值不變，只是欄位標籤語義改了）
        conn.execute(text("""
            UPDATE erp_items
            SET
                unit = secondary_unit,
                secondary_unit = unit
            WHERE unit IS NOT NULL AND unit != ''
              AND secondary_unit IS NOT NULL AND secondary_unit != ''
        """))

        # 確認結果
        result2 = conn.execute(text("""
            SELECT id, name, unit, secondary_unit, secondary_unit_ratio
            FROM erp_items
            WHERE id = ANY(:ids)
            ORDER BY id
        """), {"ids": [r[0] for r in rows]})
        print("\n對調後結果：")
        for r in result2.fetchall():
            print(f"  id={r[0]} {r[1]}: unit='{r[2]}' secondary_unit='{r[3]}' (ratio={r[4]})")

        print("\n✓ 對調完成")

if __name__ == '__main__':
    run()
