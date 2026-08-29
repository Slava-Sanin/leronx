"""Spoken template banks for when no LLM key is configured."""
from __future__ import annotations
from .config import ScriptConfig, Tone

_CTA = {
    "en": "Create your own AI video at leronx.org",
    "ru": "Создайте своё AI-видео на leronx.org",
}

_HOOKS: dict[str, dict[Tone, list[str]]] = {
    "en": {
        Tone.PROFESSIONAL: [
            "Here's what nobody tells you about {topic}.",
            "In the next {duration} seconds, you'll understand {topic}.",
        ],
        Tone.CASUAL: [
            "Okay, so {topic} is actually wild.",
            "You won't believe how {topic} actually works.",
        ],
        Tone.EDUCATIONAL: [
            "Today we're learning about {topic}.",
            "Let's break down {topic} step by step.",
        ],
        Tone.DRAMATIC: [
            "Everything you know about {topic} is about to change.",
            "{topic} — the revolution is now.",
        ],
        Tone.HUMOROUS: [
            "So {topic} is a thing. And it's hilarious.",
            "POV: you finally understand {topic}.",
        ],
        Tone.INSPIRATIONAL: [
            "Imagine what's possible with {topic}.",
            "{topic} isn't just technology — it's a movement.",
        ],
    },
    "ru": {
        Tone.PROFESSIONAL: [
            "Вот что редко говорят про {topic}.",
            "За {duration} секунд вы поймёте суть: {topic}.",
        ],
        Tone.CASUAL: [
            "Слушай, с {topic} всё гораздо интереснее, чем кажется.",
            "Если коротко про {topic} — будет неожиданно.",
        ],
        Tone.EDUCATIONAL: [
            "Разберём {topic} спокойно и по шагам.",
            "Сегодня коротко и ясно: {topic}.",
        ],
        Tone.DRAMATIC: [
            "Всё, что вы знали про {topic}, сейчас перевернётся.",
            "{topic} — точка, после которой назад уже не получится.",
        ],
        Tone.HUMOROUS: [
            "Итак, {topic}. Да, это правда происходит.",
            "Коротко про {topic}, без лишней торжественности.",
        ],
        Tone.INSPIRATIONAL: [
            "Представьте, что становится возможным благодаря {topic}.",
            "{topic} — это не просто тема. Это сдвиг.",
        ],
    },
}

_BODIES: dict[str, dict[Tone, list[str]]] = {
    "en": {
        Tone.PROFESSIONAL: [
            "{topic} is already changing how people decide, build, and compete.",
            "The real shift is not the tool itself, but what teams choose to automate and what they keep human.",
            "Those who learn the limits of {topic} will use it as leverage instead of noise.",
            "The useful question is no longer whether {topic} matters. It is how deliberately you apply it.",
        ],
        Tone.CASUAL: [
            "People talk about {topic} like it's magic. It isn't. It's a set of tradeoffs.",
            "Once you see the pattern, {topic} stops feeling mysterious and starts feeling usable.",
            "The fun part is this: small experiments beat giant plans.",
            "If you only remember one thing about {topic}, remember to try it on a real problem.",
        ],
        Tone.EDUCATIONAL: [
            "Start with the problem {topic} is meant to solve, not with the buzzwords around it.",
            "Then look at the inputs, the outputs, and the failure modes. That is the whole map.",
            "A simple example makes {topic} concrete: one task, one constraint, one measurable result.",
            "When you can explain {topic} in one minute, you are ready to use it.",
        ],
        Tone.DRAMATIC: [
            "A quiet line has already been crossed, and {topic} is on the other side.",
            "Old workflows will not fail loudly. They will simply become too slow.",
            "The people who move now will set the defaults everyone else inherits.",
            "Ignore {topic}, and the future arrives without asking you.",
        ],
        Tone.HUMOROUS: [
            "{topic} sounds serious until you watch people use it like a slightly clever intern.",
            "Half the hype is marketing. The other half is people discovering it actually helps.",
            "Yes, you can overdo {topic}. You can also overdo coffee. We still drink coffee.",
            "The punchline is simple: learn it before your group chat explains it to you.",
        ],
        Tone.INSPIRATIONAL: [
            "{topic} is a chance to make harder work lighter, not to replace the people who care.",
            "Every useful leap starts with someone who refused to wait for a perfect plan.",
            "If you bring curiosity to {topic}, the tools become a canvas.",
            "The next chapter of {topic} will be written by the people who start today.",
        ],
    },
    "ru": {
        Tone.PROFESSIONAL: [
            "{topic} уже меняет то, как люди принимают решения, собирают продукты и конкурируют.",
            "Главный сдвиг не в самом инструменте, а в том, что команды отдают машине, а что оставляют себе.",
            "Кто понимает границы {topic}, получает рычаг. Остальные получают шум.",
            "Вопрос уже не в том, важно ли {topic}. Вопрос в том, насколько осознанно вы это применяете.",
        ],
        Tone.CASUAL: [
            "Про {topic} говорят так, будто это магия. На деле это набор компромиссов.",
            "Как только видишь схему, {topic} перестаёт быть загадкой и становится рабочим приёмом.",
            "Маленький эксперимент почти всегда лучше большого плана на бумаге.",
            "Если запомнить одно: проверьте {topic} на настоящей задаче, не на лозунге.",
        ],
        Tone.EDUCATIONAL: [
            "Начните с задачи, которую должен решать {topic}, а не со слов вокруг неё.",
            "Дальше — входы, выходы и типичные ошибки. Это уже почти вся карта.",
            "Один простой пример делает {topic} понятным: одна задача, одно ограничение, один результат.",
            "Когда вы объясняете {topic} за минуту, вы готовы этим пользоваться.",
        ],
        Tone.DRAMATIC: [
            "Тихая граница уже пройдена, и {topic} оказался по ту сторону.",
            "Старые процессы не сломаются с грохотом. Они просто станут слишком медленными.",
            "Те, кто двинется сейчас, зададут правила, которые остальные потом примут как данность.",
            "Игнорировать {topic} — значит встретить будущее без права голоса.",
        ],
        Tone.HUMOROUS: [
            "{topic} звучит торжественно, пока не видишь, как этим пользуются в повседневных мелочах.",
            "Половина шума — маркетинг. Вторая половина — люди, которым это правда помогло.",
            "Да, {topic} можно переборщить. Кофе тоже. Кофе мы всё равно пьём.",
            "Мораль простая: разберитесь раньше, чем вам это перескажут в чате.",
        ],
        Tone.INSPIRATIONAL: [
            "{topic} может сделать тяжёлую работу легче, а не вычеркнуть тех, кому не всё равно.",
            "Каждый полезный скачок начинается с человека, который не ждал идеального плана.",
            "Если к {topic} подойти с любопытством, инструменты становятся холстом.",
            "Следующую главу {topic} напишут те, кто начнёт сегодня.",
        ],
    },
}


def _lang(config: ScriptConfig) -> str:
    code = (config.language or "en").lower()[:2]
    return code if code in _BODIES else "en"


def hook_line(config: ScriptConfig) -> str:
    lang = _lang(config)
    tone = config.tone if isinstance(config.tone, Tone) else Tone.PROFESSIONAL
    hooks = _HOOKS[lang].get(tone, _HOOKS[lang][Tone.PROFESSIONAL])
    line = hooks[hash(config.topic) % len(hooks)]
    return line.format(topic=config.topic, duration=config.duration)


def cta_line(config: ScriptConfig) -> str:
    return _CTA.get(_lang(config), _CTA["en"])


def body_scenes(config: ScriptConfig) -> list[str]:
    lang = _lang(config)
    tone = config.tone if isinstance(config.tone, Tone) else Tone.PROFESSIONAL
    bank = _BODIES[lang].get(tone, _BODIES[lang][Tone.PROFESSIONAL])
    n = max(2, min(len(bank), max(2, config.duration // 15)))
    slice_len = config.duration // n
    scenes = []
    for i in range(n):
        start = i * slice_len
        end = config.duration if i == n - 1 else (i + 1) * slice_len
        text = bank[i % len(bank)].format(topic=config.topic, duration=config.duration)
        scenes.append(f"[Scene {i + 1}: {start}s-{end}s]\n{text}")
    return scenes
