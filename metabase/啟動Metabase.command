#!/bin/bash
# 取得目前腳本所在的目錄
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "🍜 正在啟動滾麵專屬 本地端 Metabase..."
cd "$DIR"

# 背景啟動 docker-compose
docker-compose up -d

echo "✅ 啟動指令已送出！"
echo "👉 請大約等待 1-2 分鐘讓系統暖機完畢"
echo "🔗 接著在瀏覽器打開： http://localhost:3000"
