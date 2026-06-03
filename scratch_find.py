import json

with open('/Users/walox/qlib/data/cn_stock/hierarchical/signals/zizizaizai_reports.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    for r in data:
        content = r.get('content', '')
        if '天马新材]' in content or '楚江新材002171' in content:
            idx = content.find('楚江新材002171')
            if idx == -1: idx = content.find('天马新材]')
            print("Found in report", r.get('id'))
            print(content[max(0, idx-50):idx+100])
