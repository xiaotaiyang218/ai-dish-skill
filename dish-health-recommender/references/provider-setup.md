# 认证配置说明

当前实现里，**真正用于运行时增强的在线能力**只保留：

## 1. 百度菜品识别（Domestic Vision）
需要配置：
- `BAIDU_API_KEY`
- `BAIDU_SECRET_KEY`

用途：
- 菜肴图识别
- 菜单图中的菜品候选增强

未配置时：
- 状态会显示为 `needs_credentials`
- 自动降级到本地 `mac_vision_ocr` + OCR-assisted 候选提取

当前备注：
- 已做过一次最小成本实测，百度链路可成功返回结果。
- 由于菜品识别是收费能力，当前实现会优先在确有必要时使用，并在结果低价值（如返回“非菜”）时回退到本地 OCR-assisted 识别。

## 附录：暂不纳入当前运行时依赖的来源
以下来源不再作为当前运行时在线依赖，仅保留为未来扩展方向：

- 老乡鸡标准化菜谱：未来可作为本地标准菜谱导入源
- 中国营养学会资源库：未来可作为权威资料导入或规则校核来源
- FoodWake：未来可作为营养增强候选来源
- NutriData：未来可作为营养增强候选来源

## 验证方法
配置完成后运行：

```bash
python3 .agents/skills/dish-health-recommender/scripts/validate_apis.py
```

期望：
- `Baidu_Dish_Recognition` 从 `needs_credentials` 变为 `validated` 或 `unavailable`
