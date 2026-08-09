function labelFor(value: number, labels: readonly [string, string, string, string]) {
  if (value >= 85) return labels[0]
  if (value >= 70) return labels[1]
  if (value >= 50) return labels[2]
  return labels[3]
}

export function weatherMatchLabel(value: number) {
  return labelFor(value, ['非常适合', '比较适合', '条件一般', '不太适合'])
}

export function distanceMatchLabel(value: number) {
  return labelFor(value, ['很轻松', '较轻松', '距离适中', '距离较远'])
}

export function fairnessMatchLabel(value: number) {
  return labelFor(value, ['差异很小', '差异较小', '差异较大', '差异很大'])
}

export function popularityMatchLabel(value: number) {
  return labelFor(value, ['人气很高', '较热门', '热度适中', '相对小众'])
}

export function tripMatchIndex(value: number) {
  return Math.round(value)
}
