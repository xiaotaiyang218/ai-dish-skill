# ai-dish-skill

`ai-dish-skill` 是一个可安装到常见 Agent 的中文饮食健康推荐 skill。核心目录是 `dish-health-recommender/`，它可以根据菜名、菜单文字、OCR 文本、菜肴图片线索和用户健康约束，输出可解释的推荐结论。

这个仓库既包含 skill 本体，也包含本地脚本、测试资产、验证报告和项目报告。默认情况下，它不依赖任何外部 API key；配置可选凭证后，可以启用百度菜品识别和 Spoonacular 菜谱参考增强。

## 快速安装：安装为通用 Agent Skill

推荐把 `dish-health-recommender/` 作为一个独立 skill 目录，放到宿主 Agent 的 skills 目录下。OpenClaw、Codex 或其他支持本地 skill 目录的 Agent 都可以采用同一种方式：先确定该 Agent 的 skills 目录，再复制或软链接本 skill。

```bash
git clone https://github.com/xiaotaiyang218/ai-dish-skill.git

# 替换为你的 Agent 实际读取的 skills 目录。
# 例如 OpenClaw 或其他 Agent 的本地 skills 目录。
export AGENT_SKILLS_DIR="$HOME/.openclaw/skills"

mkdir -p "$AGENT_SKILLS_DIR"
cp -R ai-dish-skill/dish-health-recommender "$AGENT_SKILLS_DIR/dish-health-recommender"
```

安装后目录应类似：

```text
$AGENT_SKILLS_DIR/dish-health-recommender/
  SKILL.md
  scripts/
  providers/
  data/
  references/
  tests/
```

只要 `dish-health-recommender/SKILL.md` 位于 skill 根目录，支持本地 skill 的 Agent 就可以按自己的加载规则识别这个 skill。如果宿主 Agent 支持软链接，也可以用 `ln -s` 代替 `cp -R`，方便后续更新仓库代码。

安装后也可以直接用本地脚本验证核心推荐能力：

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

如果要在 OpenClaw 里按自然语言对话实测 6 个核心用例，可以直接参考：

- `dish-health-recommender/references/openclaw-core-use-cases.md`

## 安装条件

- 必需：Python 3。
- 推荐：Git，用于 clone 或更新仓库。
- 可选：百度菜品识别 API key，用于菜肴图片候选增强。
- 可选：Spoonacular API key，用于本地未命中时的菜谱参考源增强。

未配置任何 API key 时，skill 仍然可以使用本地菜谱库、营养知识库、规则引擎和降级逻辑完成推荐。外部 API 只用于增强，不是运行时硬依赖。

## 可选凭证配置

真实 key 不应提交到仓库。代码会先读取环境变量；如果环境变量不存在，再读取 `.local-secrets.json`。

推荐配置文件格式：

```json
{
  "BAIDU_API_KEY": "your-baidu-api-key",
  "BAIDU_SECRET_KEY": "your-baidu-secret-key",
  "SPOONACULAR_API_KEY": "your-spoonacular-api-key"
}
```

`.local-secrets.json` 必须放在 `dish-health-recommender/` 的父目录：

- 在本仓库内开发时：`ai-dish-skill/.local-secrets.json`
- 安装到 Agent 后：`$AGENT_SKILLS_DIR/.local-secrets.json`

相关 key 说明：

- `BAIDU_API_KEY` / `BAIDU_SECRET_KEY`：启用百度菜品识别 provider。未配置时，图片链路会显示 `needs_credentials`，并降级到 OCR-assisted vision。
- `SPOONACULAR_API_KEY`：启用 Spoonacular recipe search。未配置时，推荐链路会跳过该参考源，继续使用本地数据和其他可降级候选。

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

结果会包含标准菜名、候选菜品、食材、做法、营养标签、风险标签、解释理由、待确认项，以及命中标准配方时的营养量化字段。无精确标准配方但有常见菜谱依据时，结果可包含 `nutrition_quantitative_range`，并用“约 X-Y”和“不是实测克重”标注边界。

自然语言对话建议使用 `output_mode=human_readable_cn` 的表达顺序：先列菜肴信息（识别菜品、食材、做法、风险标签、营养估算），再给结论、原因、建议和需要确认项。这样在 OpenClaw 等 Agent App 中不会只给一句结论，用户可以看到判断依据。

如果请求带 `user_id`，推荐脚本会合并用户已确认的 `persistent_constraints` 和 `temporary_goals`，并在输出中返回 `applied_user_profile`。这类画像只应在用户明确确认后通过反馈脚本写入，不能从一次普通提问自动长期记忆。

### 2. 多模态图片验证

相关脚本：

- `dish-health-recommender/scripts/validate_images.py`
- `dish-health-recommender/scripts/image_cases.py`

样本目录：

- `pic/`
- `dish-health-recommender/tests/images/index.json`

图片识别链路会优先使用已配置的 provider；未配置或识别质量不足时，会保留原始结果并回退到 `need_confirm` 或 OCR-assisted 候选。

### 3. 在线增强能力验证

相关脚本：

- `dish-health-recommender/scripts/validate_apis.py`

当前在线菜谱增强按 `CookBook-KG -> xiachufang -> douguo -> xiangha -> Spoonacular` 顺序尝试。其中 `xiachufang`、`douguo`、`xiangha` 仅作为搜索页 reference-only 候选，不视为稳定 API；`Spoonacular` 需要 `SPOONACULAR_API_KEY`，也只作为可选参考源。

### 4. 长期反馈学习与可解释偏置

相关脚本：

- `dish-health-recommender/scripts/apply_feedback.py`
- `dish-health-recommender/scripts/chat_recommend.py`

当前支持：

- `accept`
- `reject`
- `favorite`
- `correct_dish_name`
- `set_user_profile`：在用户明确确认后记录长期约束和阶段目标
- 基于 `user_id` 的 user-dish profile
- 基于 `user_id` 的用户画像：`persistent_constraints` 存过敏、疾病相关限制、长期忌口；`temporary_goals` 存最近减脂、低盐、控糖等阶段目标
- `context_tags` 记录与 explanation 回显
- 时间衰减窗口下的 replay/profile 重建

用户画像不会从一次普通推荐里自动写入。需要用户明确确认后，才用 `action=user_profile` 记录：

```bash
python3 dish-health-recommender/scripts/apply_feedback.py /dev/stdin <<'JSON'
{
  "action": "user_profile",
  "user_id": "alice",
  "persistent_constraints": {
    "allergies": ["海鲜"]
  },
  "temporary_goals": {
    "goals": ["减脂"],
    "conditions": ["低盐"]
  }
}
JSON
```

后续推荐请求只要带同一个 `user_id`，`recommend.py` 会合并这些已确认信息，并在输出中返回 `applied_user_profile`。

## 常用命令

### 最小推荐验证

不需要任何 API key：

```bash
python3 dish-health-recommender/scripts/recommend.py <<'JSON'
{
  "dish_name": "提拉米苏",
  "user_profile": {
    "goals": ["减脂"],
    "conditions": ["控糖"]
  }
}
JSON
```

### API 状态验证

```bash
python3 dish-health-recommender/scripts/validate_apis.py
```

未配置百度或 Spoonacular key 时，相关 provider 显示 `needs_credentials` 是正常结果，不代表本地推荐不可用。

### 图片验证

```bash
python3 dish-health-recommender/scripts/validate_images.py
```

### 反馈回放

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

### 离线导入

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

## 测试说明

测试资产位于 `dish-health-recommender/tests/`，包含：

- `fixtures/`：输入样例
- `expected/`：断言样例
- `contract/`：合同测试
- `test_*.py`：主回归测试与专项测试

本地环境安装 `pytest` 后，可以运行：

```bash
python3 -m pytest dish-health-recommender/tests -q
```

也可以使用标准库 `unittest` 运行主要测试：

```bash
python3 -m unittest discover -s dish-health-recommender/tests -p 'test_*.py'
```

## 数据与边界

- 本仓库优先使用本地菜谱与营养知识做判断。
- 扩展源只允许通过离线导入落到本地快照，不作为运行时强依赖。
- 第三方能力通过环境变量或 `.local-secrets.json` 接入，不在仓库中提交真实凭证。
- 未验证的 OCR、vision、nutrition API 不应被视为已稳定可用。
- 输出仅作为饮食参考，不构成医疗诊断或治疗建议。
- 对外发布或上线前，应再次人工核查报告、截图、视频和配置文件，避免暴露账号、路径、定位和真实凭证。

## 当前发布内容概览

- Agent skill 目录 1 个：`dish-health-recommender/`
- 图片样本 22 张
- 已包含项目报告 1 份
- 已包含推荐、验证、反馈和导入脚本

## 当前证据产物

- 图片验证指标：`dish-health-recommender/validation/image-validation-report.json`
- API 验证矩阵：`dish-health-recommender/validation/api-validation-report.json`
- 报告对齐产物：`dish-health-recommender/validation/report-alignment-report.json`
- 反馈回放产物：`dish-health-recommender/validation/feedback-replay-report.json`
- 导入产物：`dish-health-recommender/validation/source-import-report.json`

当前图片指标样本统计：OCR hit rate `1.0`，Top-1 `0.3636`，Top-3 `0.3636`，health rule accuracy `0.8636`，p50/p95 latency `5083/9828ms`。
