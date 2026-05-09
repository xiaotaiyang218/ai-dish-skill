# API Validation Matrix

| Provider | Type | Status | Credential Requirement | Notes |
| --- | --- | --- | --- | --- |
| CookBook-KG | fallback | validated | none |  |
| xiachufang | reference | validated | none | skip online search provider and keep local-first fallback chain |
| douguo | reference | validated | none | skip online search provider and keep local-first fallback chain |
| xiangha | reference | validated | none | skip online search provider and keep local-first fallback chain |
| Spoonacular | reference | validated | SPOONACULAR_API_KEY |  |
| USDA_FDC | fallback | degraded | none | HTTP Error 429: Too Many Requests |
| baidu_dish_recognition | vision | degraded | none | fallback to OCR-assisted vision |
| ocr_assisted_vision | vision | validated | none | use OCR text / manual review |
| domestic_ocr_api | vision | needs_credentials | set DOMESTIC_OCR_ENDPOINT and DOMESTIC_OCR_API_KEY | fallback to local mac vision OCR |
| mac_vision_ocr | vision | validated | none |  |
