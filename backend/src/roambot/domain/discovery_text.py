"""Document structure helpers; no scenery or user-phrase vocabulary."""

import re


def venue_paragraphs(place, source):
    name = re.split(r"[（(]", place["name"], maxsplit=1)[0]
    paragraphs = [
        p.strip() for p in re.split(r"\n\s*\n|\[\.\.\.\]", source.get("excerpt", "")) if p.strip()
    ]
    anchors = [i for i, paragraph in enumerate(paragraphs) if name in paragraph]
    if not anchors:
        return paragraphs if name in source.get("title", "") else []
    allowed = set()
    for anchor in anchors:
        for i in range(anchor, min(len(paragraphs), anchor + 5)):
            if i != anchor and re.match(r"^\d{1,2}[.、\s]*[\u3400-\u9fff]{2}", paragraphs[i]):
                break
            allowed.add(i)
    selected = [paragraph for i, paragraph in enumerate(paragraphs) if i in allowed]
    result = []
    for paragraph in selected:
        if len(paragraph) <= 720 or name not in paragraph:
            result.append(paragraph)
            continue
        # Flattened articles may put several venues in one long paragraph. Keep
        # the named sentence and its immediate continuation, not the whole essay.
        sentences = re.split(r"(?<=[。！？!?])", paragraph)
        indices = {j for i, sentence in enumerate(sentences) if name in sentence
            for j in (i, i + 1) if j < len(sentences)}
        result.extend(sentences[i] for i in sorted(indices))
    return result
