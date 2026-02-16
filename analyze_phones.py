import pandas as pd
import os

# Load data
df = pd.read_csv('/Users/mason/Library/Mobile Documents/com~apple~CloudDocs/滾麵專案/智慧報表/history_report.csv')

# Check column names
col_phone = '客戶電話' if '客戶電話' in df.columns else 'Contact'
col_name = '客戶姓名' if '客戶姓名' in df.columns else 'Customer Name'

if col_phone in df.columns:
    # Top 5 most frequent phone numbers
    top_phones = df[col_phone].value_counts().head(5)
    print("Top 5 Phone Numbers:")
    print(top_phones)
    
    print("\nname distribution for these phones:")
    for phone in top_phones.index:
        names = df[df[col_phone] == phone][col_name].value_counts().head(3)
        print(f"\nPhone: {phone}")
        print(names)
else:
    print("Phone column not found")
