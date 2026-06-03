import sys

filepath = "/Users/walox/qlib/scripts/data_collector/cn_stock/fetch_zizizaizai_klines.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Add skipping logic
old_logic = """    for i, topic in enumerate(topics):
        t_id = str(topic.get("id"))
        t_name = topic.get("name")
        
        print(f"[{i+1}/{len(topics)}] Fetching klines for topic ID {t_id} ({t_name})...")"""

new_logic = """    for i, topic in enumerate(topics):
        t_id = str(topic.get("id"))
        t_name = topic.get("name")
        
        if t_id in klines_data and klines_data[t_id]:
            print(f"[{i+1}/{len(topics)}] Skipping topic ID {t_id} ({t_name}), already downloaded.")
            continue
            
        print(f"[{i+1}/{len(topics)}] Fetching klines for topic ID {t_id} ({t_name})...")"""

content = content.replace(old_logic, new_logic)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Patch applied.")
