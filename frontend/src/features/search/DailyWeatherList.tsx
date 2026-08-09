import type { DailySuitability, DailyWeather } from '../../api/types'
import { Cloud, CloudFog, CloudLightning, CloudRain, CloudSnow, CloudSun, Sun } from 'lucide-react'

const adviceLabels = {
  suitable: '适合前往',
  caution: '谨慎考虑',
  not_recommended: '不建议当日前往',
} as const

const chineseDate = new Intl.DateTimeFormat('zh-CN', {
  month: 'long',
  day: 'numeric',
  timeZone: 'UTC',
})

type DailyWeatherListProps = {
  weather: DailyWeather[]
  suitability: DailySuitability[]
}

export function DailyWeatherList({ weather, suitability }: DailyWeatherListProps) {
  const variant = weather.length === 1 ? 'single' : 'multi'

  return (
    <div className={`weather-list weather-list-${variant}`}>
      {weather.map((day) => {
        const advice = suitability.find((item) => item.date === day.date)
        return (
          <article className="weather-day" key={day.date}>
            <div className="weather-day-heading">
              <time dateTime={day.date}>{chineseDate.format(new Date(`${day.date}T00:00:00Z`))}</time>
              <div className="weather-condition">
                <WeatherIcon condition={day.condition} />
                <strong>{day.condition}</strong>
              </div>
            </div>
            <div className="weather-facts">
              <div className="weather-temperature"><span>温度</span><strong>{day.temp_min_c}–{day.temp_max_c}°C</strong></div>
              <div className="weather-advice">
                <span>出行建议</span>
                <strong>{advice ? adviceLabels[advice.status] : '暂无判断'}</strong>
              </div>
            </div>
            {advice && <p className="weather-summary">{advice.summary}</p>}
          </article>
        )
      })}
    </div>
  )
}

function WeatherIcon({ condition }: { condition: string }) {
  const props = { 'aria-hidden': true as const, size: 28, strokeWidth: 1.8 }
  if (/雷/.test(condition)) return <CloudLightning {...props} />
  if (/雪|冰雹/.test(condition)) return <CloudSnow {...props} />
  if (/雨/.test(condition)) return <CloudRain {...props} />
  if (/雾|霾|沙|尘/.test(condition)) return <CloudFog {...props} />
  if (/多云/.test(condition)) return <CloudSun {...props} />
  if (/阴/.test(condition)) return <Cloud {...props} />
  return <Sun {...props} />
}
