#!/bin/bash
# 警告：此操作不可逆，会删除所有集合及其文档！

BASE_URL="http://127.0.0.1:8081"

# 获取集合列表
collections=$(curl -s "$BASE_URL/admin/collections" | jq -r '.collections[]')

if [ -z "$collections" ]; then
    echo "没有找到任何集合"
    exit 0
fi

echo "即将删除以下集合："
echo "$collections"
read -p "确认删除？(y/N) " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "操作已取消"
    exit 0
fi

for coll in $collections; do
    echo "正在删除集合: $coll"
    curl -X DELETE "$BASE_URL/collections/$coll"
    echo
done

echo "所有集合已删除"