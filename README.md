# ai-dish-skill

这个仓库用于发布 `dish-health-recommender` skill 的代码、测试文档与项目报告。

## 目录结构

- `dish-health-recommender/`：skill 本体，包含脚本、providers、data、references、tests
- `report/`：项目优化版报告
- `pic/`：多模态图片验证样本

## 主要内容

### Skill

核心入口：

- `dish-health-recommender/SKILL.md`
- `dish-health-recommender/scripts/recommend.py`

辅助能力：

- 图片验证：`dish-health-recommender/scripts/validate_images.py`
- API 验证：`dish-health-recommender/scripts/validate_apis.py`
- 报告对齐：`dish-health-recommender/scripts/report_alignment.py`
- 反馈闭环：`dish-health-recommender/scripts/apply_feedback.py`

### 测试与验证文档

- `dish-health-recommender/tests/`

### 报告

- `report/AI创想家_菜谱识别推荐系统_优化版报告.md`

## 说明

本仓库保留了报告、skill、测试与图片样本之间的关联材料，便于展示实现与验证过程。
