#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

import scripts.recommend as core  # noqa: E402
from scripts import apply_feedback  # noqa: E402

GOAL_KEYWORDS = {
    '低盐': ['低盐', '少盐', '高血压'],
    '控糖': ['控糖', '糖尿病', '少糖'],
    '减脂': ['减脂', '减肥', '低脂', '控制热量'],
    '高蛋白': ['高蛋白', '增肌', '蛋白质'],
}
ALLERGY_KEYWORDS = {
    '鸡蛋': ['鸡蛋过敏', '蛋过敏'],
    '海鲜': ['海鲜过敏', '鱼过敏', '虾过敏', '蟹过敏'],
    '坚果': ['坚果过敏', '花生过敏', '芝麻过敏'],
}
DISH_HINT_KEYWORDS = ['饭', '面', '汤', '粉', '鱼', '虾', '鸡', '肉', '菜', '饺', '馄饨', '堡', '豆腐', '肠粉', '生煎', '鱼丸', '排骨']
MENU_STOPWORDS = ['Administration', '行政', '特色档口菜单', '餐厅', '档口', '主荤', '半荤', '素菜', '例汤', '主食', '粗粮', '小吃']


def parse_user_intent(user_query: str, payload: dict[str, Any]) -> dict[str, Any]:
    profile = dict(core.DEFAULT_PROFILE)
    raw_profile = payload.get('user_profile') or {}
    if isinstance(raw_profile, dict):
        profile.update(raw_profile)
    for allergy, keywords in ALLERGY_KEYWORDS.items():
        if any(k in user_query for k in keywords):
            profile['allergies'].append(allergy)
    for goal, keywords in GOAL_KEYWORDS.items():
        if any(k in user_query for k in keywords):
            if goal in ['低盐']:
                profile['conditions'].append(goal)
            else:
                profile['goals'].append(goal)
    if '适合' in user_query or '能吃吗' in user_query:
        intent = 'dish_question'
    else:
        intent = 'general'
    if any(k in user_query for k in ['菜单', '挑', '推荐', '选几个']) and (payload.get('image_path') or payload.get('image_reference')):
        intent = 'menu_selection'
    if any(k in user_query for k in ['营养', '热量', '蛋白质', '脂肪', '钠']) and '菜单' not in user_query:
        intent = 'nutrition_query'
    if '豆腐脑' in user_query and '甜' not in user_query and '咸' not in user_query:
        intent = 'variant_question'
    top_n = 3
    m = re.search(r'([0-9一二三四五])个', user_query)
    if m:
        mapping = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5}
        top_n = mapping.get(m.group(1), None) or int(m.group(1))
    return {'intent': intent, 'profile': profile, 'top_n': top_n}


def extract_menu_candidates(image_result: dict[str, Any]) -> list[str]:
    lines = image_result.get('ocr', {}).get('lines', [])
    candidates: list[str] = []
    for line in lines:
        if any(stop in line for stop in MENU_STOPWORDS):
            continue
        if len(line) < 2:
            continue
        if not any(k in line for k in DISH_HINT_KEYWORDS):
            continue
        if re.fullmatch(r'[0-9A-Za-z•· ]+', line):
            continue
        candidates.append(line)
    unique: list[str] = []
    for item in candidates:
        if item not in unique:
            unique.append(item)
    return unique


def score_menu_candidate(name: str, profile: dict[str, Any]) -> tuple[str, list[str]]:
    reasons = []
    score = 0
    if any(x in name for x in ['清炒', '清蒸', '西兰花', '冬瓜', '青菜', '白菜', '芹菜', '上海青']):
        score += 3
        reasons.append('做法或食材相对清淡')
    if any(x in name for x in ['剁椒', '红烧', '烤肉', '肥肠', '麻辣', '炸', '叉烧', '排骨', '猪脚', '脆骨', '牛蛙']):
        score -= 2
        reasons.append('可能偏油、偏盐或肉量较高')
    if '低盐' in profile.get('conditions', []) and any(x in name for x in ['剁椒', '红烧', '叉烧', '肥肠', '麻辣', '烤鸭']):
        score -= 2
        reasons.append('低盐需求下不太占优')
    if '减脂' in profile.get('goals', []) and any(x in name for x in ['炸', '烤鸭', '烤肉', '肉夹馍', '排骨', '猪脚']):
        score -= 2
        reasons.append('减脂目标下热量风险偏高')
    if '高蛋白' in profile.get('goals', []) and any(x in name for x in ['鸡腿', '牛肉', '鱼', '虾', '鸡胸']):
        score += 2
        reasons.append('含较明确的蛋白质来源')
    if '海鲜' in profile.get('allergies', []) and any(x in name for x in ['虾', '鱼', '蟹']):
        score -= 100
        reasons.append('命中海鲜过敏风险')
    if '鸡蛋' in profile.get('allergies', []) and '蛋' in name:
        score -= 100
        reasons.append('命中鸡蛋过敏风险')
    level = 'recommend' if score >= 2 else 'caution' if score >= 0 else 'avoid'
    return level, reasons or ['需要结合具体配方进一步确认']


def render_nutrition_cn(result: dict[str, Any]) -> str:
    quant = result.get('nutrition_quantitative')
    if not quant:
        return '当前没有命中可靠的标准配方，因此先给你定性营养判断，不强行给出精确数值。'
    basis = result.get('nutrition_basis', '标准配方估算')
    portion = result.get('portion_basis', '标准份量')
    return (
        f'按{portion}、基于{basis}估算：热量约 {quant.get("energy_kcal", "-")} 千卡，'
        f'蛋白质约 {quant.get("protein_g", "-")} 克，脂肪约 {quant.get("fat_g", "-")} 克，'
        f'碳水约 {quant.get("carbohydrate_g", "-")} 克，糖约 {quant.get("sugars_g", "-")} 克，'
        f'钠约 {quant.get("sodium_mg", "-")} 毫克。'
    )


def render_single_dish_answer(user_query: str, result: dict[str, Any]) -> str:
    label = {'recommend': '推荐', 'caution': '谨慎', 'avoid': '不推荐', 'need_confirm': '需要确认'}[result['recommendation']]
    reasons = []
    if '依据：' in result.get('explanation', ''):
        reasons = [x for x in result['explanation'].split('依据：', 1)[1].split('；') if x]
    reasons = reasons[:4]
    lines = [f'结论：{label}。']
    if result.get('normalized_dish'):
        lines.append(f'我把这道菜识别为：{result["normalized_dish"]}。')
    if reasons:
        lines.append('原因：')
        for i, reason in enumerate(reasons, 1):
            lines.append(f'{i}. {reason}')
    lines.append(render_nutrition_cn(result))
    if result.get('need_confirm'):
        lines.append(f'如果要判断得更准确，我还需要你补充：{"、".join(result["need_confirm"])}。')
    lines.append('以上仅作饮食参考，不能替代医生或营养师建议。')
    return '\n'.join(lines)


def render_variant_tofu_nao(profile: dict[str, Any]) -> str:
    sweet = '甜豆腐脑通常会加糖，控糖人群一般不优先。'
    salty = '咸豆腐脑更要关注钠和调味，低盐或高血压人群要谨慎。'
    if '控糖' in profile.get('conditions', []) or '控糖' in profile.get('goals', []):
        sweet += '对你这种控糖场景，甜口明显更不占优。'
    if '低盐' in profile.get('conditions', []):
        salty += '如果你在低盐，咸口也不建议随意多吃。'
    return '\n'.join([
        '豆腐脑需要分口味来看。',
        f'1. 甜豆腐脑：{sweet}',
        f'2. 咸豆腐脑：{salty}',
        '你吃的是甜的还是咸的？我可以再按那个版本给你更准确的建议。',
    ])


def render_menu_answer(user_query: str, candidates: list[str], profile: dict[str, Any], top_n: int) -> str:
    if not any(profile.get(k) for k in ['allergies', 'conditions', 'goals']):
        return '我已经识别出这是一张菜单图，但你还没告诉我你更在意低盐、控糖、减脂、高蛋白还是过敏规避中的哪一种。你可以告诉我目标，我再从菜单里帮你挑 3 个最适合的菜。'
    scored = []
    for name in candidates:
        level, reasons = score_menu_candidate(name, profile)
        scored.append((level, name, reasons))
    recommend_items = [item for item in scored if item[0] == 'recommend'][:top_n]
    caution_items = [item for item in scored if item[0] == 'caution'][:top_n]
    avoid_items = [item for item in scored if item[0] == 'avoid'][:top_n]
    lines = ['我先按你的需求，从这张菜单里帮你筛一轮：', '']
    if recommend_items:
        lines.append('更适合优先考虑：')
        for idx, (_, name, reasons) in enumerate(recommend_items, 1):
            lines.append(f'{idx}. {name}：{"；".join(reasons[:2])}')
        lines.append('')
    if caution_items:
        lines.append('可以谨慎考虑：')
        for idx, (_, name, reasons) in enumerate(caution_items, 1):
            lines.append(f'{idx}. {name}：{"；".join(reasons[:2])}')
        lines.append('')
    if avoid_items:
        lines.append('不太建议优先选：')
        for idx, (_, name, reasons) in enumerate(avoid_items, 1):
            lines.append(f'{idx}. {name}：{"；".join(reasons[:2])}')
        lines.append('')
    lines.append('如果你愿意，我还可以继续按“控糖 / 低盐 / 减脂 / 高蛋白”中的某一个目标，再给你精细筛一轮。')
    return '\n'.join(lines)


def render_clarification(payload: dict[str, Any], reason: str) -> str:
    return '\n'.join([
        f'我暂时不能可靠判断这张图里的具体菜品，原因是：{reason}。',
        '你可以补充这几类信息中的任意一种：',
        '1. 这是菜单还是单道菜照片？',
        '2. 你最想分析哪一道？',
        '3. 你有鸡蛋过敏、控糖、低盐、减脂、高蛋白之类需求吗？',
    ])


def answer_user_query(payload: dict[str, Any]) -> str:
    user_query = str(payload.get('user_query') or payload.get('query') or '').strip()
    if not user_query:
        return '请直接告诉我你的问题，比如“我鸡蛋过敏，这道番茄炒蛋能吃吗？”或者“帮我从这张菜单里挑 3 个更适合减脂的菜”。'
    intent = parse_user_intent(user_query, payload)
    profile = intent['profile']
    top_n = intent['top_n']
    if intent['intent'] == 'variant_question':
        return render_variant_tofu_nao(profile)
    if intent['intent'] == 'menu_selection':
        result = core.recommend({'image_path': payload.get('image_path') or payload.get('image_reference') or '', 'user_profile': profile, 'output_mode': 'json'})
        image_result = result.get('raw_image_result', {})
        candidates = extract_menu_candidates(image_result)
        if not candidates:
            return render_clarification(payload, '菜单文字识别结果不足')
        return render_menu_answer(user_query, candidates, profile, top_n)
    if payload.get('image_path') or payload.get('image_reference'):
        result = core.recommend({'image_path': payload.get('image_path') or payload.get('image_reference') or '', 'user_profile': profile, 'output_mode': 'json'})
        image_result = result.get('raw_image_result', {})
        vision_candidates = image_result.get('vision', {}).get('candidates', [])
        if not vision_candidates and result.get('recommendation') == 'need_confirm':
            return render_clarification(payload, '图片识别结果不足')
        chosen = vision_candidates[-1] if vision_candidates else result.get('normalized_dish') or ''
        if chosen:
            result = core.recommend({'dish_name': chosen, 'user_profile': profile, 'output_mode': 'json'})
        return render_single_dish_answer(user_query, result)
    # pure text flow
    if '豆腐脑' in user_query and ('甜' in user_query or '咸' in user_query):
        dish_name = '豆腐脑'
    else:
        # try to find a known dish mention
        dish_name = ''
        for alias in sorted(core.ALIASES.keys(), key=len, reverse=True):
            if alias and alias in user_query:
                dish_name = alias
                break
        if not dish_name:
            # fallback short extraction
            m = re.search(r'([\u4e00-\u9fff]{2,10})(能吃吗|适合|营养|怎么样)', user_query)
            if m:
                dish_name = m.group(1)
    if not dish_name:
        return '我还不能确定你想分析的是哪一道菜。你可以直接告诉我菜名，或者把菜单/菜肴图片发给我，我再帮你判断。'
    result = core.recommend({'dish_name': dish_name, 'user_profile': profile, 'output_mode': 'json'})
    answer = render_single_dish_answer(user_query, result)
    feedback_bias = result.get('feedback_bias', {})
    if feedback_bias:
        bias = next(iter(feedback_bias.values()))
        if bias.get('rejects', 0) > 0:
            answer += '\n另外，我注意到你之前对这类菜有过拒绝反馈，所以这次我没有把它按最高优先级推荐。'
        if bias.get('favorites', 0) > 0:
            answer += '\n另外，你之前似乎比较偏好这类菜，所以我在判断时提高了它的优先级。'
    return answer


def main() -> None:
    payload = json.load(sys.stdin) if len(sys.argv) == 1 else json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    print(answer_user_query(payload))


if __name__ == '__main__':
    main()
