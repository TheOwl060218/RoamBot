const sceneryLabels: Record<string, string> = {
  lake: '湖景',
  sea: '海景',
  old_town: '古镇',
  museum: '博物馆',
  park: '公园',
  mountain: '山地',
}

export function scenerySummary(tags: string[]) {
  return tags.map((tag) => sceneryLabels[tag] ?? tag).join('、') || '地点'
}
