import type { DailySuitability, DailyWeather } from '../../api/types'
import { weatherMatchLabel } from './matchLabels'

type DailyWeatherListProps = {
  weather: DailyWeather[]
  suitability: DailySuitability[]
}

export function DailyWeatherList({ weather, suitability }: DailyWeatherListProps) {
  return (
    <div className="weather-list">
      {weather.map((day) => {
        const score = suitability.find((item) => item.date === day.date)
        return (
          <article className="weather-day" key={day.date}>
            <div>
              <time dateTime={day.date}>{day.date.slice(5).replace('-', '/')}</time>
              <strong>{day.condition}</strong>
            </div>
            <div className="weather-temperature">{day.temp_min_c}–{day.temp_max_c}°C</div>
            <div className="weather-score">
              适宜程度 {score ? weatherMatchLabel(score.score) : '暂无判断'}
            </div>
            {score && <p>{score.reasons.join('；')}</p>}
          </article>
        )
      })}
    </div>
  )
}
