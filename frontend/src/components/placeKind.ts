export type PlaceKind = 'park' | 'mountain' | 'water' | 'museum' | 'street' | 'food' | 'book' | 'garden' | 'place'

// Use supplied map categories, from the most specific level, rather than guessing from a place's name.
const categories: [PlaceKind, RegExp][] = [
  ['garden', /园林|古典园|植物园/],
  ['park', /公园/],
  ['mountain', /山峰|山岳|山地|^山$/],
  ['water', /湖泊|河流|海滨|海滩|沙滩|水系|海洋|湿地/],
  ['museum', /博物馆|美术馆|展览馆|纪念馆|科技馆/],
  ['street', /步行街|特色街|街区|商业街|古镇|古城|古村/],
  ['food', /餐饮|餐厅|餐馆|火锅|小吃|咖啡|茶艺|甜品|饮品/],
  ['book', /书店|图书馆|书吧/],
]
const sceneryKinds: Record<string, PlaceKind> = { park: 'park', mountain: 'mountain', lake: 'water', river: 'water', sea: 'water', museum: 'museum', garden: 'garden', old_town: 'street' }

export function placeKind(typeName?: string, sceneryTags: readonly string[] = []): PlaceKind {
  for (const category of (typeName ?? '').split(/[;；·]/).map(value => value.trim()).reverse()) {
    const match = categories.find(([, pattern]) => pattern.test(category))
    if (match) return match[0]
  }
  return sceneryTags.map(tag => sceneryKinds[tag]).find(Boolean) ?? 'place'
}
