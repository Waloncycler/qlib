import requests

def test_eastmoney_popularity():
    url = "https://emappdata.eastmoney.com/stockrank/getAllCurrentList"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        data = {"appId": "appId01", "globalId": "786e4c21-70dc-435a-93bb-38", "marketType": "", "pageNo": 1, "pageSize": 200}
        resp = requests.post(url, json=data, headers=headers)
        js = resp.json()
        print(f"Total: {len(js.get('data', []))}")
        if js.get("data"):
            print("First item:", js["data"][0])
    except Exception as e:
        print("Error:", e)

test_eastmoney_popularity()
