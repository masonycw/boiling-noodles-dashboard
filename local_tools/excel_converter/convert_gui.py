import tkinter as tk
from tkinter import messagebox, scrolledtext
import pandas as pd
import os
import sys
from datetime import datetime

# --- Config ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, 'input')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

# Ensure directories exist
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

class ConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("滾麵 Excel 轉 CSV 小工具")
        self.root.geometry("600x400")
        
        # Title
        tk.Label(root, text="Excel 批量轉 CSV 工具", font=("Arial", 20, "bold")).pack(pady=10)
        
        # Instructions
        instruction_text = (
            f"1. 請把 Excel 檔案 (.xls, .xlsx) 放入 '{os.path.basename(INPUT_DIR)}' 資料夾。\n"
            f"2. 按下方的「開始轉換」按鈕。\n"
            f"3. 轉換後的 CSV 檔案會出現在 '{os.path.basename(OUTPUT_DIR)}' 資料夾。\n"
            f"4. 請把 CSV 檔案上傳到伺服器。"
        )
        tk.Label(root, text=instruction_text, justify="left", font=("Arial", 12)).pack(pady=10)
        
        # Convert Button
        self.btn_convert = tk.Button(root, text="開始轉換 (Start Conversion)", command=self.run_conversion, 
                                     font=("Arial", 14, "bold"), bg="#4CAF50", fg="black", height=2)
        self.btn_convert.pack(pady=10, fill='x', padx=50)
        
        # Log Area
        tk.Label(root, text="執行日誌 (Log):", font=("Arial", 10, "bold")).pack(anchor='w', padx=10)
        self.log_area = scrolledtext.ScrolledText(root, height=10, state='disabled', font=("Courier", 10))
        self.log_area.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.log(f"準備就緒。請將檔案放入: {INPUT_DIR}")

    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')
        self.root.update()

    def run_conversion(self):
        self.btn_convert.config(state='disabled')
        self.log("--- 開始掃描 ---")
        
        files = [f for f in os.listdir(INPUT_DIR) if f.endswith(('.xls', '.xlsx'))]
        
        if not files:
            self.log("❌ 找不到 Excel 檔案！請確認 'input' 資料夾內有檔案。")
            messagebox.showwarning("找不到檔案", "input 資料夾是空的！")
            self.btn_convert.config(state='normal')
            return
            
        success_count = 0
        
        for f in files:
            input_path = os.path.join(INPUT_DIR, f)
            output_filename = os.path.splitext(f)[0] + ".csv"
            output_path = os.path.join(OUTPUT_DIR, output_filename)
            
            try:
                self.log(f"正在讀取: {f} ...")
                
                # Determine engine
                if f.endswith('.xls'):
                    df = pd.read_excel(input_path, engine='xlrd')
                else:
                    df = pd.read_excel(input_path, engine='openpyxl')
                
                # Convert to CSV
                df.to_csv(output_path, index=False, encoding='utf-8-sig') # utf-8-sig for Excel compatibility
                
                self.log(f"✅ 成功轉換: {output_filename}")
                success_count += 1
                
            except Exception as e:
                self.log(f"❌ 失敗 {f}: {str(e)}")
        
        self.log(f"--- 完成 ---")
        self.log(f"共轉換 {success_count} 個檔案。請查看 output 資料夾。")
        messagebox.showinfo("完成", f"成功轉換 {success_count} 個檔案！")
        self.btn_convert.config(state='normal')

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = ConverterApp(root)
        root.mainloop()
    except Exception as e:
        # Fallback if Tkinter fails
        print(f"Error launching GUI: {e}")
        input("Press Enter to exit...")
