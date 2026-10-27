import type { SceneryType } from '../../api/types'

/** Conservative offline compatibility only; subjective preferences still need AI. */
export function localSceneryTypes(text: string): SceneryType[] {
  const positive = text.split(/[，,。；;\n]/).filter(part => !/不要|不想|避开|不去/.test(part)).join('，')
  const rules: [SceneryType, RegExp][] = [
    ['lake', /湖|水边|水库/], ['sea', /海边|海景|海岸|海滩/], ['old_town', /古镇|古街|历史街区/],
    ['museum', /博物馆|展览|美术馆|室内/], ['park', /公园|绿地|湿地|散步/], ['mountain', /登山|徒步|爬山|山景/],
  ]
  return rules.filter(([, pattern]) => pattern.test(positive)).map(([kind]) => kind)
}
