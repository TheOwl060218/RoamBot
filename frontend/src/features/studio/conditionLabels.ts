import type { ConditionKey } from './types'
export const conditionLabels: Record<ConditionKey, string> = {
  mainOrigin: '出发地', companions: '同行出发地', dates: '日期', sceneryTypes: '风景',
  range: '目的地范围', targetPlace: '评估地点', weights: '偏好权重',
}
export const sceneryLabels = { lake: '湖景', sea: '海景', old_town: '古镇/历史街区', museum: '博物馆', park: '公园/绿地/湿地', mountain: '山地/徒步' }
