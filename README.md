# ai-dish-skill

`ai-dish-skill` 是一个面向中文饮食健康场景的 skill 发布仓库，核心能力是对菜名、菜单文字、OCR 结果和菜肴图片线索进行理解，再结合用户的过敏、疾病相关限制和饮食目标，输出可解释的推荐结论。

当前仓库主要用于沉淀以下内容：

- `dish-health-recommender` skill 本体
- 本地可运行的推荐脚本与辅助 providers
- 回归测试、合同测试和图片样本
- 项目优化版报告

## 仓库结构

- `dish-health-recommender/`
  - `SKILL.md`：skill 定义与使用边界
  - `scripts/`：推荐、图片验证、API 验证、反馈闭环、报告对齐等脚本
  - `providers/`：OCR、vision、nutrition provider
  - `data/`：菜谱、营养知识、反馈、量化配方与来源清单
  - `references/`：输出模板、规则说明、数据源说明、provider 配置说明
  - `tests/`：回归测试、合同测试、fixtures、expected、图片索引
- `report/`
  - `AI创想家_菜谱识别推荐系统_优化版报告.md`：项目优化版报告
- `pic/`
  - 多模态图片验证样本

## 核心能力

### 1. 菜品归一化与健康推荐

核心脚本：`dish-health-recommender/scripts/recommend.py`

支持输入：

- `dish_name`
- `menu_text`
- `ocr_text`
- `image_reference`
- `image_path`
- `ingredients`
- `user_profile`
- `user_id`
- `context_tags`
- `output_mode`

输出结论分为四类：

- `recommend`
- `caution`
- `avoid`
- `need_confirm`

同时返回标准菜名、食材、做法、营养标签、风险标签、解释理由、待确认项，以及在命中标准配方时的营养量化字段。

### 2. 多模态图片验证

相关脚本：

- `dish-health-recommender/scripts/validate_images.py`
- `dish-health-recommender/scripts/image_cases.py`

样本目录：

- `pic/`
- `dish-health-recommender/tests/images/index.json`

### 3. 在线增强能力验证

相关脚本：

- `dish-health-recommender/scripts/validate_apis.py`

当前实现中，外部能力默认通过环境变量或仓库根目录下的 `.local-secrets.json` 注入凭证；未配置时会保留降级路径，不会把未验证能力包装成已完成能力。当前在线菜谱增强按 `CookBook-KG -> xiachufang -> douguo -> xiangha -> Spoonacular` 顺序尝试，其中三个中文站点仅作为运行时 reference-only 搜索源，`Spoonacular` 仍需 `SPOONACULAR_API_KEY` 且仅作为可选参考源。

### 4. 长期反馈学习与可解释偏置

相关脚本：

- `dish-health-recommender/scripts/apply_feedback.py`
- `dish-health-recommender/scripts/chat_recommend.py`

当前支持：

- `accept`
- `reject`
- `favorite`
- `correct_dish_name`
- 基于 `user_id` 的 user-dish profile
- `context_tags` 记录与 explanation 回显
- 时间衰减窗口下的 replay/profile 重建

## 快速使用

### 运行单次推荐

```bash
python3 dish-health-recommender/scripts/recommend.py <<'JSON'
{
  "dish_name": "番茄炒蛋",
  "user_profile": {
    "allergies": ["鸡蛋"]
  }
}
JSON
```

### 运行图片验证

```bash
python3 dish-health-recommender/scripts/validate_images.py
```

### 运行 API 验证

```bash
python3 dish-health-recommender/scripts/validate_apis.py
```

### 运行反馈回放

```bash
python3 dish-health-recommender/scripts/apply_feedback.py /dev/stdin <<'JSON'
{
  "action": "replay",
  "storePath": "dish-health-recommender/data/feedback.json",
  "profileMode": "user_dish",
  "decayWindowDays": 30
}
JSON
```

### 运行离线导入

```bash
python3 dish-health-recommender/scripts/import_sources.py /dev/stdin <<'JSON'
{
  "sourceName": "CookBook-KG",
  "sourceType": "recipe",
  "importMode": "offline_snapshot",
  "sourceLocation": "https://raw.githubusercontent.com/ngl567/CookBook-KG/master/visualization/vizdata.json",
  "targetFiles": ["dish-health-recommender/data/dishes.json"],
  "enableForRuntime": true
}
JSON
```

## 测试说明

测试资产位于 `dish-health-recommender/tests/`，包含：

- `fixtures/`：输入样例
- `expected/`：断言样例
- `contract/`：合同测试
- `test_*.py`：主回归测试与专项测试

说明：当前仓库已包含测试代码与测试文档，但本地环境是否能直接运行完整测试取决于是否安装了对应测试依赖。

当前已验证通过的关键测试包括：

- `test_recommend.py`
- `test_multimodal.py`
- `test_quantization.py`
- `test_feedback.py`
- `test_e2e_nl.py`
- `test_alignment.py`
- `test_import_sources.py`
- `tests/contract/` 合同测试套件

## 数据与边界

- 本仓库优先使用本地菜谱与营养知识做判断。
- 扩展源只允许通过离线导入落到本地快照，不作为运行时强依赖。
- 在线菜谱增强按 `CookBook-KG -> xiachufang -> douguo -> xiangha -> Spoonacular` 顺序尝试；其中 `xiachufang`、`douguo`、`xiangha` 仅作为运行时 reference-only 搜索增强，未配置、超时、反爬或页面变化时都不会阻断本地推荐链路。
- `Spoonacular` 仅作为带配额限制的可选在线参考源；未配置或失败时同样不会阻断本地推荐链路。
- 第三方能力通过环境变量接入，不在仓库中提交真实凭证。
- 未验证的 OCR、vision、nutrition API 不应被视为已稳定可用。
- 输出仅作为饮食参考，不构成医疗诊断或治疗建议。
- 报告中提到的比赛提交合规项，仍应在正式对外交付前再次人工核查。

## 当前发布内容概览

- 非二进制文件约 112 个
- 图片样本 22 张
- 已包含项目报告 1 份

## 适用场景

这个仓库适合用于：

- 展示 skill 从规则、数据、脚本到测试的完整实现材料
- 做中文菜谱健康推荐相关的二次开发
- 基于当前数据、反馈回放、离线导入和测试资产继续扩展菜谱库、规则引擎和多模态验证链路

## 当前证据产物

- 图片验证指标：`dish-health-recommender/validation/image-validation-report.json`
- 报告对齐产物：`dish-health-recommender/validation/report-alignment-report.json`
- 反馈回放产物：`dish-health-recommender/validation/feedback-replay-report.json`
- 导入产物：`dish-health-recommender/validation/source-import-report.json`

当前图片指标样本统计：OCR hit rate `1.0`，Top-1 `0.3636`，Top-3 `0.3636`，health rule accuracy `0.8636`，p50/p95 latency `5083/9828ms`
