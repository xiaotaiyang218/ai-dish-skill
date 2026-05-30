---
name: dish-health-recommender
description: 分析菜名、菜单文字、食物图片线索和用户健康约束，输出中文健康饮食推荐、营养风险解释和待确认事项。适用于判断菜品是否适合用户、筛选菜单、识别过敏/控糖/低盐/减脂等风险，并可作为无需专用后端的便携式菜品识别与推荐 skill。
---

# 菜品健康推荐助手

## 用途

使用本 skill 帮助 agent 扮演菜品理解与健康推荐助手。它不要求部署专用后端：优先使用宿主 agent 已具备的文本、图片、文件、联网和记忆能力；需要确定性本地检查时，调用随 skill 提供的脚本。

本 skill 的输出只作为饮食参考，不构成医疗诊断或治疗建议。

## 工作流程

1. 解析用户输入：
   - 菜名、菜单文字、OCR 文本或用户自然语言描述。
   - 食物图、菜单图或图片路径，如果宿主平台支持视觉能力。
   - 用户约束，包括过敏、疾病相关限制、饮食目标、偏好和忌口。
2. 归一化并理解菜品：
   - 将常见别名归一化，例如 `西红柿炒鸡蛋` -> `番茄炒蛋`。
   - 对歧义菜名保持保守，例如 `鱼香肉丝` 通常不含鱼，但过敏敏感场景仍应确认具体配方。
   - 推断可能食材、做法和风险标签，并区分已确认事实和合理假设。
3. 比对用户约束：
   - 过敏源和明确疾病限制优先级最高。
   - 低盐、控糖、减脂、高蛋白、素食、低脂等目标会影响推荐等级。
   - 证据不足、图片候选冲突或数据缺失时，返回 `需要确认`，不要强行给确定结论。
4. 用中文解释推荐：
   - 开头先给结论：`推荐`、`谨慎`、`不推荐` 或 `需要确认`。
   - 给出 2-4 条与食材、做法、营养风险或用户约束直接相关的理由。
   - 只有在缺失信息会改变判断时，才向用户追问。

## 可用资源

- 确定性本地推荐：运行 `scripts/recommend.py`，输入 JSON。支持 `dish_name`、`menu_text`、`ocr_text`、`image_reference`、`image_path`、`ingredients`、`user_profile`、`user_id`、`context_tags` 和 `output_mode`。
- 报告与实现证据对齐：运行 `scripts/report_alignment.py`，生成或验证 `ReportAlignmentItem`。
- 本地菜谱缓存刷新：运行 `scripts/fetch_cookbook_kg.py`，写入 `data/dishes.json` 和 `data/source_manifest.json`。
- 图片验证：运行 `scripts/validate_images.py`，结合 `data/image_test_cases.json` 和图片样本验证 OCR / vision 链路。
- API 状态验证：运行 `scripts/validate_apis.py`，检查外部 provider 的 `validated`、`needs_credentials`、`degraded` 或 `unavailable` 状态。
- 反馈闭环：运行 `scripts/apply_feedback.py`，处理 `accept`、`reject`、`favorite`、`correct_dish_name` 等反馈事件。

必要参考文件：

- 规则与不确定性策略：`references/recommendation-rules.md`
- 数据源优先级：`references/data-sources.md`
- Provider 配置：`references/provider-setup.md`
- 输出模板：`references/output-templates.md`
- 单系统提示词迁移：`references/platform-prompt.md`
- 验证样例：`references/test-cases.md`
- 报告证据核查：`references/report-alignment-checklist.md`

## 本地配置

无需配置 API key 也可以使用本地推荐能力。外部凭证仅用于增强链路：

- `BAIDU_API_KEY` / `BAIDU_SECRET_KEY`：启用百度菜品识别。
- `SPOONACULAR_API_KEY`：启用 Spoonacular 菜谱参考增强。

读取顺序：

1. 优先读取环境变量。
2. 如果环境变量不存在，读取 `dish-health-recommender/` 父目录下的 `.local-secrets.json`。

示例：

```json
{
  "BAIDU_API_KEY": "your-baidu-api-key",
  "BAIDU_SECRET_KEY": "your-baidu-secret-key",
  "SPOONACULAR_API_KEY": "your-spoonacular-api-key"
}
```

仓库开发时，文件位置通常是 `ai-dish-skill/.local-secrets.json`；安装到宿主 Agent 后，文件位置通常是该 Agent skills 目录下的 `.local-secrets.json`，也就是 `dish-health-recommender/` 的父目录。不要把真实 key 写入仓库。

## 脚本契约

`scripts/recommend.py` 从 stdin 或文件路径读取 JSON，并向 stdout 输出 UTF-8 JSON。

数据解析顺序：

1. 常见菜品的内置安全样例。
2. 本地菜谱库 `data/dishes.json`。
3. 本地未命中且网络可用时的 CookBook-KG fallback。
4. 本地营养知识库 `data/nutrition_knowledge.json`，用于补充营养标签、风险标签和约束提醒。
5. 本地缺失食材时的 USDA FoodData Central fallback。
6. 可选 Spoonacular recipe search 参考源。
7. 无可靠候选时返回 `need_confirm`。

示例：

```bash
python3 dish-health-recommender/scripts/recommend.py <<'JSON'
{
  "dish_name": "番茄炒蛋",
  "user_profile": {
    "allergies": ["鸡蛋"],
    "goals": ["低脂"]
  }
}
JSON
```

典型输出字段：

- `normalized_dish`
- `recommendation`: `recommend`、`caution`、`avoid` 或 `need_confirm`
- `confidence`
- `ingredients`
- `cooking_method`
- `nutrition_tags`
- `risk_tags`
- `nutrition_evidence`
- `explanation`
- `need_confirm`
- `candidates`
- `raw_image_result`
- `nutrition_quantitative`

脚本也支持自定义食材和中文用户展示模式：

```json
{
  "dish_name": "巧克力甜点",
  "ingredients": ["chocolate"],
  "user_profile": {"conditions": ["控糖"], "goals": ["减脂"]},
  "output_mode": "human_readable_cn"
}
```

## 边界

- 不把输出表述为医疗诊断、治疗建议或替代医生意见。
- 没有可靠数据源时，不编造精确热量、蛋白质、钠、糖或脂肪数值。
- 未在当前环境验证的外部 API，不声称可用。
- 不因为口味偏好而覆盖过敏或严重健康限制。
- 当前运行环境缺少 OCR 或 vision 能力时，要明确降级并请求文字或食材补充，不能假装完成图片识别。
- 优先使用国内中式菜谱和营养知识；国外数据源只作为可选补充。
