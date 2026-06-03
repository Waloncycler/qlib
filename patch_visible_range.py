import sys

filepath = "/Users/walox/qlib/scripts/data_collector/cn_stock/topic_dashboard.html"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the dataZoom extraction logic to be safe against undefined
old_logic = """                    const currentOption = chartInstance.getOption();
                    if (currentOption.dataZoom && currentOption.dataZoom[0]) {
                        visibleRange.value = {
                            start: currentOption.dataZoom[0].startValue,
                            end: currentOption.dataZoom[0].endValue
                        };
                    }"""

new_logic = """                    const currentOption = chartInstance.getOption();
                    if (currentOption.dataZoom && currentOption.dataZoom[0]) {
                        const start = currentOption.dataZoom[0].startValue;
                        const end = currentOption.dataZoom[0].endValue;
                        visibleRange.value = {
                            start: start !== undefined ? start : 0,
                            end: end !== undefined ? end : kdata.length - 1
                        };
                    } else {
                        visibleRange.value = { start: 0, end: kdata.length - 1 };
                    }"""

content = content.replace(old_logic, new_logic)

# Replace the datazoom event listener logic similarly
old_event = """                        if (opt.dataZoom && opt.dataZoom[0]) {
                            visibleRange.value = {
                                start: opt.dataZoom[0].startValue,
                                end: opt.dataZoom[0].endValue
                            };
                        }"""

new_event = """                        if (opt.dataZoom && opt.dataZoom[0]) {
                            const start = opt.dataZoom[0].startValue;
                            const end = opt.dataZoom[0].endValue;
                            visibleRange.value = {
                                start: start !== undefined ? start : 0,
                                end: end !== undefined ? end : kdata.length - 1
                            };
                        }"""

content = content.replace(old_event, new_event)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Patch applied.")
