#!/bin/bash
# 取得目前腳本所在的目錄
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "💤 正在關閉並休眠您本地的 Metabase..."
cd "$DIR"

# 關閉並移除 container
docker-compose down

echo "✅ Metabase 已成功關閉，並釋放您的電腦記憶體！"
