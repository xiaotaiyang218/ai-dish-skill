# Provider 配置与验证说明

当前实现里，运行时 provider 分为两类：
- 图片识别链路：`baidu_dish_recognition`、`domestic_ocr_api`、`mac_vision_ocr`、`ocr_assisted_vision`
- 营养/参考链路：`CookBook-KG`、`xiachufang`、`douguo`、`xiangha`、`Spoonacular`、`USDA_FDC`

本地开发可在仓库根目录创建 `.local-secrets.json`，写入 `BAIDU_API_KEY`、`BAIDU_SECRET_KEY`、`SPOONACULAR_API_KEY`；该文件已被 `.gitignore` 忽略。

## 1. 百度菜品识别（`baidu_dish_recognition`）
需要配置：
- `BAIDU_API_KEY`
- `BAIDU_SECRET_KEY`

用途：
- 菜肴图识别
- 菜单图中的菜品候选增强

未配置时：
- 状态会显示为 `needs_credentials`
- 自动降级到 `ocr_assisted_vision`

## 2. 国内 OCR（`domestic_ocr_api`）
需要配置：
- `DOMESTIC_OCR_ENDPOINT`
- `DOMESTIC_OCR_API_KEY`

用途：
- 优先尝试在线 OCR 提取图片文字
- 为 `ocr_assisted_vision` 提供更稳定的菜单/菜名候选

未配置或鉴权失败时：
- 状态会显示为 `needs_credentials`
- 自动降级到本地 `mac_vision_ocr`

## 3. 本地 OCR（`mac_vision_ocr`）
需要：
- macOS 本机 `Vision` 能力可用

用途：
- 本地 OCR 兜底
- 在在线 OCR 不可用时继续输出可追溯文字结果

异常时：
- 状态会显示为 `degraded`
- 图片主链路继续保留 `raw_image_result`，并由上层进入 `need_confirm` 或 OCR-assisted 兜底

## 4. OCR 辅助视觉候选（`ocr_assisted_vision`）
用途：
- 基于 OCR 行文本抽取菜品候选
- 过滤 `菜单`、`档口位置`、套餐/配餐文案和 `@肯德基` 一类低价值文本

说明：
- 这是运行时兜底 provider，不需要额外凭证
- 仅当候选通过低价值过滤后才会参与图片主链路 seed 选择

## 5. 营养/参考链路
- `CookBook-KG`：联网兜底菜谱候选
- `xiachufang`：搜索页候选增强，入口为 `GET https://www.xiachufang.com/search/?keyword=<query>&cat=1001&via=home`
- `douguo`：搜索页候选增强，入口为 `GET https://www.douguo.com/caipu/<urlencoded-query>`
- `xiangha`：搜索页候选增强，入口为 `GET https://www.xiangha.com/so/?s=<query>`
- `Spoonacular`：基于 `SPOONACULAR_API_KEY` 的可选 recipe search 参考源
- `USDA_FDC`：联网兜底营养标签

这些 provider 失败时只影响增强能力，不阻断本地推荐链路。`xiachufang`、`douguo`、`xiangha` 都只是运行时 reference-only 搜索 provider，依赖搜索页 HTML 结构与可访问性，不写入 `source_manifest.json`，也不应视为稳定 API 或运行时必需依赖；`Spoonacular` 同样仅作为可选参考。

## 验证方法
配置完成后运行：

```bash
python3 dish-health-recommender/scripts/validate_apis.py
python3 dish-health-recommender/scripts/validate_images.py
```

验证产物会写入：
- `dish-health-recommender/validation/api-validation-report.json`
- `dish-health-recommender/validation/api-validation.md`
- `dish-health-recommender/validation/image-validation-report.json`

`validate_apis.py` 会同时输出：
- `CookBook-KG`
- `xiachufang`
- `douguo`
- `xiangha`
- `Spoonacular`
- `USDA_FDC`
- `baidu_dish_recognition`
- `domestic_ocr_api`
- `mac_vision_ocr`
- `ocr_assisted_vision`

期望：
- `baidu_dish_recognition` 未配置时为 `needs_credentials`，配置后变为 `validated` 或 `degraded`
- `domestic_ocr_api` 未配置时为 `needs_credentials`，配置后变为 `validated` 或 `degraded`
- `mac_vision_ocr` 通常为 `validated` 或 `degraded`
- `ocr_assisted_vision` 在可解析 OCR 文本时为 `validated`
- 图片验证报告包含统一的 `report_name`、`report_path`、`results` 顶层字段，便于后续指标统计与报告对齐复用
