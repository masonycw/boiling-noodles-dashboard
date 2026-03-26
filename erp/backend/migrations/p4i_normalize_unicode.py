"""
p4i: 修正 erp_items 和 erp_vendors 名稱中的康熙部首字元（Unicode NFKC 正規化）

這些異常字元是初始測試資料由 AI 生成時產生的，肉眼無法辨識但會導致搜尋失效。
例如：⼩(U+2F29) 看起來與 小(U+5C0F) 完全相同，但字串比對會失敗。
"""
import unicodedata
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from erp.backend.db.session import SessionLocal
from erp.backend.db.models import Item, Vendor, ItemCategory, StocktakeGroup


def normalize(s):
    if s is None:
        return s
    return unicodedata.normalize('NFKC', s)


def run():
    db = SessionLocal()
    try:
        fixed = 0

        # erp_items
        for item in db.query(Item).all():
            n = normalize(item.name)
            if n != item.name:
                print(f"  Item id={item.id}: {repr(item.name)} → {repr(n)}")
                item.name = n
                fixed += 1

        # erp_vendors
        for vendor in db.query(Vendor).all():
            n = normalize(vendor.name)
            if n != vendor.name:
                print(f"  Vendor id={vendor.id}: {repr(vendor.name)} → {repr(n)}")
                vendor.name = n
                fixed += 1

        # erp_item_categories
        for cat in db.query(ItemCategory).all():
            n = normalize(cat.name)
            if n != cat.name:
                print(f"  ItemCategory id={cat.id}: {repr(cat.name)} → {repr(n)}")
                cat.name = n
                fixed += 1

        # erp_stocktake_groups
        for grp in db.query(StocktakeGroup).all():
            n = normalize(grp.name)
            if n != grp.name:
                print(f"  StocktakeGroup id={grp.id}: {repr(grp.name)} → {repr(n)}")
                grp.name = n
                fixed += 1

        db.commit()
        print(f"完成：共修正 {fixed} 筆資料")
    except Exception as e:
        db.rollback()
        print(f"錯誤：{e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    run()
