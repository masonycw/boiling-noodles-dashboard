import pandas as pd
import data_loader

def test_mapping():
    # 建立一個測試用的虛擬資料集，包含不同的情境：
    # 1. 載具被多個人使用（看 Frequency, Recency, Monetary 排行）
    # 2. 只有載具沒電話的訂單，是否成功被指派
    
    loader = data_loader.UniversalLoader()
    
    # 模擬的 DataFrame
    data = [
        # 情境 1: 老公開啟載具 (Frequency = 1, Recency = 10/1, Monetary = 200)
        {'order_id': '001', 'date': '2025-10-01 12:00:00', 'total_amount': 200, 'member_phone': '0911111111', 'customer_name': '老公', 'carrier_id': '/ABCD123'},
        
        # 情境 2: 太太後來也用同個載具，來了 2 天 (Frequency = 2, Recency = 10/15, Monetary = 300)
        {'order_id': '002', 'date': '2025-10-05 12:00:00', 'total_amount': 150, 'member_phone': '0922222222', 'customer_name': '太太', 'carrier_id': '/ABCD123'},
        {'order_id': '003', 'date': '2025-10-15 12:00:00', 'total_amount': 150, 'member_phone': '0922222222', 'customer_name': '太太', 'carrier_id': '/ABCD123'},
        
        # 情境 3: 無名單 - 只有載具，沒留電話
        {'order_id': '004', 'date': '2025-09-01 12:00:00', 'total_amount': 500, 'member_phone': None, 'customer_name': None, 'carrier_id': '/ABCD123'},
        {'order_id': '005', 'date': '2025-11-01 12:00:00', 'total_amount': 100, 'member_phone': '', 'customer_name': '', 'carrier_id': '/ABCD123'},
        
        # 情境 4: 孤零零的載具 - 從來沒綁定過電話
        {'order_id': '006', 'date': '2025-12-01 12:00:00', 'total_amount': 300, 'member_phone': None, 'customer_name': None, 'carrier_id': '/ALONE99'}
    ]
    
    df_report = pd.DataFrame(data)
    df_details = pd.DataFrame() # 空的 Details
    
    print("--- 原始資料 ---")
    print(df_report[['order_id', 'member_phone', 'customer_name', 'carrier_id']])
    
    # 執行 Enrich Data (此邏輯會觸發載具綁定)
    df_report, _ = loader.enrich_data(df_report, df_details)
    
    print("\n--- 綁定後的資料 ---")
    print(df_report[['order_id', 'member_phone', 'customer_name', 'carrier_id', 'Member_ID']])
    
    # 驗證
    print("\n--- 驗證結果 ---")
    # Order 004 應該被綁定給太太 (0922222222)，因為她的 Frequency = 2 勝過老公的 1
    o4 = df_report[df_report['order_id'] == '004'].iloc[0]
    if o4['member_phone'] == '0922222222' and o4['Member_ID'] == 'CRM_0922222222':
        print("✅ 測試通過：無名單成功歸戶給最高頻率的太太 (0922222222)")
    else:
        print(f"❌ 測試失敗：無名單被錯誤歸戶或未歸戶，結果是 {o4['member_phone']} / {o4['Member_ID']}")

    # Order 006 應該維持 Carrier 身分
    o6 = df_report[df_report['order_id'] == '006'].iloc[0]
    if pd.isna(o6['member_phone']) or o6['member_phone'] == '':
        if o6['Member_ID'] == 'Carrier_/ALONE99':
            print("✅ 測試通過：未曾綁定過電話的載具維持 Carrier 身分")
        else:
            print(f"❌ 測試失敗：未綁定載具的 Member_ID 不正確，結果是 {o6['Member_ID']}")

if __name__ == '__main__':
    test_mapping()
