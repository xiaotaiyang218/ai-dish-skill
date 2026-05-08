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
- `ingredients`
- `user_profile`
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

当前实现中，外部能力默认通过环境变量注入凭证；未配置时会保留降级路径，不会把未验证能力包装成已完成能力。

### 4. 最小反馈闭环

相关脚本：

- `dish-health-recommender/scripts/apply_feedback.py`

当前支持的最小反馈事件包括：

- `accept`
- `reject`
- `favorite`
- `correct_dish_name`

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

## 测试说明

测试资产位于 `dish-health-recommender/tests/`，包含：

- `fixtures/`：输入样例
- `expected/`：断言样例
- `contract/`：合同测试
- `test_*.py`：主回归测试与专项测试

说明：当前仓库已包含测试代码与测试文档，但本地环境是否能直接运行完整测试取决于是否安装了对应测试依赖。

## 数据与边界

- 本仓库优先使用本地菜谱与营养知识做判断。
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
- 基于当前数据与测试资产继续扩展菜谱库、规则引擎和多模态验证链路
