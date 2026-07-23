import type { DailySuitability, DailyWeather } from '../../api/types'

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
  return (
    <div className="weather-list">
      {weather.map((day) => {
        const advice = suitability.find((item) => item.date === day.date)
        return (
          <article className="weather-day" key={day.date}>
            <div>
              <time dateTime={day.date}>{chineseDate.format(new Date(`${day.date}T00:00:00Z`))}</time>
              <strong>{day.condition}</strong>
            </div>
            <div className="weather-temperature">{day.temp_min_c}–{day.temp_max_c}°C</div>
            <div className="weather-advice">
              <span>出行建议</span>
              <strong>{advice ? adviceLabels[advice.status] : '暂无判断'}</strong>
            </div>
            {advice && <p className="weather-summary">{advice.summary}</p>}
          </article>
        )
      })}
    </div>
  )
}
